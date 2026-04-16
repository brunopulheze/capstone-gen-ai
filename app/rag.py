"""
RAG Pipeline — BrixoAI Capstone
================================

RAG (Retrieval-Augmented Generation) makes the chatbot ground its answers in
real studio knowledge rather than relying on the LLM's general training data.

Pipeline stages (run once at startup):
1. LOAD   — Read every .md file from data/ via LangChain DirectoryLoader.
2. SPLIT  — Chunk documents into ~500-char overlapping segments.
3. EMBED  — Convert each chunk to a 384-dim vector via all-MiniLM-L6-v2.
4. INDEX  — Store vectors in a persistent ChromaDB vector store.

At query time (every chat request):
5. QUERY  — Embed the user's message and run cosine similarity search.
6. INJECT — Prepend top-k chunks as context before the LLM prompt.
"""

import os
from pathlib import Path

from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEndpointEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

# ── Paths ─────────────────────────────────────────────────────────────────────
DATA_DIR   = Path(__file__).parent.parent / "data"
CHROMA_DIR = Path(__file__).parent.parent / "chroma_db"

EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def build_retriever(k: int = 4):
    """
    Build and return a LangChain retriever backed by a persistent ChromaDB store.

    Args:
        k: Number of document chunks to return per query (default 4).

    Returns:
        LangChain VectorStoreRetriever (MMR search, diversity-aware).
    """
    # ── STEP 1: Load ──────────────────────────────────────────────────────────
    loader = DirectoryLoader(
        str(DATA_DIR),
        glob="**/*.md",
        loader_cls=TextLoader,
        loader_kwargs={"encoding": "utf-8"},
        show_progress=False,
    )
    documents = loader.load()

    # ── STEP 2: Split ─────────────────────────────────────────────────────────
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=60,
        separators=["\n\n", "\n", ". ", " "],
    )
    chunks = splitter.split_documents(documents)

    # ── STEP 3: Embed ─────────────────────────────────────────────────────────
    hf_token = os.getenv("HF_TOKEN") or None
    embeddings = HuggingFaceEndpointEmbeddings(
        model=EMBED_MODEL,
        **({"huggingfacehub_api_token": hf_token} if hf_token else {}),
    )

    # ── STEP 4: Index (load from disk if already built) ───────────────────────
    if CHROMA_DIR.exists() and any(CHROMA_DIR.iterdir()):
        print("RAG >> Loading existing ChromaDB from disk …")
        vectorstore = Chroma(
            persist_directory=str(CHROMA_DIR),
            embedding_function=embeddings,
        )
    else:
        print("RAG >> Building ChromaDB from documents (first run) …")
        vectorstore = Chroma.from_documents(
            documents=chunks,
            embedding=embeddings,
            persist_directory=str(CHROMA_DIR),
        )

    # ── STEP 5+6: Return a diversity-aware retriever ──────────────────────────
    # MMR (Maximum Marginal Relevance) returns chunks that are relevant AND
    # diverse — avoids returning near-duplicate paragraphs from the same file.
    return vectorstore.as_retriever(
        search_type="mmr",
        search_kwargs={"k": k, "fetch_k": k * 3},
    )
