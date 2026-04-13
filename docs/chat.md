# Chat Service

**Endpoint:** `POST /chat`

## Overview

The Chat service is the core conversational interface for BrixoAI. It routes every user message through a LangChain tool-calling agent backed by a Groq LLM. The agent decides autonomously whether to answer directly, query the knowledge base, or redirect the user to a specialist service.

## How It Works

```
User message
     │
     ▼
Menu / redirect intent check (keyword matching)
     │
     ▼
Build LangChain message history (HumanMessage / AIMessage)
     │
     ▼  optional
Inject project context as SystemMessage (if project_context provided)
     │
     ▼
LangChain Tool-Calling Agent (Groq LLM)
     │
     ├── tool_calls? ──► execute tool ──► append ToolMessage ──► loop (max 4 iterations)
     │
     └── No tool_calls ──► return AIMessage content
```

## Request Payload

| Field | Type | Required | Description |
|---|---|---|---|
| `message` | `string` | ✅ | The user's message |
| `history` | `list[dict]` | — | Previous turns `[{"role": "user"/"assistant", "content": "..."}]` |
| `service_mode` | `string` | — | Active service panel (e.g. `"ux-audit"`, `"data-insights"`) |
| `project_context` | `string` | — | Serialised AI reports to give the LLM full project awareness |

## Response Payload

| Field | Type | Description |
|---|---|---|
| `reply` | `string` | The assistant's text response |
| `show_menu` | `bool` | `true` if the user explicitly asked for the service menu |
| `show_menu_hint` | `bool` | `true` if the LLM reply looks like a redirect (e.g. "how can I help") |
| `trigger_service` | `string \| null` | Service mode to auto-open on the frontend |

## Intent Detection

Two keyword lists run on every request **before** the LLM is called:

- **Menu phrases** — e.g. `"show menu"`, `"what can you do"` → sets `show_menu: true`
- **Redirect phrases** — LLM reply patterns that suggest it couldn't help → sets `show_menu_hint: true` so the frontend can surface the menu

## Available Tools

| Tool | Trigger intent |
|---|---|
| `search_portfolio` | Questions about the studio, services, pricing, projects |
| `book_consultation` | "book a call", "schedule a meeting" |
| `start_ux_audit` | "audit my website", "design feedback" |
| `start_data_insights` | "analyse my data", "upload CSV" |
| `start_project_scope` | "scope a project", "I have an idea" |
| `create_user_persona` | "create a persona", "define my audience" |

## Technology

- **LLM:** Groq `meta-llama/llama-4-scout-17b-16e-instruct`
- **RAG:** ChromaDB retriever injected into the `search_portfolio` tool
- **Framework:** LangChain tool-calling loop (max 4 iterations)
