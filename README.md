# BrixoAI — Generative AI Capstone

**Modular AI-powered design studio assistant built with LangChain, FastAPI, and Streamlit.**

This repository is the capstone deliverable for the Generative AI programme. It implements a
multimodal, agentic AI pipeline that serves as an intelligent front-desk assistant for a
digital design studio.

---

## Features

| Service | Capability | AI technique |
|---|---|---|
| 💬 Chat | General studio Q&A with RAG grounding | LangChain agent + ChromaDB RAG |
| 📊 Data Insights | Upload CSV/Excel → instant profiling + Q&A | Pandas + LLM analysis |
| 🎨 UX Audit | Analyse websites by URL or screenshot | Reflexion loop + Vision LLM |
| 💼 Scope Project | Brief → structured scope + brand palette | Contradiction detection + Tavily |
| 👤 User Persona | Generate research-grade UX personas | Structured JSON generation |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              Streamlit GUI  (streamlit_app.py)               │
└───────────────────────┬─────────────────────────────────────┘
                        │  HTTP (REST)
┌───────────────────────▼─────────────────────────────────────┐
│              FastAPI  (app/main.py)                          │
│                                                             │
│  /chat          → services/chat.py                          │
│  /upload        → services/data_insights.py                 │
│  /chat/data     → services/data_insights.py                 │
│  /ux-audit/*    → services/ux_audit.py                      │
│  /scope-project → services/scope_project.py                 │
│  /persona       → services/user_persona.py                  │
│  /generate-*    → services/brief.py                         │
└───────────────────────┬─────────────────────────────────────┘
                        │
             ┌──────────┼──────────┐
             ▼          ▼          ▼
          Groq LLM   ChromaDB   Tavily
       (llama-3.3)   (RAG)    (web search)
```

---

## Multimodal Inputs

The system accepts **four distinct input modalities**:

- **Text** — typed chat messages
- **Image** — website screenshots for visual UX audit
- **Tabular** — CSV / Excel files for data analysis

---

## Quick Start

### Prerequisites

- Python 3.11+
- API keys: Groq, Tavily (required); HuggingFace, LangSmith (optional)

### 1. Install

```bash
git clone https://github.com/your-org/capstone-gen-ai
cd capstone-gen-ai
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
```

### 2. Configure

```bash
copy .env.example .env        # Windows
# cp .env.example .env        # macOS/Linux
# Edit .env and fill in your API keys
```

### 3. Run FastAPI

```bash
uvicorn app.main:app --reload --port 8000
```

API docs available at: http://localhost:8000/docs

### 4. Run Streamlit UI

```bash
streamlit run app/streamlit_app.py
```

Opens at: http://localhost:8501

---

## Project Structure

```
capstone-gen-ai/
├── app/
│   ├── main.py               # FastAPI entrypoint
│   ├── config.py             # Settings & env vars
│   ├── rag.py                # RAG pipeline (ChromaDB + HF embeddings)
│   ├── chain.py              # LangChain tool-calling agent
│   ├── state.py              # Module-level singletons
│   ├── streamlit_app.py      # Streamlit GUI (all services)
│   └── services/
│       ├── chat.py           # General chat endpoint
│       ├── data_insights.py  # CSV/Excel analysis + Q&A
│       ├── ux_audit.py       # URL & image UX audit (Reflexion)
│       ├── scope_project.py  # Project scope + palette generation
│       ├── user_persona.py   # User persona generation
│       └── brief.py          # Brief & proposal generation
├── notebooks/
│   ├── 01_rag_pipeline.ipynb       # RAG: load → split → embed → index → query
│   ├── 02_langchain_agent.ipynb    # Tool-calling agent & agentic loop
│   ├── 03_data_insights.ipynb      # DataFrame profiling + LLM Q&A
│   ├── 04_ux_audit.ipynb           # URL scraping + vision + Reflexion loop
│   ├── 05_scope_project.ipynb      # Brief → scope → palette
│   └── 06_user_persona.ipynb       # Persona generation + gender enforcement
├── data/
│   ├── faq.md                # Studio FAQ (RAG knowledge source)
│   ├── projects.md           # Portfolio (RAG knowledge source)
│   ├── services.md           # Services (RAG knowledge source)
│   └── studio.md             # Studio info (RAG knowledge source)
├── deployment/
│   ├── Dockerfile            # Multi-stage Docker build
│   └── render.yaml           # Render.com deployment config
├── requirements.txt
├── .env.example
└── README.md
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| LLM | Groq `llama-3.3-70b-versatile` |
| Vision LLM | Groq `meta-llama/llama-4-scout-17b-16e-instruct` |
| Agent framework | LangChain tool-calling agents |
| Observability | LangSmith tracing |
| Vector DB | ChromaDB (persisted) |
| Embeddings | HuggingFace `all-MiniLM-L6-v2` |
| Web search | Tavily API |
| Backend | FastAPI + Uvicorn |
| Frontend | Streamlit |
| Data | Pandas, NumPy, OpenPyXL |

---

## Notebooks

Each notebook is self-contained and can be run independently.
Cells import directly from the `app/` source code where possible.

| Notebook | Topic | Key concepts |
|---|---|---|
| [01](notebooks/01_rag_pipeline.ipynb) | RAG Pipeline | Document loading, chunking, MMR retrieval |
| [02](notebooks/02_langchain_agent.ipynb) | LangChain Agent | Tool-calling, agentic loop, tool schemas |
| [03](notebooks/03_data_insights.ipynb) | Data Insights | Column profiling, correlation, LLM Q&A |
| [04](notebooks/04_ux_audit.ipynb) | UX Audit | Reflexion loop, vision LLM, web scraping |
| [05](notebooks/05_scope_project.ipynb) | Scope Project | Contradiction detection, Tavily, palette gen |
| [06](notebooks/06_user_persona.ipynb) | User Persona | Structured JSON, gender enforcement |

---

## API Endpoints

| Method | Path | Service |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/chat` | General chat |
| `POST` | `/upload` | Upload CSV/Excel |
| `POST` | `/chat/data` | Follow-up data Q&A |
| `POST` | `/ux-audit/url` | UX audit by URL |
| `POST` | `/ux-audit/image` | UX audit by image |
| `POST` | `/scope-project` | Scope a project |
| `POST` | `/regenerate-palette` | Regenerate brand palette |
| `POST` | `/persona` | Generate user persona |
| `POST` | `/generate-brief` | Generate project brief |
| `POST` | `/generate-proposal` | Generate client proposal |

Full interactive docs at `/docs` once the server is running.

---

## Deployment

### Docker

```bash
docker build -f deployment/Dockerfile -t brixoai-capstone .
docker run -p 8000:8000 --env-file .env brixoai-capstone
```

### Render.com

Push to GitHub, then import the repo in Render — the `deployment/render.yaml` file
configures both the FastAPI API and Streamlit services automatically.

---

## Licence

Academic project for the Generative AI Capstone. Not for commercial distribution.
