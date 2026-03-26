"""
🔥 SMART LLM ROUTER - MASTER/WORKER ARCHITECTURE 🔥

Claude is the MASTER THREAD - orchestrates, delegates, NEVER rate limited.
Other LLMs are WORKER THREADS - they do the heavy lifting.

Architecture:
    MASTER (Claude/Copilot) 
        │
        ├── Worker: OpenAI (gpt-4o) - Complex code
        ├── Worker: Groq (llama-3.3) - FASTEST responses  
        ├── Worker: Gemini (2.0-flash) - FREE, fast
        ├── Worker: DeepSeek (v3) - FREE credits
        ├── Worker: Together (llama-3.3) - FREE credits
        ├── Worker: Local Ollama - UNLIMITED
        └── Worker: OpenRouter (50+ models) - Fallback

Modes:
    - LUDICROUS: Fire ALL workers, fastest wins
    - CONSENSUS: Fire 3+, compare results
    - CASCADE: Try FREE first, fall back to paid
    - DEDICATED: Route to best worker for task type

Usage:
    from agentic_brain.smart_router import SmartRouter, ludicrous_smash
    
    router = SmartRouter()
    result = await router.route("code", "Write a function...")
    
    # Or fire all at once
    result = await ludicrous_smash("Say hi!")
"""

from .core import SmartRouter, SmashMode, SmashResult
from .workers import (
    AzureOpenAIWorker,
    DeepSeekWorker,
    GeminiWorker,
    GroqWorker,
    LocalWorker,
    OpenAIWorker,
    OpenRouterWorker,
    TogetherWorker,
)
from .coordinator import RedisCoordinator, ludicrous_smash, cascade_smash
from .posture import SecurityPosture, PostureMode

__all__ = [
    "SmartRouter",
    "SmashMode", 
    "SmashResult",
    "OpenAIWorker",
    "AzureOpenAIWorker",
    "GroqWorker",
    "GeminiWorker", 
    "LocalWorker",
    "OpenRouterWorker",
    "TogetherWorker",
    "DeepSeekWorker",
    "RedisCoordinator",
    "ludicrous_smash",
    "cascade_smash",
    "SecurityPosture",
    "PostureMode",
]
