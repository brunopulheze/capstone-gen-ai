"""
Service: User Persona
=====================
Generates a detailed UX user persona from guided onboarding answers.

The LLM is instructed to honour the user's explicit gender choice and return
a structured JSON persona that the frontend renders as a persona card.
"""

import json
import re

from fastapi import APIRouter
from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq
from pydantic import BaseModel

from app.config import GROQ_API_KEY
from app.services.chat import ChatResponse

router = APIRouter()

_PERSONA_GEN_PROMPT = """\
You are a senior UX researcher at BrixoAI.
You MUST create a {gender} persona — this is a hard requirement.
Return ONLY valid JSON — no markdown fences, no prose outside the JSON object.

Client inputs:
Product / Service: {product_type}
Target Audience: {audience}
Primary Goals: {goals}
Biggest Frustration: {frustration}
Persona Gender: {gender} (REQUIRED — do not change this)

JSON schema:
{{
  "name": "Full name — must be an unambiguously {gender} name",
  "age": "age as a number string, e.g. '32'",
  "role": "Job title or life role",
  "location": "City, Country",
  "gender": "{gender}",
  "quote": "A short, candid first-person quote capturing their mindset (max 15 words)",
  "bio": "2–3 sentence narrative describing who this person is and their context",
  "goals": ["specific goal 1", "specific goal 2", "specific goal 3"],
  "pain_points": ["pain 1", "pain 2", "pain 3"],
  "motivations": ["motivation 1", "motivation 2", "motivation 3"],
  "devices": ["Mobile", "Laptop"],
  "tech_savvy": "Low"
}}

Rules:
- The persona's name must be unambiguously {gender}.
- The gender field in the JSON must be exactly "{gender}".
- Goals, pain points, and motivations must reflect BOTH the audience type AND the product.
- tech_savvy must be exactly one of: Low, Medium, High.
- Return ONLY the JSON object — no surrounding text or markdown fences.
"""


class PersonaRequest(BaseModel):
    product_type: str = ""
    audience:     str = ""
    goals:        list[str] = []
    frustration:  str = ""
    gender:       str = ""


@router.post("/persona", response_model=ChatResponse)
async def generate_persona(req: PersonaRequest):
    """Generate a UX user persona from guided onboarding answers."""
    persona_llm = ChatGroq(api_key=GROQ_API_KEY, model="llama-3.3-70b-versatile", temperature=0.7)

    gender = (req.gender or "female").lower()
    prompt = _PERSONA_GEN_PROMPT.format(
        product_type=req.product_type or "general product",
        audience=req.audience     or "general audience",
        goals=", ".join(req.goals) if req.goals else "not specified",
        frustration=req.frustration or "not specified",
        gender=gender,
    )

    response = await persona_llm.ainvoke([HumanMessage(content=prompt)])
    raw = str(response.content).strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw).rstrip("`").strip()

    try:
        persona_data = json.loads(raw)
    except json.JSONDecodeError:
        return ChatResponse(reply="I had trouble generating the persona. Please try again! 🐾")

    # Always enforce the user's explicit gender choice
    persona_data["gender"] = gender

    return ChatResponse(
        reply="✨ Your User Persona is ready! Check out the panel to meet them.",
        persona_report=persona_data,
    )
