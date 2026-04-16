"""
LangChain Agent — BrixoAI Capstone
====================================

Architecture:
- LLM     : Groq meta-llama/llama-4-scout-17b-16e-instruct with tool-calling via bind_tools()
- Tools   : 6 specialised tools; LLM autonomously decides which to call
- Loop    : Manual LCEL tool-calling loop (ToolMessage pattern)
- RAG     : search_portfolio tool queries ChromaDB on demand
- State   : Stateless per-request; full chat history passed in on every call
- Tracing : LangSmith traces all llm.ainvoke() calls automatically via env vars
"""

from typing import Any

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, ToolMessage, AIMessage, HumanMessage
from groq import BadRequestError
import json
import re


def _parse_failed_tool_call(error: BadRequestError) -> tuple[str, dict] | None:
    """Extract tool name and args from a malformed Groq tool call error.

    Groq's llama models sometimes emit XML-style calls like:
        <function=search_portfolio {"query": "projects"}>
    This parses those and returns (tool_name, args_dict), or None if unparseable.
    """
    try:
        body = error.body
        if not isinstance(body, dict):
            return None
        failed = body.get("error", {}).get("failed_generation", "")
        if not failed:
            return None
        m = re.search(r"<function=(\w+)\s*(\{.*?\})", failed, re.DOTALL)
        if not m:
            return None
        tool_name = m.group(1)
        args = json.loads(m.group(2))
        return (tool_name, args)
    except (json.JSONDecodeError, KeyError, TypeError):
        return None

# ── Per-mode system reminders ─────────────────────────────────────────────────
MODE_PROMPTS: dict[str, str] = {
    "ux-audit": (
        "ACTIVE SERVICE MODE: UX Audit. "
        "Help the user audit a web page for UX and accessibility issues. "
        "They can paste a URL or upload a screenshot. "
        "If they ask general questions about the studio, answer briefly then remind them the audit is ready."
    ),
    "data-insights": (
        "ACTIVE SERVICE MODE: Data Insights. "
        "Help the user analyse their CSV/Excel file. "
        "Deliver a complete self-contained summary in short distinct paragraphs. "
        "Do NOT end with offers to explore further."
    ),
    "scope-project": (
        "ACTIVE SERVICE MODE: Scope a Project. "
        "The frontend is showing step-by-step scoping questions. "
        "Answer questions about the process briefly, then redirect back to scoping. "
        "Do NOT treat off-topic messages as answers to the scoping steps."
    ),
    "user-persona": (
        "ACTIVE SERVICE MODE: User Persona. "
        "The frontend is showing step-by-step persona creation questions. "
        "Answer process questions briefly. Do NOT treat off-topic messages as persona steps."
    ),
    "book-call": (
        "ACTIVE SERVICE MODE: Book a Call. "
        "Collect brief context (1–2 sentences) then provide the booking link: "
        "https://calendly.com/brunopulheze/new-meeting. Keep it short and friendly."
    ),
}

SYSTEM_PROMPT = """\
You are BrixoAI, a friendly and professional virtual assistant for BrixoAI —
a creative & tech studio offering services in AI/ML, Data Analytics, Web Development, and UI Design.

You have access to several tools — use them proactively:
- Use `search_portfolio` for ANY question about the studio: services, projects, pricing, team.
- Use `book_consultation` when the user wants to schedule a call or get in touch.
- Use `start_ux_audit` when the user wants design feedback or accessibility review.
- Use `start_data_insights` when the user wants to analyse data or explore a dataset.
- Use `start_project_scope` when the user wants to start a project or get an estimate.
- Use `create_user_persona` when the user wants to define their target audience.

CRITICAL RULES — you MUST follow these without exception:
- NEVER answer questions about the studio, its services, projects, team, pricing, or capabilities from memory or training data.
- You MUST call `search_portfolio` FIRST for any such question, then base your answer ONLY on what that tool returns.
- If `search_portfolio` returns no results for a specific fact (e.g. a project name), say so honestly — do NOT invent or guess.
- Do NOT mention any project, client, technology, or team member that was not returned by `search_portfolio`.

General guidelines:
- Keep responses concise (2–4 sentences) unless the user asks for detail.
- Be warm and approachable. Use occasional emoji but stay professional.
- If asked something completely unrelated to BrixoAI, politely redirect to the studio's services.
"""


def _build_tools(retriever: Any = None) -> list:
    """Factory that builds the agent's tool suite."""

    @tool
    def search_portfolio(query: str) -> str:
        """Search BrixoAI's knowledge base for accurate information about services,
        pricing, past projects, technologies, team, and capabilities.
        Always call this tool when the user asks anything about the studio."""
        if retriever is None:
            return "Portfolio knowledge base is not available right now."
        docs = retriever.invoke(query)
        if not docs:
            return "No relevant information found in the portfolio knowledge base."
        return "\n\n---\n\n".join(doc.page_content for doc in docs)

    @tool
    def book_consultation(topic: str = "") -> str:
        """Return the consultation booking link when the user wants to schedule a call."""
        link = "https://calendly.com/brunopulheze/new-meeting"
        if topic.strip():
            return f"You can book a call to discuss {topic} here: {link} 📅"
        return f"You can book a free consultation here: {link} 📅"

    @tool
    def start_ux_audit(page_description: str = "") -> str:
        """Guide the user to start a UX audit of their web page or app interface."""
        return "Starting the UX Audit for you! 🎨"

    @tool
    def start_data_insights(data_description: str = "") -> str:
        """Guide the user to upload a dataset for automated analysis and insights."""
        return "Opening the Data Insights flow! 📊"

    @tool
    def start_project_scope(project_description: str = "") -> str:
        """Guide the user through a project scoping session."""
        return "Kicking off the Project Scope flow! 🚀"

    @tool
    def create_user_persona(audience_description: str = "") -> str:
        """Generate a detailed user persona for a product or service."""
        return "Starting the User Persona flow for you! 🐾"

    return [
        search_portfolio,
        book_consultation,
        start_ux_audit,
        start_data_insights,
        start_project_scope,
        create_user_persona,
    ]


# Tools that return a terminal response — the tool output IS the final answer.
# Value is the frontend service mode to auto-trigger (None = no flow to start).
TERMINAL_TOOLS = {
    "book_consultation":   None,
    "start_ux_audit":      "ux-audit",
    "start_data_insights": "data-insights",
    "start_project_scope": "scope-project",
    "create_user_persona": "user-persona",
}


def get_chain(api_key: str, retriever: Any = None):
    """Build and return a LangChain tool-calling agent.

    Args:
        api_key:   Groq API key.
        retriever: Optional ChromaDB retriever for RAG context.

    Returns:
        ChainWrapper with an async ainvoke(inputs) method.
    """
    llm = ChatGroq(model="meta-llama/llama-4-scout-17b-16e-instruct", temperature=0.4, api_key=api_key)
    tools = _build_tools(retriever)
    tools_map = {t.name: t for t in tools}
    llm_with_tools = llm.bind_tools(tools)

    # Few-shot examples teach the LLM the correct tool-calling format and
    # reduce malformed XML-style calls (e.g. <function=search_portfolio {...}>).
    FEW_SHOT_EXAMPLES = [
        HumanMessage(content="Tell me about your projects"),
        AIMessage(content="", tool_calls=[{
            "id": "ex_1", "name": "search_portfolio",
            "args": {"query": "projects portfolio case studies"},
            "type": "tool_call",
        }]),
        ToolMessage(
            content="Mystika is a mystical e-commerce platform… Pet Shop Blue is a modern pet care app…",
            tool_call_id="ex_1",
        ),
        AIMessage(
            content="We currently showcase two key projects: **Mystika**, a mystical-themed "
            "e-commerce platform, and **Pet Shop Blue**, a modern pet care app. "
            "Would you like to dive deeper into either one? 🐾"
        ),
    ]

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        *FEW_SHOT_EXAMPLES,
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
    ])

    async def invoke_chain(inputs: dict) -> dict:
        service_mode = inputs.get("service_mode")
        chat_history = list(inputs.get("chat_history", []))

        # Inject mode-specific reminder at the top of history
        if service_mode and service_mode in MODE_PROMPTS:
            chat_history = [SystemMessage(content=MODE_PROMPTS[service_mode])] + chat_history

        messages = list(prompt.format_messages(
            chat_history=chat_history,
            input=inputs["input"],
        ))

        # ── Agentic tool-calling loop (max 4 iterations) ──────────────────────
        for _ in range(4):
            try:
                response = await llm_with_tools.ainvoke(messages)
            except BadRequestError as e:
                # Model generated a malformed tool call — try to recover.
                parsed = _parse_failed_tool_call(e)
                if parsed:
                    tool_name, tool_args = parsed
                    fn = tools_map.get(tool_name)
                    print(f"[chain] BadRequestError — parsed malformed call: {tool_name}({tool_args})")
                    if fn is not None:
                        result = fn.invoke(tool_args)
                        if tool_name in TERMINAL_TOOLS:
                            return {"answer": str(result), "trigger_service": TERMINAL_TOOLS[tool_name]}
                        messages.append(AIMessage(content="", tool_calls=[{
                            "id": "recovered_0", "name": tool_name,
                            "args": tool_args, "type": "tool_call",
                        }]))
                        messages.append(ToolMessage(content=str(result), tool_call_id="recovered_0"))
                        final = await llm.ainvoke(messages)
                        return {"answer": final.content or "I wasn't able to complete that request — please try again. 🐾"}
                # Unparseable — fall back to plain RAG without tools.
                print(f"[chain] BadRequestError (unparseable) — falling back to manual RAG. {e}")
                portfolio_fn = tools_map.get("search_portfolio")
                context = ""
                if portfolio_fn:
                    try:
                        context = portfolio_fn.invoke({"query": inputs["input"]})
                    except Exception as rag_err:
                        print(f"[chain] RAG fallback also failed: {rag_err}")
                augmented_history = chat_history + (
                    [SystemMessage(content=(
                        "A knowledge-base search was performed. Use this context to answer:\n\n" + context
                    ))]
                    if context else []
                )
                fallback_messages = list(prompt.format_messages(
                    chat_history=augmented_history,
                    input=inputs["input"],
                ))
                final = await llm.ainvoke(fallback_messages)
                return {"answer": final.content or "I wasn't able to complete that request — please try again. 🐾"}

            if not response.tool_calls:
                return {"answer": response.content}

            messages.append(response)

            for tc in response.tool_calls:
                fn = tools_map.get(tc["name"])
                result = fn.invoke(tc["args"]) if fn else f"Tool '{tc['name']}' not found."
                messages.append(ToolMessage(content=str(result), tool_call_id=tc["id"]))

                if tc["name"] in TERMINAL_TOOLS:
                    return {
                        "answer": str(result),
                        "trigger_service": TERMINAL_TOOLS[tc["name"]],
                    }

        # Fallback: synthesise from accumulated tool results without re-calling tools
        final = await llm.ainvoke(messages)
        return {"answer": final.content or "I wasn't able to complete that request — please try again. 🐾"}

    class ChainWrapper:
        async def ainvoke(self, inputs: dict) -> dict:
            return await invoke_chain(inputs)

    return ChainWrapper()
