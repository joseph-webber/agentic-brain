# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber
#
# Licensed under the Apache License, Version 2.0 ("License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""
Worker implementations for SmartRouter.

Each worker encapsulates the HTTP contract for a single provider so that the
router can treat them uniformly while SmashMode determines how to coordinate
them.
"""

import os
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

try:
    import httpx
except ImportError:
    httpx = None


class BaseWorker(ABC):
    """Base class for all LLM workers."""

    name: str = "base"

    @abstractmethod
    async def execute(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Execute prompt and return result."""
        raise NotImplementedError

    def get_api_key(self, env_var: str) -> Optional[str]:
        """Get an API key from the environment."""
        return os.environ.get(env_var)


class OpenAIWorker(BaseWorker):
    """OpenAI GPT worker - best for complex code"""

    name = "openai"

    async def execute(
        self, prompt: str, model: str = "gpt-4o-mini", **kwargs
    ) -> Dict[str, Any]:
        key = self.get_api_key("OPENAI_API_KEY")
        if not key:
            return {"success": False, "error": "No OPENAI_API_KEY"}

        start = time.time()
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": kwargs.get("max_tokens", 500),
                },
            )
            elapsed = time.time() - start

            if r.status_code == 200:
                data = r.json()
                return {
                    "success": True,
                    "response": data["choices"][0]["message"]["content"],
                    "elapsed": elapsed,
                    "tokens": data.get("usage", {}).get("total_tokens", 0),
                    "status_code": r.status_code,
                }
            return {
                "success": False,
                "error": f"HTTP {r.status_code}",
                "elapsed": elapsed,
                "status_code": r.status_code,
            }


class AzureOpenAIWorker(BaseWorker):
    """Azure OpenAI worker - enterprise deployments"""

    name = "azure_openai"

    async def execute(
        self, prompt: str, model: str | None = None, **kwargs
    ) -> Dict[str, Any]:
        key = self.get_api_key("AZURE_OPENAI_API_KEY")
        endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
        deployment = model or os.environ.get("AZURE_OPENAI_DEPLOYMENT")
        api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
        if not key or not endpoint or not deployment:
            return {
                "success": False,
                "error": "Missing AZURE_OPENAI_API_KEY/ENDPOINT/DEPLOYMENT",
            }

        url = (
            f"{endpoint.rstrip('/')}/openai/deployments/{deployment}/chat/completions"
            f"?api-version={api_version}"
        )

        start = time.time()
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                url,
                headers={"api-key": key},
                json={
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": kwargs.get("max_tokens", 500),
                },
            )
            elapsed = time.time() - start

            if r.status_code == 200:
                data = r.json()
                return {
                    "success": True,
                    "response": data["choices"][0]["message"]["content"],
                    "elapsed": elapsed,
                    "tokens": data.get("usage", {}).get("total_tokens", 0),
                    "status_code": r.status_code,
                }
            return {
                "success": False,
                "error": f"HTTP {r.status_code}",
                "elapsed": elapsed,
                "status_code": r.status_code,
            }


class GroqWorker(BaseWorker):
    """Groq worker - THE FASTEST! 🚀"""

    name = "groq"

    async def execute(
        self, prompt: str, model: str = "llama-3.3-70b-versatile", **kwargs
    ) -> Dict[str, Any]:
        key = self.get_api_key("GROQ_API_KEY")
        if not key:
            return {"success": False, "error": "No GROQ_API_KEY"}

        start = time.time()
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": kwargs.get("max_tokens", 500),
                },
            )
            elapsed = time.time() - start

            if r.status_code == 200:
                data = r.json()
                return {
                    "success": True,
                    "response": data["choices"][0]["message"]["content"],
                    "elapsed": elapsed,
                    "tokens": data.get("usage", {}).get("total_tokens", 0),
                    "status_code": r.status_code,
                }
            return {
                "success": False,
                "error": f"HTTP {r.status_code}",
                "elapsed": elapsed,
                "status_code": r.status_code,
            }


class GeminiWorker(BaseWorker):
    """Gemini worker - FREE and fast!"""

    name = "gemini"

    async def execute(
        self, prompt: str, model: str = "gemini-2.0-flash", **kwargs
    ) -> Dict[str, Any]:
        key = self.get_api_key("GOOGLE_API_KEY") or self.get_api_key("GEMINI_API_KEY")
        if not key:
            return {"success": False, "error": "No GOOGLE_API_KEY or GEMINI_API_KEY"}

        start = time.time()
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}",
                json={"contents": [{"parts": [{"text": prompt}]}]},
            )
            elapsed = time.time() - start

            if r.status_code == 200:
                data = r.json()
                if "candidates" in data:
                    return {
                        "success": True,
                        "response": data["candidates"][0]["content"]["parts"][0][
                            "text"
                        ],
                        "elapsed": elapsed,
                        "status_code": r.status_code,
                    }
            return {
                "success": False,
                "error": f"HTTP {r.status_code}",
                "elapsed": elapsed,
                "status_code": r.status_code,
            }


class LocalWorker(BaseWorker):
    """Local Ollama worker - UNLIMITED! 🏠"""

    name = "local"

    async def execute(
        self, prompt: str, model: str = "llama3.1:8b", **kwargs
    ) -> Dict[str, Any]:
        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                r = await client.post(
                    "http://localhost:11434/api/generate",
                    json={"model": model, "prompt": prompt, "stream": False},
                )
                elapsed = time.time() - start

                if r.status_code == 200:
                    data = r.json()
                    return {
                        "success": True,
                        "response": data.get("response", ""),
                        "elapsed": elapsed,
                        "status_code": r.status_code,
                    }
                return {
                    "success": False,
                    "error": f"HTTP {r.status_code}",
                    "elapsed": elapsed,
                    "status_code": r.status_code,
                }
        except Exception as e:
            return {"success": False, "error": str(e), "elapsed": time.time() - start}


class TogetherWorker(BaseWorker):
    """Together.ai worker - free tier credits"""

    name = "together"

    async def execute(
        self,
        prompt: str,
        model: str = "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        **kwargs,
    ) -> Dict[str, Any]:
        key = self.get_api_key("TOGETHER_API_KEY")
        if not key:
            return {"success": False, "error": "No TOGETHER_API_KEY"}

        start = time.time()
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                "https://api.together.xyz/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": kwargs.get("max_tokens", 500),
                },
            )
            elapsed = time.time() - start

            if r.status_code == 200:
                data = r.json()
                return {
                    "success": True,
                    "response": data["choices"][0]["message"]["content"],
                    "elapsed": elapsed,
                    "tokens": data.get("usage", {}).get("total_tokens", 0),
                    "status_code": r.status_code,
                }
            return {
                "success": False,
                "error": f"HTTP {r.status_code}",
                "elapsed": elapsed,
                "status_code": r.status_code,
            }


class DeepSeekWorker(BaseWorker):
    """DeepSeek worker - free/cheap reasoning"""

    name = "deepseek"

    async def execute(
        self, prompt: str, model: str = "deepseek-chat", **kwargs
    ) -> Dict[str, Any]:
        key = self.get_api_key("DEEPSEEK_API_KEY")
        if not key:
            return {"success": False, "error": "No DEEPSEEK_API_KEY"}

        start = time.time()
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": kwargs.get("max_tokens", 500),
                },
            )
            elapsed = time.time() - start

            if r.status_code == 200:
                data = r.json()
                return {
                    "success": True,
                    "response": data["choices"][0]["message"]["content"],
                    "elapsed": elapsed,
                    "tokens": data.get("usage", {}).get("total_tokens", 0),
                    "status_code": r.status_code,
                }
            return {
                "success": False,
                "error": f"HTTP {r.status_code}",
                "elapsed": elapsed,
                "status_code": r.status_code,
            }


class OpenRouterWorker(BaseWorker):
    """OpenRouter worker - 50+ models with one key!"""

    name = "openrouter"

    async def execute(
        self,
        prompt: str,
        model: str = "meta-llama/llama-3.1-8b-instruct:free",
        **kwargs,
    ) -> Dict[str, Any]:
        key = self.get_api_key("OPENROUTER_API_KEY")
        if not key:
            return {"success": False, "error": "No OPENROUTER_API_KEY"}

        start = time.time()
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {key}",
                    "HTTP-Referer": "https://github.com/joseph-webber/agentic-brain",
                },
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            elapsed = time.time() - start

            if r.status_code == 200:
                data = r.json()
                return {
                    "success": True,
                    "response": data["choices"][0]["message"]["content"],
                    "elapsed": elapsed,
                    "status_code": r.status_code,
                }
            return {
                "success": False,
                "error": f"HTTP {r.status_code}",
                "elapsed": elapsed,
                "status_code": r.status_code,
            }


# Factory to get workers
WORKERS: Dict[str, type[BaseWorker]] = {
    "openai": OpenAIWorker,
    "azure_openai": AzureOpenAIWorker,
    "groq": GroqWorker,
    "gemini": GeminiWorker,
    "local": LocalWorker,
    "openrouter": OpenRouterWorker,
    "together": TogetherWorker,
    "deepseek": DeepSeekWorker,
}


def get_worker(name: str) -> BaseWorker:
    """Return a worker instance by name."""
    worker_class = WORKERS.get(name)
    if worker_class:
        return worker_class()
    raise ValueError(f"Unknown worker: {name}")


def get_all_workers() -> List[BaseWorker]:
    """Return new instances of every registered worker."""
    return [cls() for cls in WORKERS.values()]
