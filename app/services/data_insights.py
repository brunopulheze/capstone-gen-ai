"""
Service: Data Insights
======================
Handles CSV/Excel file uploads and free-form data Q&A.

Features:
  - Parse uploaded CSV/Excel into a pandas DataFrame
  - Compute KPI cards, per-column profiles (numeric, categorical, temporal)
  - Build histogram / value-count distributions
  - Compute Pearson correlation matrix and top pairs
  - Generate an AI narrative summary via the LLM
  - Suggest 3 grounded follow-up questions using the LLM
  - Follow-up Q&A endpoint: answer natural-language questions about the dataset
"""

import io
import json
import re

import numpy as np
import pandas as pd
from fastapi import APIRouter, File, Form, UploadFile
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from pydantic import BaseModel

from app import state
from app.config import GROQ_API_KEY
from app.services.chat import ChatResponse

router = APIRouter()

_MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
_ALLOWED_EXTENSIONS = {"csv", "xls", "xlsx"}

# ── DataFrame helpers ─────────────────────────────────────────────────────────

def _fmt(v: float) -> str:
    if abs(v) >= 1_000_000:
        return f"{v / 1_000_000:.1f}M"
    if abs(v) >= 1_000:
        return f"{v / 1_000:.1f}k"
    return f"{v:.4g}"


_ID_NAME      = re.compile(r"\bid\b", re.IGNORECASE)
_GEO_NAME     = re.compile(r"\b(lat|latitude|lon|lng|longitude)\b", re.IGNORECASE)
_MEASURE_NAME = re.compile(
    r"\b(income|revenue|salary|wages|amount|value|price|cost|rate|score|"
    r"count|total|sum|avg|average|balance|weight|height|age|duration|"
    r"distance|quantity|qty|profit|loss|tax|fee|charge|payment|budget|"
    r"spend|spending|premium|claim|lifetime|coverage)\b",
    re.IGNORECASE,
)


def _build_insights(df: pd.DataFrame, filename: str, ai_summary: str = "") -> dict:
    """Build a structured insights payload from a parsed DataFrame."""
    null_total = int(df.isnull().sum().sum())
    numeric_cols = df.select_dtypes(include="number").columns.tolist()

    kpis = [
        {"label": "Rows",            "value": f"{len(df):,}"},
        {"label": "Columns",         "value": str(len(df.columns))},
        {"label": "Missing Values",  "value": f"{null_total:,}"},
        {"label": "Numeric Columns", "value": str(len(numeric_cols))},
    ]

    columns: list[dict] = []
    for col in df.columns:
        series = df[col]
        null_count = int(series.isnull().sum())
        info: dict = {
            "name":     col,
            "dtype":    str(series.dtype),
            "nulls":    null_count,
            "null_pct": round(null_count / len(df) * 100, 1) if len(df) else 0.0,
            "unique":   int(series.nunique()),
        }

        # ── Datetime ──────────────────────────────────────────────────────────
        if pd.api.types.is_datetime64_any_dtype(series):
            clean   = series.dropna().sort_values()
            monthly = clean.dt.to_period("M").value_counts().sort_index()
            info["kind"]         = "categorical"
            info["subkind"]      = "temporal"
            info["distribution"] = [{"bin": str(p), "count": int(c)} for p, c in monthly.items()]
            columns.append(info)
            continue

        # ── Numeric ───────────────────────────────────────────────────────────
        if pd.api.types.is_numeric_dtype(series):
            clean = series.dropna()

            if _GEO_NAME.search(col):
                info["kind"] = "categorical"; info["subkind"] = "geo"; info["distribution"] = []
                columns.append(info); continue

            is_measure           = bool(_MEASURE_NAME.search(col))
            is_id_by_cardinality = not is_measure and len(df) > 0 and info["unique"] / len(df) > 0.95
            is_id_by_name        = not is_measure and bool(_ID_NAME.search(col))
            if is_id_by_cardinality or is_id_by_name:
                info["kind"] = "categorical"; info["subkind"] = "id"; info["distribution"] = []
                columns.append(info); continue

            all_integers = bool((clean % 1 == 0).all())
            if not is_measure and all_integers and info["unique"] <= 10:
                vc = series.value_counts().sort_index()
                info["kind"]         = "categorical"
                info["distribution"] = [{"bin": str(int(v)), "count": int(c)} for v, c in vc.items()]
                columns.append(info); continue

            info["kind"]   = "numeric"
            info["min"]    = round(float(clean.min()), 2)   if len(clean) else None
            info["max"]    = round(float(clean.max()), 2)   if len(clean) else None
            info["mean"]   = round(float(clean.mean()), 2)  if len(clean) else None
            info["median"] = round(float(clean.median()), 2) if len(clean) else None
            info["std"]    = round(float(clean.std()), 2)   if len(clean) else None

            counts, edges = np.histogram(clean, bins=min(10, len(clean.unique())))
            avg_bin = (edges[-1] - edges[0]) / len(counts) if len(counts) else 0
            def _fe(v: float) -> str:
                return str(int(round(v))) if avg_bin >= 1.0 else _fmt(v)
            info["distribution"] = [
                {"bin": f"{_fe(edges[i])}\u2013{_fe(edges[i+1])}", "count": int(counts[i])}
                for i in range(len(counts))
            ]

        # ── Categorical / string ──────────────────────────────────────────────
        else:
            non_null   = series.dropna()
            parse_rate = 0.0
            if len(non_null) > 0:
                parsed     = pd.to_datetime(non_null, errors="coerce", infer_datetime_format=True)
                parse_rate = parsed.notna().sum() / len(non_null)
            if parse_rate >= 0.8:
                monthly = parsed.dropna().sort_values().dt.to_period("M").value_counts().sort_index()
                info["kind"]         = "categorical"
                info["subkind"]      = "temporal"
                info["distribution"] = [{"bin": str(p), "count": int(c)} for p, c in monthly.items()]
            else:
                vc = series.value_counts().head(10)
                info["kind"]         = "categorical"
                info["distribution"] = [{"bin": str(k), "count": int(v)} for k, v in vc.items()]

        columns.append(info)

    preview = df.head(5).fillna("").astype(str).to_dict(orient="records")

    # ── Correlation ───────────────────────────────────────────────────────────
    orig_numeric = df.select_dtypes(include="number").columns.tolist()
    correlations: list[dict] = []
    correlation_matrix: dict = {}
    if len(orig_numeric) >= 2:
        corr_df = df[orig_numeric].dropna(how="all").corr(method="pearson", numeric_only=True)
        correlation_matrix = {
            col: {
                other: round(float(corr_df.loc[col, other]), 3)
                       if not pd.isna(corr_df.loc[col, other]) else None
                for other in corr_df.columns
            }
            for col in corr_df.columns
        }
        seen: set[frozenset] = set()
        for col_a in corr_df.columns:
            for col_b in corr_df.columns:
                key = frozenset([col_a, col_b])
                if col_a == col_b or key in seen:
                    continue
                seen.add(key)
                r = corr_df.loc[col_a, col_b]
                if pd.isna(r):
                    continue
                r = float(round(r, 3))
                if abs(r) >= 0.3:
                    correlations.append({"col_a": col_a, "col_b": col_b, "r": r})
        correlations = sorted(correlations, key=lambda p: abs(p["r"]), reverse=True)[:12]

    return {
        "filename":           filename,
        "shape":              {"rows": len(df), "cols": len(df.columns)},
        "kpis":               kpis,
        "columns":            columns,
        "preview":            preview,
        "correlations":       correlations,
        "correlation_matrix": correlation_matrix,
        "ai_summary":         ai_summary,
    }


def _summarize_dataframe(df: pd.DataFrame, filename: str) -> str:
    """Return a concise text summary of a DataFrame for LLM consumption."""
    parts = [
        f"File: {filename}",
        f"Shape: {df.shape[0]:,} rows × {df.shape[1]} columns",
        f"Columns: {', '.join(df.columns.tolist())}",
        "",
        "Data Types:",
        df.dtypes.to_string(),
    ]
    null_counts = df.isnull().sum()
    if null_counts.any():
        parts.extend(["", "Missing Values:", null_counts[null_counts > 0].to_string()])
    parts.extend([
        "", "Statistical Summary:", df.describe(include="all").to_string(),
        "", "First 5 Rows:", df.head().to_string(),
    ])
    return "\n".join(parts)


# ── Upload endpoint ───────────────────────────────────────────────────────────

@router.post("/upload", response_model=ChatResponse)
async def upload_file(
    file: UploadFile = File(...),
    message: str = Form("Analyze this file and highlight key patterns, trends, and insights."),
    service_mode: str = Form("data-insights"),
    history: str = Form("[]"),
):
    """Parse a CSV/Excel upload, run AI analysis, and return structured insights."""
    filename = file.filename or "uploaded_file"
    ext = filename.rsplit(".", 1)[-1].lower()

    if ext not in _ALLOWED_EXTENSIONS:
        return ChatResponse(reply="I can only analyze CSV and Excel files (.csv, .xls, .xlsx). 📊")

    contents = await file.read()
    if len(contents) > _MAX_UPLOAD_BYTES:
        return ChatResponse(reply="Max file size is 5 MB — please upload a smaller subset. 📊")

    try:
        if ext == "csv":
            df = pd.read_csv(io.BytesIO(contents), sep=None, engine="python")
        elif ext == "xls":
            df = pd.read_excel(io.BytesIO(contents), engine="xlrd")
        else:
            df = pd.read_excel(io.BytesIO(contents), engine="openpyxl")
    except Exception:
        return ChatResponse(reply="I couldn't read that file — it may be corrupted or in an unexpected format. 🐾")

    summary          = _summarize_dataframe(df, filename)
    enhanced_message = f"{message}\n\n---\n\nData Summary:\n{summary}"

    hist = json.loads(history)
    chat_history = [
        HumanMessage(content=m["content"]) if m["role"] == "user"
        else AIMessage(content=m["content"])
        for m in hist
    ]

    result   = await state.chain.ainvoke({"input": enhanced_message, "chat_history": chat_history, "service_mode": service_mode})
    insights = _build_insights(df, filename, ai_summary=result["answer"])

    # ── Suggested follow-up questions ─────────────────────────────────────────
    suggested_questions: list[str] = []
    if state.llm_quick:
        try:
            meaningful_cols = [c["name"] for c in insights["columns"] if c.get("subkind") not in ("id", "geo")]
            corr_text = ""
            if insights["correlations"]:
                top = insights["correlations"][:3]
                corr_text = "Notable correlations: " + ", ".join(
                    f"{p['col_a']} ↔ {p['col_b']} (r={p['r']})" for p in top
                )
            q_prompt = (
                f"You are a data analyst. A user just uploaded a dataset.\n\n"
                f"AI summary:\n{result['answer']}\n\n"
                f"Meaningful columns: {', '.join(meaningful_cols[:20])}\n{corr_text}\n\n"
                f"Suggest exactly 3 specific follow-up questions referencing actual column names. "
                f'Return ONLY a JSON array of 3 strings: ["Question 1?", "Question 2?", "Question 3?"]'
            )
            q_response = await state.llm_quick.ainvoke(q_prompt)
            raw = q_response.content.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            suggested_questions = json.loads(raw)
            if not isinstance(suggested_questions, list):
                suggested_questions = []
        except Exception:
            suggested_questions = []

    insights["suggested_questions"] = suggested_questions
    return ChatResponse(reply="📊 Your Data Insights report is ready!", insights=insights)


# ── Data Q&A endpoint ─────────────────────────────────────────────────────────

_DATA_QA_SYSTEM = """You are a data analyst assistant.
The user has uploaded a dataset and is asking questions about it.
A compact summary is provided below — answer based only on that information.
Be concise, specific, and friendly. Use bullet points or short paragraphs.
Avoid code blocks unless the user explicitly asks for code.

If the user asks something clearly unrelated to the dataset, start your reply with
[TOPIC_CHANGE] on the first line (the frontend will strip it and show a menu button).

Dataset context:
{dataset_context}"""


class DataChatRequest(BaseModel):
    message: str
    history: list[dict] = []
    dataset_context: str = ""


@router.post("/chat/data", response_model=ChatResponse)
async def chat_data(req: DataChatRequest):
    """Answer free-form questions about a previously uploaded dataset."""
    if not req.dataset_context.strip():
        return ChatResponse(reply="No dataset loaded yet — please upload a CSV or Excel file first! 📊")

    data_llm = ChatGroq(api_key=GROQ_API_KEY, model="llama-3.3-70b-versatile", temperature=0.3)

    system_prompt = _DATA_QA_SYSTEM.format(dataset_context=req.dataset_context)
    chat_history = [
        HumanMessage(content=m["content"]) if m["role"] == "user"
        else AIMessage(content=m["content"])
        for m in req.history
    ]
    messages = [SystemMessage(content=system_prompt)] + chat_history + [HumanMessage(content=req.message)]

    response     = await data_llm.ainvoke(messages)
    reply        = str(response.content).strip()
    topic_change = reply.startswith("[TOPIC_CHANGE]")
    if topic_change:
        reply = reply[len("[TOPIC_CHANGE]"):].lstrip("\n").strip()

    return ChatResponse(reply=reply, show_menu_hint=topic_change)
