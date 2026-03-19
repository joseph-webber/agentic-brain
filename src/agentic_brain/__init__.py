"""
Agentic Brain - Lightweight AI Agent Framework
===============================================

A minimal, production-ready framework for building AI agents with:
- Persistent Neo4j memory
- Data separation (public/private/customer)
- LLM orchestration

Copyright (C) 2026 Joseph Webber
License: GPL-2.0-or-later

Example:
    >>> from agentic_brain import Agent, Neo4jMemory
    >>> memory = Neo4jMemory(uri="bolt://localhost:7687")
    >>> agent = Agent(name="assistant", memory=memory)
    >>> response = agent.chat("Hello!")
"""

__version__ = "0.1.0"
__author__ = "Joseph Webber"
__email__ = "joseph.webber@me.com"
__license__ = "GPL-2.0-or-later"

from agentic_brain.agent import Agent
from agentic_brain.memory import Neo4jMemory, DataScope
from agentic_brain.router import LLMRouter

__all__ = [
    "Agent",
    "Neo4jMemory",
    "DataScope",
    "LLMRouter",
    "__version__",
]
