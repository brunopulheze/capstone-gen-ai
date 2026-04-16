import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY   = os.getenv("GROQ_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
HF_TOKEN       = os.getenv("HF_TOKEN", "")

# ── LangSmith tracing ─────────────────────────────────────────────────────────
# Set LANGCHAIN_TRACING_V2=true in .env to enable LangSmith traces.
LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY", "")
LANGCHAIN_PROJECT = os.getenv("LANGCHAIN_PROJECT", "capstone-gen-ai")

if LANGCHAIN_API_KEY:
    os.environ.setdefault("LANGCHAIN_TRACING_V2", os.getenv("LANGCHAIN_TRACING_V2", "true"))
    os.environ["LANGCHAIN_API_KEY"] = LANGCHAIN_API_KEY
    os.environ["LANGCHAIN_PROJECT"] = LANGCHAIN_PROJECT

ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8501",  # Streamlit default port
    *[o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()],
]
