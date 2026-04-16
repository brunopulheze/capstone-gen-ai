"""
Service: Scope Project
======================
Generates a structured project scope document from guided onboarding answers.

Features:
  - Pre-flight contradiction check between structured answers and free-text description.
  - Competitor URL scraping (up to 3 URLs) to inform scope with competitor insights.
  - Brand preferences → AI-generated colour palette (5 swatches).
  - Palette regeneration endpoint (POST /regenerate-palette).
"""

import json
import re

from fastapi import APIRouter
from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq
from pydantic import BaseModel

from app import state
from app.config import GROQ_API_KEY
from app.services.chat import ChatResponse
from app.services.ux_audit import _scrape_url   # reuse URL scraper

router = APIRouter()

# ── Prompts ───────────────────────────────────────────────────────────────────

_CONTRADICTION_CHECK_PROMPT = """\
A user completed a project scoping questionnaire and then added a free-text description.

Structured answers:
- Business Type: {business_type}
- Project Type: {project_type}
- Features: {features}

Free-text description: "{description}"

Decide whether the free-text MEANINGFULLY contradicts the structured answers.
Minor additions or details that naturally extend the answers are NOT contradictions.

Return ONLY valid JSON — no prose, no markdown.

If a clear contradiction exists:
{{"has_conflict": true, "question": "One short clarifying question. Max 20 words."}}

If no contradiction:
{{"has_conflict": false}}
"""

_SCOPE_GEN_PROMPT = """\
You are a senior project scoping expert at BrixoAI — a creative & tech studio
specialising in web apps, AI/ML solutions, chatbots, data analytics, and UX/UI design.

A client provided these answers during onboarding:
Business Type: {business_type}
Project Type: {project_type}
Features Requested: {features}
Desired Timeline: {timeline}
Additional Description: {description}{competitor_context}{brand_context}

Generate a structured scope document. Return ONLY valid JSON — no markdown, no prose.

JSON schema:
{{
  "project_type": "complete descriptive title",
  "overview": "2–3 sentence plain-English project description",
  "features": ["feature 1", "feature 2", ...],
  "tech_stack": ["technology 1 (rationale)", ...],
  "timeline": "realistic estimate string",
  "next_steps": ["action 1", "action 2", "action 3"],
  "extra_notes": "string or null",
  "competitor_insights": "2–3 sentence summary or null",
  "brand_notes": "brief summary of colour/style direction or null",
  "color_palette": [{{"hex": "#RRGGBB", "name": "Colour Name"}}, ...]
}}

Rules:
- Always return exactly 5 colours in color_palette.
- If brand preferences were provided, base the palette on those. Otherwise devise a fitting palette for the industry.
- Do NOT include pricing or budget estimates anywhere.
- tech_stack: choose the stack best suited to THIS specific project; add a brief parenthetical rationale for non-obvious choices.
"""

_DEFAULT_PALETTE = [
    {"hex": "#7C3AED", "name": "Violet"},
    {"hex": "#C4B5FD", "name": "Soft Lavender"},
    {"hex": "#F5F3FF", "name": "Ghost White"},
    {"hex": "#374151", "name": "Charcoal"},
    {"hex": "#F9FAFB", "name": "Off White"},
]


# ── Pydantic models ───────────────────────────────────────────────────────────

class ScopeRequest(BaseModel):
    business_type:    str = ""
    project_type:     str = ""
    features:         list[str] = []
    timeline:         str = ""
    description:      str = ""
    clarification:    str = ""
    history:          list[dict] = []
    competitor_urls:  list[str] = []
    brand_preferences: str = ""


class PaletteRequest(BaseModel):
    project_type: str = ""
    brand_notes:  str = ""


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/scope-project", response_model=ChatResponse)
async def scope_project(req: ScopeRequest):
    """Generate a structured scope document from guided onboarding answers."""
    if not req.project_type:
        return ChatResponse(reply="No project details provided. Please complete the onboarding steps.")

    scope_llm = ChatGroq(api_key=GROQ_API_KEY, model="llama-3.3-70b-versatile", temperature=0.3)

    description_text   = req.description.strip()
    clarification_text = req.clarification.strip()

    # ── Contradiction check ───────────────────────────────────────────────────
    if description_text and not clarification_text:
        check_prompt = _CONTRADICTION_CHECK_PROMPT.format(
            business_type=req.business_type or "Not specified",
            project_type=req.project_type,
            features=", ".join(req.features) if req.features else "Not specified",
            description=description_text,
        )
        try:
            check_response = await (state.llm_quick or scope_llm).ainvoke([HumanMessage(content=check_prompt)])
            check_raw = str(check_response.content).strip()
            if check_raw.startswith("```"):
                check_raw = re.sub(r"^```[a-z]*\n?", "", check_raw).rstrip("`").strip()
            check_data = json.loads(check_raw)
            if check_data.get("has_conflict"):
                question = check_data.get("question", "Could you clarify — which industry or product type should we focus on?")
                return ChatResponse(
                    reply=f"🐾 I noticed something that might change your scope — {question}",
                    needs_clarification=True,
                )
        except Exception:
            pass  # fail silently — proceed without check

    # ── Build combined description ────────────────────────────────────────────
    if clarification_text:
        combined_description = f"{description_text}\nClarification from user: {clarification_text}".strip()
    elif description_text:
        combined_description = description_text
    else:
        combined_description = "Not provided"

    # ── Competitor scraping ───────────────────────────────────────────────────
    competitor_snippets: list[str] = []
    for comp_url in (req.competitor_urls or [])[:3]:
        if not comp_url.startswith(("http://", "https://")):
            continue
        try:
            scraped = _scrape_url(comp_url)
            competitor_snippets.append(f"- {comp_url}:\n{scraped[:600]}")
        except Exception:
            competitor_snippets.append(f"- {comp_url}: (could not scrape)")

    competitor_context = (
        "\n\nCompetitor Websites (scraped content):\n" + "\n".join(competitor_snippets)
        if competitor_snippets else ""
    )
    brand_context = (
        f"\n\nClient Brand Preferences: {req.brand_preferences.strip()}"
        if req.brand_preferences and req.brand_preferences.strip() else ""
    )

    prompt = _SCOPE_GEN_PROMPT.format(
        business_type=req.business_type or "Not specified",
        project_type=req.project_type,
        features=", ".join(req.features) if req.features else "Not specified",
        timeline=req.timeline or "Not specified",
        description=combined_description,
        competitor_context=competitor_context,
        brand_context=brand_context,
    )

    response = await scope_llm.ainvoke([HumanMessage(content=prompt)])
    raw = str(response.content).strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw).rstrip("`").strip()

    try:
        scope_data = json.loads(raw)
    except json.JSONDecodeError:
        return ChatResponse(reply="I couldn't generate a clean scope card. Please try again! 💼")

    # Ensure palette is always present and complete
    palette = scope_data.get("color_palette")
    if not isinstance(palette, list) or len(palette) == 0:
        try:
            palette_prompt = (
                f"Generate exactly 5 brand colours for: {scope_data.get('project_type', req.project_type)}.\n"
                + (f"Brand preferences: {req.brand_preferences.strip()}\n" if req.brand_preferences else "")
                + 'Return ONLY a JSON array: [{"hex": "#RRGGBB", "name": "Colour Name"}, ...]'
            )
            palette_resp = await scope_llm.ainvoke([HumanMessage(content=palette_prompt)])
            palette_raw = str(palette_resp.content).strip()
            if palette_raw.startswith("```"):
                palette_raw = re.sub(r"^```[a-z]*\n?", "", palette_raw).rstrip("`").strip()
            parsed = json.loads(palette_raw)
            if isinstance(parsed, list) and len(parsed) > 0:
                scope_data["color_palette"] = [p for p in parsed if "hex" in p and "name" in p][:5]
        except Exception:
            scope_data["color_palette"] = _DEFAULT_PALETTE

    return ChatResponse(reply="✨ Your project scope is ready! Take a look at the panel ←", scope_report=scope_data)


@router.post("/regenerate-palette")
async def regenerate_palette(req: PaletteRequest):
    """Return a fresh 5-colour palette for an existing scope report."""
    palette_llm = ChatGroq(api_key=GROQ_API_KEY, model="llama-3.3-70b-versatile", temperature=0.8)
    palette_prompt = (
        f"Generate exactly 5 brand colours for: {req.project_type}.\n"
        + (f"Brand preferences/notes: {req.brand_notes}\n" if req.brand_notes else "")
        + 'Return ONLY a JSON array: [{"hex": "#RRGGBB", "name": "Colour Name"}, ...]'
    )
    try:
        resp = await palette_llm.ainvoke([HumanMessage(content=palette_prompt)])
        raw = str(resp.content).strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw).rstrip("`").strip()
        parsed = json.loads(raw)
        if isinstance(parsed, list) and len(parsed) > 0:
            return {"color_palette": [p for p in parsed if "hex" in p and "name" in p][:5]}
    except Exception:
        pass
    return {"color_palette": []}
