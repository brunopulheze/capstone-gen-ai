"""
Service: Chat
=============
General-purpose conversation endpoint powered by the LangChain tool-calling agent.
Handles free-form questions, service routing, and menu-intent detection.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from app import state

router = APIRouter()

_MENU_PHRASES = [
    "menu", "show menu", "show services", "show options", "show buttons",
    "back to menu", "back to start", "start over", "reset chat", "reset",
    "see options", "see services", "see menu", "open menu",
    "what can you do", "what can you help with", "what do you offer",
]

_REDIRECT_PHRASES = [
    "outside my expertise", "how can i assist", "how can i help you today",
    "i'm not sure", "i don't understand", "could you clarify",
    "not sure what you mean", "here are our options", "here's what i can",
    "here is what i can", "i'm happy to chat", "happy to help with",
    "happy to discuss", "not within my", "outside the scope",
]


def _is_menu_intent(text: str) -> bool:
    lower = text.lower()
    return any(p in lower for p in _MENU_PHRASES)


def _is_redirect_reply(text: str) -> bool:
    lower = text.lower()
    return any(p in lower for p in _REDIRECT_PHRASES)


# ── Pydantic models ───────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []
    service_mode: str | None = None
    project_context: str | None = None


class ChatResponse(BaseModel):
    reply: str
    show_menu: bool = False
    show_menu_hint: bool = False
    trigger_service: str | None = None
    insights: dict | None = None
    audit_report: str | None = None
    scope_report: dict | None = None
    persona_report: dict | None = None
    needs_clarification: bool = False


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """General chat — routes to tools or returns a natural-language reply."""
    show_menu = _is_menu_intent(req.message)

    chat_history = [
        HumanMessage(content=m["content"]) if m["role"] == "user"
        else AIMessage(content=m["content"])
        for m in req.history
    ]

    if req.project_context:
        chat_history = [SystemMessage(content=(
            "PROJECT CONTEXT — The user's saved AI reports for this project are listed below. "
            "Use this information to answer questions about their scope, persona, UX audit, or data insights. "
            "Do NOT reveal raw JSON unless explicitly asked; summarise clearly and naturally.\n\n"
            + req.project_context
        ))] + chat_history

    result = await state.chain.ainvoke({
        "input": req.message,
        "chat_history": chat_history,
        "service_mode": req.service_mode,
    })
    answer = result["answer"]
    show_menu_hint = show_menu or _is_redirect_reply(answer)

    return ChatResponse(
        reply=answer,
        show_menu=show_menu,
        show_menu_hint=show_menu_hint,
        trigger_service=result.get("trigger_service"),
    )
