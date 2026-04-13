# LangChain Tool-Calling Agent

**Notebook:** `notebooks/02_langchain_agent.ipynb`  
**Production module:** `app/chain.py`

## What is the Agent?

The agent is the decision-making layer that sits between the user and the LLM. Rather than passing every message directly to the LLM for a plain text reply, the agent can **invoke tools** — calling specific functions to retrieve information, trigger services, or perform actions. The LLM decides autonomously which tool to call (if any) based on the user's intent.

## Architecture

```
User message
     │
     ▼
Build prompt:
  [System prompt]
  [Optional mode reminder (SystemMessage)]
  [Optional project context (SystemMessage)]
  [Chat history (HumanMessage / AIMessage)]
  [Current user message (HumanMessage)]
     │
     ▼
Groq LLM (llama-4-scout-17b-16e-instruct) with bound tools
     │
     ├── response.tool_calls present?
     │        │
     │        ▼
     │   Execute each tool locally
     │   Append AIMessage + ToolMessage to conversation
     │        │
     │        ├── Terminal tool? ──► return immediately
     │        │   (trigger_service set for frontend)
     │        │
     │        └── Non-terminal? ──► loop back to LLM (max 4 iterations)
     │
     └── No tool_calls ──► return response.content as final answer
          │
          ▼ (fallback after max iterations)
     Final LLM call without tools to synthesise accumulated results
```

## Tools

The agent has 6 tools registered via LangChain's `@tool` decorator and bound to the LLM using `.bind_tools()`.

| Tool | Description | Terminal? |
|---|---|---|
| `search_portfolio` | Queries ChromaDB with the user's question and returns relevant knowledge base chunks | No — LLM reads result and continues |
| `book_consultation` | Returns the Calendly booking link | Yes — result is the final answer |
| `start_ux_audit` | Signals the frontend to open the UX Audit panel | Yes — triggers `ux-audit` mode |
| `start_data_insights` | Signals the frontend to open the Data Insights panel | Yes — triggers `data-insights` mode |
| `start_project_scope` | Signals the frontend to open the Scope Project panel | Yes — triggers `scope-project` mode |
| `create_user_persona` | Signals the frontend to open the User Persona panel | Yes — triggers `user-persona` mode |

### Terminal vs. Non-Terminal Tools

- **Non-terminal** (`search_portfolio`): The tool result is appended to the conversation as a `ToolMessage`, and the LLM gets another turn to formulate a grounded answer using that context.
- **Terminal** (all others): The tool result IS the final answer. The agentic loop exits immediately and sets `trigger_service` so the Streamlit frontend can auto-switch to the relevant panel.

## Prompt Construction

Every request builds a fresh message list:

```
1. System prompt (SYSTEM_PROMPT constant)
   → Defines the BrixoAI assistant persona and tool usage rules

2. [Optional] Mode reminder (SystemMessage)
   → Injected if service_mode is set (e.g. "ux-audit", "data-insights")
   → Keeps the LLM focused on the active service context

3. [Optional] Project context (SystemMessage)
   → Serialised AI reports if the user has saved scope/persona/audit data
   → Allows the LLM to answer questions about their specific project

4. Chat history (HumanMessage / AIMessage alternating)
   → Full conversation passed in on every request (stateless design)

5. Current user message (HumanMessage)
```

## Agentic Loop

```python
for iteration in range(4):            # max 4 iterations
    response = await llm.ainvoke(messages)

    if not response.tool_calls:
        return {"answer": response.content}   # done

    for tc in response.tool_calls:
        result = tool_map[tc["name"]].invoke(tc["args"])
        messages += [response, ToolMessage(result, tool_call_id=tc["id"])]

        if tc["name"] in TERMINAL_TOOLS:
            return {"answer": result, "trigger_service": ...}

# Fallback after max iterations
final = await llm.ainvoke(messages)   # synthesise without tool-calling
```

The loop is capped at **4 iterations** to prevent runaway chains. In practice, most requests complete in 1–2 iterations:
- General question → 1 iteration (no tool call)
- Studio question → 2 iterations (`search_portfolio` + answer)
- Service trigger → 1 iteration (terminal tool)

## Service Mode System

When the frontend is showing a specific panel, it passes `service_mode` with every `/chat` request. The agent injects a `SystemMessage` reminder at the top of the history to keep the LLM contextually aware:

| `service_mode` | Effect |
|---|---|
| `"ux-audit"` | Reminds LLM it's helping with a UX audit |
| `"data-insights"` | Directs LLM to deliver complete data summaries |
| `"scope-project"` | Prevents off-topic messages from being treated as scoping answers |
| `"user-persona"` | Same boundary enforcement for persona creation |
| `"book-call"` | Directs LLM to collect context and return booking link |

## RAG Integration

The `search_portfolio` tool is the bridge between the agent and the RAG pipeline. When called:

1. The user's query is passed to `retriever.invoke(query)`
2. ChromaDB returns the top-k most relevant knowledge base chunks (MMR)
3. Chunks are joined with `---` separators and returned as the tool result
4. The LLM receives this grounded context as a `ToolMessage` and uses it to formulate its answer

If the retriever is unavailable (e.g. ChromaDB not yet built), the tool returns a graceful fallback message.

## Stateless Design

The agent holds **no session state**. Every request receives the full conversation history as a parameter. This makes the agent:
- Horizontally scalable (any server instance can handle any request)
- Simple to reason about (no hidden state mutations)
- Easy to test (each call is a pure function of its inputs)

## Technology

| Component | Library / Model |
|---|---|
| LLM | Groq `meta-llama/llama-4-scout-17b-16e-instruct` |
| Tool binding | LangChain `ChatGroq.bind_tools()` |
| Prompt templating | `ChatPromptTemplate` + `MessagesPlaceholder` |
| Tool definitions | LangChain `@tool` decorator |
| RAG retriever | ChromaDB via `app/rag.py` |
| Tracing | LangSmith (automatic via env vars) |
