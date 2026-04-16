"""
BrixoAI Capstone — FastAPI Application Entry Point
====================================================
Modular design: each service (chat, data insights, UX audit, scope project,
user persona) lives in its own file under app/services/.
This file only handles app lifecycle and wires the routers together.

Run with:
    uvicorn app.main:app --reload --port 8000
"""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langchain_groq import ChatGroq
from tavily import TavilyClient

from app import state
from app.config import ALLOWED_ORIGINS, GROQ_API_KEY, TAVILY_API_KEY
from app.chain import get_chain
from app.rag import build_retriever

# ── Service routers ───────────────────────────────────────────────────────────
from app.services.chat         import router as chat_router
from app.services.data_insights import router as data_router
from app.services.ux_audit     import router as ux_router
from app.services.scope_project import router as scope_router
from app.services.user_persona  import router as persona_router


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────────────────
    print(">> Building RAG retriever …")
    for attempt in range(3):
        try:
            retriever     = build_retriever(k=4)
            state.chain   = get_chain(GROQ_API_KEY, retriever=retriever)
            print(">> RAG retriever ready. Server is live.")
            break
        except Exception as exc:
            if attempt < 2:
                wait = (attempt + 1) * 5
                print(f">> RAG build attempt {attempt + 1} failed ({exc!r}). Retrying in {wait}s …")
                await asyncio.sleep(wait)
            else:
                print(f">> WARNING: RAG build failed — starting without retriever. Error: {exc!r}")
                state.chain = get_chain(GROQ_API_KEY)

    state.llm_quick = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.5, api_key=GROQ_API_KEY)

    state.tavily_client = TavilyClient(api_key=TAVILY_API_KEY) if TAVILY_API_KEY else None
    if state.tavily_client:
        print(">> Tavily client ready for UX Audit reflexion.")

    yield
    # ── Shutdown (nothing to clean up) ────────────────────────────────────────


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="BrixoAI Capstone API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST", "HEAD"],
    allow_headers=["Content-Type"],
)

# ── Health check ──────────────────────────────────────────────────────────────

@app.api_route("/health", methods=["GET", "HEAD"])
async def health():
    return {"status": "ok"}


# ── Register service routers ──────────────────────────────────────────────────

app.include_router(chat_router)
app.include_router(data_router)
app.include_router(ux_router)
app.include_router(scope_router)
app.include_router(persona_router)
