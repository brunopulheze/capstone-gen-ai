"""
Shared application state — holds the chain, LLM, and Tavily client instances
initialised during the FastAPI lifespan. Services import from here to access
the singleton objects without circular imports.
"""

chain        = None   # LangChain tool-calling agent (ChainWrapper)
llm_quick    = None   # Lightweight ChatGroq for short, tool-free calls
tavily_client = None  # TavilyClient for web search (None if key not set)
