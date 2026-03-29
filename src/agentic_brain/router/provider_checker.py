# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Provider availability checker for foolproof LLM setup.

Detects which LLM providers are available and provides helpful setup guidance.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from dataclasses import dataclass

import aiohttp

from .config import Provider

logger = logging.getLogger(__name__)


@dataclass
class ProviderStatus:
    """Status of an LLM provider."""

    provider: Provider
    available: bool
    reason: str = ""


class ProviderChecker:
    """Check which LLM providers are available."""

    @staticmethod
    def check_ollama() -> ProviderStatus:
        """Check if Ollama is available.

        Returns:
            ProviderStatus with availability and reason
        """
        # Check if ollama command exists
        if not shutil.which("ollama"):
            return ProviderStatus(
                provider=Provider.OLLAMA,
                available=False,
                reason="Ollama command not found in PATH",
            )

        # Try to connect to Ollama API
        try:
            import urllib.error
            import urllib.request

            response = urllib.request.urlopen(
                "http://localhost:11434/api/tags", timeout=2
            )
            if response.status == 200:
                return ProviderStatus(
                    provider=Provider.OLLAMA,
                    available=True,
                    reason="Ollama is running at http://localhost:11434",
                )
        except (urllib.error.URLError, urllib.error.HTTPError, Exception) as e:
            return ProviderStatus(
                provider=Provider.OLLAMA,
                available=False,
                reason=f"Ollama not running: {str(e)[:50]}",
            )

        return ProviderStatus(
            provider=Provider.OLLAMA,
            available=False,
            reason="Ollama is installed but not running",
        )

    @staticmethod
    def check_openai() -> ProviderStatus:
        """Check if OpenAI is configured.

        Returns:
            ProviderStatus with availability and reason
        """
        key = os.getenv("OPENAI_API_KEY", "").strip()
        if key and len(key) > 10:  # Basic validation
            return ProviderStatus(
                provider=Provider.OPENAI,
                available=True,
                reason="OPENAI_API_KEY is set",
            )

        return ProviderStatus(
            provider=Provider.OPENAI,
            available=False,
            reason="OPENAI_API_KEY not set in environment",
        )

    @staticmethod
    def check_azure_openai() -> ProviderStatus:
        """Check if Azure OpenAI is configured.

        Returns:
            ProviderStatus with availability and reason
        """
        key = os.getenv("AZURE_OPENAI_API_KEY", "").strip()
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").strip()
        deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "").strip()
        if key and endpoint and deployment:
            return ProviderStatus(
                provider=Provider.AZURE_OPENAI,
                available=True,
                reason="AZURE_OPENAI_API_KEY/ENDPOINT/DEPLOYMENT set",
            )

        missing = []
        if not key:
            missing.append("AZURE_OPENAI_API_KEY")
        if not endpoint:
            missing.append("AZURE_OPENAI_ENDPOINT")
        if not deployment:
            missing.append("AZURE_OPENAI_DEPLOYMENT")
        reason = "Missing " + ", ".join(missing) if missing else "Missing config"

        return ProviderStatus(
            provider=Provider.AZURE_OPENAI,
            available=False,
            reason=reason,
        )

    @staticmethod
    def check_anthropic() -> ProviderStatus:
        """Check if Anthropic is configured.

        Returns:
            ProviderStatus with availability and reason
        """
        key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        if key and len(key) > 10:  # Basic validation
            return ProviderStatus(
                provider=Provider.ANTHROPIC,
                available=True,
                reason="ANTHROPIC_API_KEY is set",
            )

        return ProviderStatus(
            provider=Provider.ANTHROPIC,
            available=False,
            reason="ANTHROPIC_API_KEY not set in environment",
        )

    @staticmethod
    def check_openrouter() -> ProviderStatus:
        """Check if OpenRouter is configured.

        Returns:
            ProviderStatus with availability and reason
        """
        key = os.getenv("OPENROUTER_API_KEY", "").strip()
        if key and len(key) > 10:  # Basic validation
            return ProviderStatus(
                provider=Provider.OPENROUTER,
                available=True,
                reason="OPENROUTER_API_KEY is set",
            )

        return ProviderStatus(
            provider=Provider.OPENROUTER,
            available=False,
            reason="OPENROUTER_API_KEY not set in environment",
        )

    @staticmethod
    def check_groq() -> ProviderStatus:
        """Check if Groq is configured.

        Returns:
            ProviderStatus with availability and reason
        """
        key = os.getenv("GROQ_API_KEY", "").strip()
        if key and len(key) > 10:  # Basic validation
            return ProviderStatus(
                provider=Provider.GROQ,
                available=True,
                reason="GROQ_API_KEY is set",
            )

        return ProviderStatus(
            provider=Provider.GROQ,
            available=False,
            reason="GROQ_API_KEY not set in environment",
        )

    @staticmethod
    def check_together() -> ProviderStatus:
        """Check if Together is configured.

        Returns:
            ProviderStatus with availability and reason
        """
        key = os.getenv("TOGETHER_API_KEY", "").strip()
        if key and len(key) > 10:  # Basic validation
            return ProviderStatus(
                provider=Provider.TOGETHER,
                available=True,
                reason="TOGETHER_API_KEY is set",
            )

        return ProviderStatus(
            provider=Provider.TOGETHER,
            available=False,
            reason="TOGETHER_API_KEY not set in environment",
        )

    @staticmethod
    def check_google() -> ProviderStatus:
        """Check if Google AI Studio is configured.

        Returns:
            ProviderStatus with availability and reason
        """
        key = os.getenv("GOOGLE_API_KEY", "").strip()
        if key and len(key) > 10:  # Basic validation
            return ProviderStatus(
                provider=Provider.GOOGLE,
                available=True,
                reason="GOOGLE_API_KEY is set",
            )

        return ProviderStatus(
            provider=Provider.GOOGLE,
            available=False,
            reason="GOOGLE_API_KEY not set in environment",
        )

    @staticmethod
    def check_xai() -> ProviderStatus:
        """Check if xAI Grok is configured.

        Returns:
            ProviderStatus with availability and reason
        """
        key = os.getenv("XAI_API_KEY", "").strip()
        if key and len(key) > 10:  # Basic validation
            return ProviderStatus(
                provider=Provider.XAI,
                available=True,
                reason="XAI_API_KEY is set",
            )

        return ProviderStatus(
            provider=Provider.XAI,
            available=False,
            reason="XAI_API_KEY not set in environment",
        )

    @classmethod
    def check_all(cls) -> dict[str, ProviderStatus]:
        """Check all providers.

        Returns:
            Dict with provider names as keys and ProviderStatus as values
        """
        return {
            "ollama": cls.check_ollama(),
            "openai": cls.check_openai(),
            "azure_openai": cls.check_azure_openai(),
            "anthropic": cls.check_anthropic(),
            "openrouter": cls.check_openrouter(),
            "groq": cls.check_groq(),
            "together": cls.check_together(),
            "google": cls.check_google(),
            "xai": cls.check_xai(),
        }

    @classmethod
    def get_available_providers(cls) -> list[Provider]:
        """Get list of available providers.

        Returns:
            List of Provider enums that are available
        """
        status_dict = cls.check_all()
        return [status.provider for status in status_dict.values() if status.available]

    @classmethod
    def has_any_provider(cls) -> bool:
        """Check if at least one provider is available.

        Returns:
            True if any provider is configured and available
        """
        return len(cls.get_available_providers()) > 0


def get_setup_help(provider: str) -> str:
    """Get detailed setup help for a specific provider.

    Args:
        provider: Provider name (ollama, groq, openai, etc.)

    Returns:
        Formatted setup instructions
    """
    help_text = {
        "groq": """
╔════════════════════════════════════════════════════════════════╗
║  ⭐ GROQ SETUP (Recommended - FREE & FAST)                      ║
╠════════════════════════════════════════════════════════════════╣
║                                                                ║
║  1. Go to: https://console.groq.com                            ║
║  2. Sign up (free account required)                            ║
║  3. Go to Settings > API Keys                                  ║
║  4. Create new API key (starts with gsk_)                      ║
║  5. Copy the key and add to .env:                              ║
║     GROQ_API_KEY=gsk_your_key_here                             ║
║  6. Save and restart: agentic serve                            ║
║                                                                ║
║  Models available: mixtral-8x7b, llama2-70b                    ║
║  Rate limit: 30 requests per minute (free)                     ║
║  Speed: ~100ms for typical responses                           ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
""",
        "ollama": """
╔════════════════════════════════════════════════════════════════╗
║  🖥️  OLLAMA SETUP (Local, No Internet Needed)                  ║
╠════════════════════════════════════════════════════════════════╣
║                                                                ║
║  1. Download: https://ollama.ai/download                       ║
║  2. Install and launch Ollama                                  ║
║  3. Open terminal and run:                                     ║
║     ollama pull llama2                                         ║
║  4. Start server:                                              ║
║     ollama serve                                               ║
║  5. Update .env:                                               ║
║     OLLAMA_HOST=http://localhost:11434                         ║
║     DEFAULT_LLM_PROVIDER=ollama                                ║
║                                                                ║
║  Available models:                                             ║
║  - llama2 (7B, ~4GB) - Fast, good quality                      ║
║  - mistral (7B, ~5GB) - Better quality                         ║
║  - neural-chat (7B, ~4GB) - Good for chat                      ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
""",
        "openai": """
╔════════════════════════════════════════════════════════════════╗
║  🔑 OPENAI SETUP (Paid)                                         ║
╠════════════════════════════════════════════════════════════════╣
║                                                                ║
║  1. Go to: https://platform.openai.com/api-keys                ║
║  2. Create account or sign in                                  ║
║  3. Create new API key                                         ║
║  4. Copy key (starts with sk-) and add to .env:                ║
║     OPENAI_API_KEY=sk_your_key_here                            ║
║  5. Restart: agentic serve                                     ║
║                                                                ║
║  Models: gpt-4-turbo, gpt-3.5-turbo (recommended)              ║
║  Pricing: ~$0.01-0.03 per 1K tokens                            ║
║  Speed: ~1-2 seconds for typical responses                     ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
""",
        "azure_openai": """
╔════════════════════════════════════════════════════════════════╗
║  🟦 AZURE OPENAI SETUP (Enterprise)                            ║
╠════════════════════════════════════════════════════════════════╣
║                                                                ║
║  1. Create Azure OpenAI resource in Azure Portal               ║
║  2. Create a deployment (e.g., gpt-4o)                         ║
║  3. Copy endpoint and key                                      ║
║  4. Add to .env:                                               ║
║     AZURE_OPENAI_API_KEY=...                                   ║
║     AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com  ║
║     AZURE_OPENAI_DEPLOYMENT=gpt-4o                             ║
║     AZURE_OPENAI_API_VERSION=2024-02-15-preview                ║
║  5. Restart: agentic serve                                     ║
║                                                                ║
║  Models: gpt-4o, gpt-4-turbo, gpt-35-turbo (via deployment)     ║
║  Pricing: Azure OpenAI pricing                                 ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
""",
        "anthropic": """
╔════════════════════════════════════════════════════════════════╗
║  🧠 ANTHROPIC (CLAUDE) SETUP (Paid)                            ║
╠════════════════════════════════════════════════════════════════╣
║                                                                ║
║  1. Go to: https://console.anthropic.com/                      ║
║  2. Create account or sign in                                  ║
║  3. Create new API key                                         ║
║  4. Copy key and add to .env:                                  ║
║     ANTHROPIC_API_KEY=sk-ant_your_key_here                     ║
║  5. Restart: agentic serve                                     ║
║                                                                ║
║  Models: claude-3-sonnet (recommended), claude-3-opus          ║
║  Pricing: ~$0.003-0.015 per 1K tokens                          ║
║  Quality: Excellent reasoning and creativity                   ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
""",
        "google": """
╔════════════════════════════════════════════════════════════════╗
║  🔍 GOOGLE AI STUDIO SETUP (FREE Gemini)                       ║
╠════════════════════════════════════════════════════════════════╣
║                                                                ║
║  1. Go to: https://aistudio.google.com/apikey                  ║
║  2. Click "Get API Key"                                        ║
║  3. Create new project (if needed)                             ║
║  4. Copy API key and add to .env:                              ║
║     GOOGLE_API_KEY=AIza_your_key_here                          ║
║  5. Restart: agentic serve                                     ║
║                                                                ║
║  Models: gemini-pro, gemini-pro-vision (free tier)             ║
║  Limit: 60 requests/minute (free tier)                         ║
║  Speed: ~1-2 seconds for typical responses                     ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
""",
        "xai": """
╔════════════════════════════════════════════════════════════════╗
║  🤖 XAI GROK SETUP (Requires X Premium)                        ║
╠════════════════════════════════════════════════════════════════╣
║                                                                ║
║  1. Requires X (Twitter) Premium subscription                  ║
║  2. Go to: https://console.x.ai                                ║
║  3. Create API keys page                                       ║
║  4. Create new key                                             ║
║  5. Copy key and add to .env:                                  ║
║     XAI_API_KEY=xai_your_key_here                              ║
║  6. Restart: agentic serve                                     ║
║                                                                ║
║  Models: grok-beta, grok-2                                     ║
║  Quality: High - powerful reasoning model                      ║
║  Cost: Depends on X Premium plan                               ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
""",
    }
    return help_text.get(
        provider.lower(),
        f"No setup help available for provider: {provider}",
    )


def format_error_message(status_dict: dict[str, ProviderStatus]) -> str:
    """Format an error message showing which providers are missing.

    Args:
        status_dict: Dict from check_all()

    Returns:
        Formatted error message string
    """
    [s for s in status_dict.values() if s.available]
    unavailable = [s for s in status_dict.values() if not s.available]

    lines = []
    lines.append("")
    lines.append("╔══════════════════════════════════════════════════════════════════╗")
    lines.append(
        "║  ❌ NO LLM PROVIDER CONFIGURED                                    ║"
    )
    lines.append("╠══════════════════════════════════════════════════════════════════╣")
    lines.append("║  You need at least one LLM provider to use agentic-brain.       ║")
    lines.append("║                                                                  ║")
    lines.append("║  ⭐ QUICKEST FREE OPTIONS (2 minutes):                           ║")
    lines.append("║                                                                  ║")
    lines.append("║  1. Groq (FREE, FAST - Recommended):                             ║")
    lines.append("║     • Go to: https://console.groq.com                            ║")
    lines.append("║     • Create account, get API key                                ║")
    lines.append("║     • Add to .env: GROQ_API_KEY=gsk_...                          ║")
    lines.append("║                                                                  ║")
    lines.append("║  2. OpenRouter (FREE models available):                          ║")
    lines.append("║     • Go to: https://openrouter.ai                               ║")
    lines.append("║     • Get API key for free tier                                  ║")
    lines.append("║     • Add to .env: OPENROUTER_API_KEY=sk-or-...                  ║")
    lines.append("║                                                                  ║")
    lines.append("║  3. Google AI Studio (FREE, Gemini):                             ║")
    lines.append("║     • Go to: https://aistudio.google.com/apikey                  ║")
    lines.append("║     • Create API key (free tier available)                       ║")
    lines.append("║     • Add to .env: GOOGLE_API_KEY=AIza...                        ║")
    lines.append("║                                                                  ║")
    lines.append("║  4. Ollama (FREE, Local - No API needed):                        ║")
    lines.append("║     • Download: https://ollama.ai/download                       ║")
    lines.append("║     • Run: ollama pull llama3.2                                  ║")
    lines.append("║     • Run: ollama serve                                          ║")
    lines.append("║                                                                  ║")
    if unavailable:
        lines.append(
            "║  Currently checked:                                              ║"
        )
        for status in unavailable[:3]:  # Show first 3
            reason_short = status.reason[:46]
            lines.append(f"║  • {status.provider.value:12} - {reason_short:<46} ║")
    lines.append("╚══════════════════════════════════════════════════════════════════╝")
    lines.append("")

    return "\n".join(lines)


def format_provider_status_report(status_dict: dict[str, ProviderStatus]) -> str:
    """Format a status report of all providers.

    Args:
        status_dict: Dict from check_all()

    Returns:
        Formatted status report string
    """
    available = [s for s in status_dict.values() if s.available]
    unavailable = [s for s in status_dict.values() if not s.available]

    lines = []
    lines.append("")
    lines.append("╔══════════════════════════════════════════════════════════════════╗")
    lines.append("║  🔍 LLM PROVIDER STATUS CHECK                                    ║")
    lines.append("╠══════════════════════════════════════════════════════════════════╣")

    if available:
        lines.append(
            "║  ✓ AVAILABLE PROVIDERS:                                          ║"
        )
        for status in available:
            reason_short = status.reason[:48]
            lines.append(f"║    • {status.provider.value:12} {reason_short:<48} ║")
        lines.append(
            "║                                                                  ║"
        )

    if unavailable:
        lines.append(
            "║  ✗ UNAVAILABLE PROVIDERS:                                        ║"
        )
        for status in unavailable:
            reason_short = status.reason[:46]
            lines.append(f"║    • {status.provider.value:12} {reason_short:<46} ║")
        lines.append(
            "║                                                                  ║"
        )

    lines.append("║  📚 SETUP GUIDE:                                                 ║")
    lines.append("║                                                                  ║")

    # Groq setup (fastest, recommended)
    if not status_dict["groq"].available:
        lines.append(
            "║  GROQ (⭐ Recommended - FREE, FAST, 2 minutes):                  ║"
        )
        lines.append(
            "║    1. Go to: https://console.groq.com                           ║"
        )
        lines.append(
            "║    2. Create account and get API key                            ║"
        )
        lines.append(
            "║    3. Add to .env: GROQ_API_KEY=gsk_...                         ║"
        )
        lines.append(
            "║                                                                  ║"
        )

    # Ollama setup
    if not status_dict["ollama"].available:
        lines.append(
            "║  OLLAMA (FREE, Local, No internet needed):                      ║"
        )
        lines.append(
            "║    1. Download: https://ollama.ai/download                      ║"
        )
        lines.append(
            "║    2. Pull model: ollama pull llama3.2                          ║"
        )
        lines.append(
            "║    3. Start: ollama serve                                       ║"
        )
        lines.append(
            "║                                                                  ║"
        )

    # Google AI Studio setup
    if not status_dict["google"].available:
        lines.append(
            "║  GOOGLE AI STUDIO (FREE Gemini):                                ║"
        )
        lines.append(
            "║    1. Go to: https://aistudio.google.com/apikey                 ║"
        )
        lines.append(
            "║    2. Create API key (free tier available)                      ║"
        )
        lines.append(
            "║    3. Add to .env: GOOGLE_API_KEY=AIza...                       ║"
        )
        lines.append(
            "║                                                                  ║"
        )

    # OpenRouter setup
    if not status_dict["openrouter"].available:
        lines.append(
            "║  OPENROUTER (Free tier available):                              ║"
        )
        lines.append(
            "║    1. Get key: https://openrouter.ai/keys                       ║"
        )
        lines.append(
            "║    2. Add to .env: OPENROUTER_API_KEY=sk-or-...                 ║"
        )
        lines.append(
            "║                                                                  ║"
        )

    # Together.ai setup
    if not status_dict["together"].available:
        lines.append(
            "║  TOGETHER (FREE tier + $25 credit):                             ║"
        )
        lines.append(
            "║    1. Go to: https://www.together.ai/                           ║"
        )
        lines.append(
            "║    2. Create account and get API key                            ║"
        )
        lines.append(
            "║    3. Add to .env: TOGETHER_API_KEY=...                         ║"
        )
        lines.append(
            "║                                                                  ║"
        )

    # OpenAI setup
    if not status_dict["openai"].available:
        lines.append(
            "║  OPENAI (Cloud-based, Paid):                                    ║"
        )
        lines.append(
            "║    1. Get key: https://platform.openai.com/api-keys             ║"
        )
        lines.append(
            "║    2. Add to .env: OPENAI_API_KEY=sk-...                        ║"
        )
        lines.append(
            "║                                                                  ║"
        )

    # Azure OpenAI setup
    if not status_dict["azure_openai"].available:
        lines.append(
            "║  AZURE OPENAI (Enterprise):                                     ║"
        )
        lines.append(
            "║    1. Create Azure OpenAI resource + deployment                 ║"
        )
        lines.append(
            "║    2. Add to .env: AZURE_OPENAI_API_KEY=...                     ║"
        )
        lines.append(
            "║    3. Add: AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com ║"
        )
        lines.append(
            "║    4. Add: AZURE_OPENAI_DEPLOYMENT=gpt-4o                       ║"
        )
        lines.append(
            "║                                                                  ║"
        )

    # Anthropic setup
    if not status_dict["anthropic"].available:
        lines.append(
            "║  ANTHROPIC (Cloud-based, Paid):                                 ║"
        )
        lines.append(
            "║    1. Get key: https://console.anthropic.com/                   ║"
        )
        lines.append(
            "║    2. Add to .env: ANTHROPIC_API_KEY=sk-ant-...                 ║"
        )
        lines.append(
            "║                                                                  ║"
        )

    # xAI setup
    if not status_dict["xai"].available:
        lines.append(
            "║  XAI GROK (Requires X Premium):                                 ║"
        )
        lines.append(
            "║    1. Get key: https://console.x.ai                             ║"
        )
        lines.append(
            "║    2. Add to .env: XAI_API_KEY=xai-...                          ║"
        )
        lines.append(
            "║                                                                  ║"
        )

    lines.append("╚══════════════════════════════════════════════════════════════════╝")
    lines.append("")

    return "\n".join(lines)
