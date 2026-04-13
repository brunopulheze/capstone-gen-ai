# Data Insights Service

**Endpoint:** `POST /upload`  
**Follow-up Q&A:** `POST /chat` (with `service_mode: "data-insights"`)

## Overview

The Data Insights service accepts a CSV or Excel file, performs automated statistical analysis, and returns a rich structured payload that includes KPI cards, per-column profiles, correlation analysis, an AI narrative summary, and suggested follow-up questions.

## How It Works

```
File upload (CSV / XLS / XLSX, max 5 MB)
     │
     ▼
Validate extension and file size
     │
     ▼
Parse into pandas DataFrame
     │
     ▼
┌─────────────────────────────────────────────┐
│  Statistical Analysis (_build_insights)     │
│  - KPI cards (rows, columns, nulls)         │
│  - Per-column profiling:                    │
│    · Numeric → histogram bins, min/max/mean │
│    · Categorical → value counts             │
│    · Temporal → monthly distribution        │
│    · ID / geo columns → skipped             │
│  - Pearson correlation matrix (top pairs)   │
└─────────────────────────────────────────────┘
     │
     ▼
AI narrative summary  (Groq LLM)
     │
     ▼
3 suggested follow-up questions (Groq LLM)
     │
     ▼
Return structured insights payload
```

## Request (Multipart Form)

| Field | Type | Required | Description |
|---|---|---|---|
| `file` | `UploadFile` | ✅ | CSV, XLS, or XLSX — max 5 MB |
| `message` | `string` | — | Optional user instruction (e.g. "focus on sales trends") |
| `service_mode` | `string` | — | Should be `"data-insights"` |
| `history` | `string` (JSON) | — | Serialised chat history for context |

## Response Payload

| Field | Type | Description |
|---|---|---|
| `reply` | `string` | AI narrative summary of the dataset |
| `insights.kpis` | `list` | Cards: rows, columns, missing values, numeric cols |
| `insights.columns` | `list` | Per-column profiles (kind, distribution, stats) |
| `insights.correlations` | `list` | Top Pearson correlation pairs `{col_a, col_b, r}` |
| `insights.preview` | `list[dict]` | First N rows for a data table preview |
| `insights.ai_summary` | `string` | Full LLM-generated narrative |
| `insights.suggested_questions` | `list[string]` | 3 follow-up questions grounded in the data |

## Column Classification

Each column is automatically classified into a `kind` before profiling:

| Kind | Subkind | Condition |
|---|---|---|
| `numeric` | — | Numeric, measure-like name, or >10 unique integer values |
| `categorical` | `temporal` | Datetime dtype |
| `categorical` | `geo` | Name matches lat/lon/latitude/longitude |
| `categorical` | `id` | Unique ratio >95% or name matches `id` pattern |
| `categorical` | — | Numeric but ≤10 unique integer values |

## File Limits

| Limit | Value |
|---|---|
| Max file size | 5 MB |
| Supported formats | CSV, XLS, XLSX |

## Technology

- **Data processing:** pandas, NumPy
- **LLM:** Groq (via `state.llm_quick` — `llama-3.3-70b-versatile`)
- **Correlation:** Pearson via `pandas.DataFrame.corr()`
