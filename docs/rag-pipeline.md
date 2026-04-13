# RAG Pipeline

**Notebook:** `notebooks/01_rag_pipeline.ipynb`  
**Production module:** `app/rag.py`

## What is RAG?

RAG (Retrieval-Augmented Generation) grounds the chatbot's answers in **real, curated studio knowledge** rather than relying on the LLM's general training data. Without RAG, the LLM can only guess at studio-specific facts like services, pricing, and past projects. With RAG, the correct information is retrieved from a local knowledge base and injected into the prompt before the LLM responds.

## Knowledge Base

The knowledge base is made up of four Markdown files in the `data/` folder:

| File | Content |
|---|---|
| `data/studio.md` | Studio overview, team, values, and culture |
| `data/services.md` | Full service catalogue with descriptions and pricing |
| `data/projects.md` | Past project case studies |
| `data/faq.md` | Frequently asked questions |

## Pipeline Architecture

The pipeline has two distinct phases: **indexing** (run once at startup) and **querying** (run on every chat request).

```
── INDEXING PHASE (startup) ────────────────────────────────────────

  data/*.md files
       │
       ▼
  Step 1 — LOAD
  DirectoryLoader reads all .md files via TextLoader (UTF-8)
       │
       ▼
  Step 2 — SPLIT
  RecursiveCharacterTextSplitter
  chunk_size=500 chars · overlap=60 chars
  separators: ["\n\n", "\n", ". ", " "]
       │
       ▼
  Step 3 — EMBED
  HuggingFace all-MiniLM-L6-v2
  384-dimensional dense vectors
       │
       ▼
  Step 4 — INDEX
  ChromaDB persistent vector store (saved to chroma_db/)
  ← Skipped on subsequent startups if chroma_db/ already exists

── QUERY PHASE (every chat request) ────────────────────────────────

  User message
       │
       ▼
  Step 5 — QUERY
  User message embedded with the same all-MiniLM-L6-v2 model
  MMR search: fetch k×3 candidates, return k most relevant & diverse
       │
       ▼
  Step 6 — INJECT
  Top-k chunks passed to search_portfolio tool as context string
  LLM generates grounded answer
```

## Step-by-Step Breakdown

### Step 1 — Load

`DirectoryLoader` scans `data/` for all `*.md` files and loads each one as a LangChain `Document` object. Each document carries the file content and metadata (source path).

### Step 2 — Split

`RecursiveCharacterTextSplitter` breaks each document into overlapping chunks:

| Parameter | Value | Reason |
|---|---|---|
| `chunk_size` | 500 chars | Fits comfortably within the embedding model's context window |
| `chunk_overlap` | 60 chars | Prevents answers from being cut off at chunk boundaries |
| `separators` | `["\n\n", "\n", ". ", " "]` | Prefers natural breaks (paragraphs → sentences → words) |

### Step 3 — Embed

Each chunk is converted to a 384-dimensional vector using `sentence-transformers/all-MiniLM-L6-v2` via HuggingFace. This lightweight model is fast, runs locally (no API cost), and produces high-quality semantic embeddings.

### Step 4 — Index

Vectors are stored in a **persistent ChromaDB** instance on disk (`chroma_db/`). On the first run, all chunks are embedded and written. On subsequent startups, the existing store is loaded directly — no re-embedding needed.

### Step 5 — Query

When the `search_portfolio` tool is called, the user's query is embedded with the same model, and ChromaDB runs a **cosine similarity search** to find the most semantically similar chunks.

### Step 6 — Inject (MMR)

The retriever uses **Maximum Marginal Relevance (MMR)** rather than plain similarity search:

- Fetches `k × 3` candidate chunks by similarity
- Selects the final `k` chunks that are both **relevant** and **diverse**
- This avoids returning near-duplicate paragraphs from the same document section

The retrieved chunks are concatenated with `---` separators and returned as the tool result, which the LLM uses as grounded context.

## Configuration

| Parameter | Default | Where set |
|---|---|---|
| `k` (chunks returned) | `4` | `build_retriever(k=4)` in `app/main.py` |
| `fetch_k` (MMR candidates) | `k × 3 = 12` | `search_kwargs` in `app/rag.py` |
| Embedding model | `all-MiniLM-L6-v2` | `EMBED_MODEL` constant in `app/rag.py` |
| Vector store path | `chroma_db/` | `CHROMA_DIR` in `app/rag.py` |
| Notebook store path | `chroma_db_nb/` | Used by the notebook only |

## Technology

| Component | Library |
|---|---|
| Document loading | `langchain-community` `DirectoryLoader` |
| Text splitting | `langchain-text-splitters` `RecursiveCharacterTextSplitter` |
| Embeddings | `langchain-huggingface` + `sentence-transformers/all-MiniLM-L6-v2` |
| Vector store | `langchain-chroma` + ChromaDB |
| Search strategy | MMR (Maximum Marginal Relevance) |
