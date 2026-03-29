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
Enhanced Agentic Brain Installer
=================================

Interactive, accessible installer with environment detection,
user profile setup, LLM configuration, and health checking.

Features:
- Environment detection (OS, Python, GPU, voices)
- Privacy-first user profile setup
- LLM configuration with fallback chain
- ADL initialization
- Comprehensive health checks
- Screen reader accessible
- Graceful error handling
"""

import argparse
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

__version__ = "2.0.0"


# ANSI colors - disabled automatically for accessibility
class Colors:
    """ANSI color codes - auto-disabled if terminal doesn't support color."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    BLUE = "\033[34m"

    @classmethod
    def disable(cls):
        """Disable all colors for accessibility."""
        cls.RESET = cls.BOLD = cls.CYAN = ""
        cls.GREEN = cls.YELLOW = cls.RED = cls.BLUE = ""


# Auto-disable colors if not supported or accessibility mode
if (
    not sys.stdout.isatty()
    or os.environ.get("NO_COLOR")
    or os.environ.get("TERM") == "dumb"
):
    Colors.disable()


# ============================================================================
# ENVIRONMENT DETECTION
# ============================================================================


def detect_os() -> Dict[str, Any]:
    """Detect operating system details."""
    system = platform.system()
    release = platform.release()
    version = platform.version()
    machine = platform.machine()

    os_info = {
        "system": system,
        "release": release,
        "version": version,
        "machine": machine,
        "is_macos": system == "Darwin",
        "is_linux": system == "Linux",
        "is_windows": system == "Windows",
    }

    # Detect Apple Silicon
    if os_info["is_macos"]:
        os_info["is_apple_silicon"] = machine in ["arm64", "aarch64"]

    return os_info


def detect_python() -> Dict[str, Any]:
    """Detect Python version and environment."""
    version_info = sys.version_info

    return {
        "version": f"{version_info.major}.{version_info.minor}.{version_info.micro}",
        "major": version_info.major,
        "minor": version_info.minor,
        "micro": version_info.micro,
        "executable": sys.executable,
        "is_virtualenv": hasattr(sys, "real_prefix")
        or (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix),
        "version_ok": version_info >= (3, 9),
    }


def detect_gpu() -> Dict[str, Any]:
    """Detect available GPU acceleration."""
    gpu_info: Dict[str, Any] = {
        "has_gpu": False,
        "type": None,
        "name": None,
        "can_accelerate": False,
    }

    # Check for Apple Silicon MPS
    try:
        import torch

        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            gpu_info["has_gpu"] = True
            gpu_info["type"] = "Apple Silicon"
            gpu_info["name"] = "Metal Performance Shaders (MPS)"
            gpu_info["can_accelerate"] = True
            return gpu_info
    except ImportError:
        pass

    # Check for NVIDIA CUDA
    try:
        import torch

        if torch.cuda.is_available():
            gpu_info["has_gpu"] = True
            gpu_info["type"] = "NVIDIA CUDA"
            gpu_info["name"] = torch.cuda.get_device_name(0)
            gpu_info["can_accelerate"] = True
            return gpu_info
    except (ImportError, RuntimeError):
        pass

    # Check for AMD ROCm (Linux only)
    if platform.system() == "Linux":
        try:
            result = subprocess.run(
                ["rocm-smi", "--showproductname"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                gpu_info["has_gpu"] = True
                gpu_info["type"] = "AMD ROCm"
                gpu_info["name"] = result.stdout.strip()
                gpu_info["can_accelerate"] = True
                return gpu_info
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    return gpu_info


def detect_voices() -> Dict[str, Any]:
    """Detect available text-to-speech voices (macOS say command)."""
    voices_info: Dict[str, Any] = {
        "has_tts": False,
        "system": None,
        "voices": [],
        "recommended": [],
    }

    os_type = platform.system()

    # macOS `say` command
    if os_type == "Darwin":
        try:
            result = subprocess.run(
                ["say", "-v", "?"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                voices_info["has_tts"] = True
                voices_info["system"] = "macOS say"

                # Parse voice list
                lines = result.stdout.strip().split("\n")
                for line in lines:
                    parts = line.split(maxsplit=1)
                    if len(parts) >= 1:
                        voice_name = parts[0]
                        voices_info["voices"].append(voice_name)

                # Recommended voices for accessibility
                recommended = [
                    "Samantha",
                    "Karen",
                    "Daniel",
                    "Alex",
                    "Kyoko",
                    "Tingting",
                ]
                voices_info["recommended"] = [
                    v for v in recommended if v in voices_info["voices"]
                ]
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    # Linux - espeak/festival
    elif os_type == "Linux":
        try:
            result = subprocess.run(
                ["espeak", "--voices"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                voices_info["has_tts"] = True
                voices_info["system"] = "espeak"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    # Windows - PowerShell SAPI
    elif os_type == "Windows":
        try:
            ps_command = "Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).GetInstalledVoices() | Select -ExpandProperty VoiceInfo | Select Name"
            result = subprocess.run(
                ["powershell", "-Command", ps_command],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                voices_info["has_tts"] = True
                voices_info["system"] = "Windows SAPI"
                voices_info["voices"] = result.stdout.strip().split("\n")[
                    1:
                ]  # Skip header
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    return voices_info


def detect_timezone() -> Dict[str, Any]:
    """Detect system timezone."""

    # Try to get timezone name
    try:
        utc_offset = -time.altzone if time.daylight else -time.timezone

        hours_offset = utc_offset // 3600
        minutes_offset = (abs(utc_offset) % 3600) // 60

        tz_name = time.tzname[time.daylight]

        return {
            "name": tz_name,
            "offset": f"UTC{hours_offset:+03d}:{minutes_offset:02d}",
            "hours_offset": hours_offset,
            "minutes_offset": minutes_offset,
        }
    except Exception:
        return {
            "name": "UTC",
            "offset": "UTC+00:00",
            "hours_offset": 0,
            "minutes_offset": 0,
        }


def detect_llm_keys() -> Dict[str, bool]:
    """Detect which LLM API keys are available."""
    keys = {
        "openai": bool(os.environ.get("OPENAI_API_KEY")),
        "anthropic": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "gemini": bool(
            os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        ),
        "groq": bool(os.environ.get("GROQ_API_KEY")),
        "ollama": False,  # Check if Ollama is running
    }

    # Check if Ollama is accessible
    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, timeout=3)
        keys["ollama"] = result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return keys


def run_environment_detection() -> Dict[str, Any]:
    """Run all environment detection checks."""
    print(f"\n{Colors.CYAN}🔍 Detecting your environment...{Colors.RESET}\n")

    env = {}

    # OS
    print("  • Operating System...", end="", flush=True)
    env["os"] = detect_os()
    print(
        f" {Colors.GREEN}✓{Colors.RESET} {env['os']['system']} {env['os']['release']}"
    )

    # Python
    print("  • Python Version...", end="", flush=True)
    env["python"] = detect_python()
    status = Colors.GREEN if env["python"]["version_ok"] else Colors.YELLOW
    print(f" {status}✓{Colors.RESET} {env['python']['version']}")

    # GPU
    print("  • GPU Acceleration...", end="", flush=True)
    env["gpu"] = detect_gpu()
    if env["gpu"]["has_gpu"]:
        print(
            f" {Colors.GREEN}✓{Colors.RESET} {env['gpu']['type']} - {env['gpu']['name']}"
        )
    else:
        print(f" {Colors.YELLOW}○{Colors.RESET} No GPU detected (CPU only)")

    # TTS Voices
    print("  • Text-to-Speech...", end="", flush=True)
    env["voices"] = detect_voices()
    if env["voices"]["has_tts"]:
        count = len(env["voices"]["voices"])
        print(
            f" {Colors.GREEN}✓{Colors.RESET} {env['voices']['system']} ({count} voices)"
        )
    else:
        print(f" {Colors.YELLOW}○{Colors.RESET} No TTS system detected")

    # Timezone
    print("  • Timezone...", end="", flush=True)
    env["timezone"] = detect_timezone()
    print(
        f" {Colors.GREEN}✓{Colors.RESET} {env['timezone']['name']} ({env['timezone']['offset']})"
    )

    # LLM Keys
    print("  • LLM API Keys...", end="", flush=True)
    env["llm_keys"] = detect_llm_keys()
    available_count = sum(env["llm_keys"].values())
    if available_count > 0:
        print(f" {Colors.GREEN}✓{Colors.RESET} {available_count} provider(s) available")
    else:
        print(
            f" {Colors.YELLOW}○{Colors.RESET} No API keys found (local LLM recommended)"
        )

    return env


# ============================================================================
# USER PROFILE SETUP
# ============================================================================


def get_config_dir() -> Path:
    """Get the configuration directory for agentic-brain."""
    home = Path.home()
    os_type = platform.system()

    if os_type == "Darwin":
        return home / "Library" / "Application Support" / "agentic-brain"
    elif os_type == "Windows":
        return home / "AppData" / "Local" / "agentic-brain"
    else:
        return home / ".config" / "agentic-brain"


def setup_user_profile(env: Dict[str, Any]) -> Dict[str, Any]:
    """Set up user profile with privacy-first approach."""
    print(f"\n{Colors.CYAN}👤 User Profile Setup{Colors.RESET}")
    print("\nPrivacy-first: All information is stored locally and optional.")
    print("Required: Timezone (for accurate scheduling)")
    print("Optional: Name, location, contact info\n")

    profile = {
        "created_at": datetime.utcnow().isoformat(),
        "version": __version__,
    }

    # Timezone (REQUIRED - use detected as default)
    detected_tz = env["timezone"]["name"]
    detected_offset = env["timezone"]["offset"]
    print(f"Timezone detected: {detected_tz} ({detected_offset})")
    use_detected = input("Use this timezone? [Y/n]: ").strip().lower()

    if use_detected != "n":
        profile["timezone"] = detected_tz
        profile["timezone_offset"] = detected_offset
    else:
        tz_input = input(
            "Enter your timezone (e.g., 'America/New_York', 'Australia/Adelaide'): "
        ).strip()
        profile["timezone"] = tz_input or "UTC"
        profile["timezone_offset"] = "UTC+00:00"

    # Optional: Location
    print("\nOptional: Location (city, state/region)")
    location = input("City/State (leave empty to skip): ").strip()
    if location:
        profile["location"] = location

    # Optional: Name
    print("\nOptional: Your name (for personalization)")
    name = input("Name (leave empty to skip): ").strip()
    if name:
        profile["name"] = name

    # Optional: Email
    print("\nOptional: Email (for notifications)")
    email = input("Email (leave empty to skip): ").strip()
    if email:
        profile["email"] = email

    # Optional: Date of birth
    print("\nOptional: Date of birth (for age-appropriate content)")
    dob = input("Date of birth YYYY-MM-DD (leave empty to skip): ").strip()
    if dob:
        profile["date_of_birth"] = dob

    # Save profile
    config_dir = get_config_dir()
    private_dir = config_dir / "private"
    private_dir.mkdir(parents=True, exist_ok=True)

    profile_path = private_dir / "user_profile.json"
    profile_path.write_text(json.dumps(profile, indent=2))

    # Make it read-only for security
    profile_path.chmod(0o600)

    print(f"\n{Colors.GREEN}✓{Colors.RESET} Profile saved to {profile_path}")

    # Create .env.user (git-ignored)
    env_user_path = config_dir / ".env.user"
    env_content = f"""# Agentic Brain User Configuration
# Generated: {datetime.utcnow().isoformat()}
# DO NOT commit this file to git!

# User Settings
USER_TIMEZONE={profile.get('timezone', 'UTC')}
"""

    if "name" in profile:
        env_content += f"USER_NAME={profile['name']}\n"
    if "location" in profile:
        env_content += f"USER_LOCATION={profile['location']}\n"
    if "email" in profile:
        env_content += f"USER_EMAIL={profile['email']}\n"

    env_user_path.write_text(env_content)
    env_user_path.chmod(0o600)

    print(f"{Colors.GREEN}✓{Colors.RESET} User env saved to {env_user_path}")

    return profile


# ============================================================================
# LLM CONFIGURATION
# ============================================================================


def test_llm_connection(provider: str) -> Tuple[bool, str]:
    """Test LLM provider connection."""
    if provider == "ollama":
        try:
            result = subprocess.run(["ollama", "list"], capture_output=True, timeout=3)
            if result.returncode == 0:
                return True, "Ollama is running and accessible"
            return False, "Ollama not responding"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False, "Ollama not installed or not running"

    elif provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return False, "OPENAI_API_KEY not set"

        try:
            import requests

            response = requests.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=5,
            )
            if response.status_code == 200:
                return True, "OpenAI API key is valid"
            return False, f"OpenAI API error: {response.status_code}"
        except Exception as e:
            return False, f"OpenAI connection failed: {str(e)}"

    elif provider == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return False, "ANTHROPIC_API_KEY not set"

        try:
            import requests

            response = requests.get(
                "https://api.anthropic.com/v1/models",
                headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
                timeout=5,
            )
            if response.status_code == 200:
                return True, "Anthropic API key is valid"
            return False, f"Anthropic API error: {response.status_code}"
        except Exception as e:
            return False, f"Anthropic connection failed: {str(e)}"

    elif provider == "groq":
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            return False, "GROQ_API_KEY not set"
        return True, "Groq API key found (connection test skipped)"

    elif provider == "gemini":
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            return False, "GEMINI_API_KEY or GOOGLE_API_KEY not set"
        return True, "Gemini API key found (connection test skipped)"

    return False, f"Unknown provider: {provider}"


def configure_llm(env: Dict[str, Any]) -> Dict[str, Any]:
    """Configure LLM with fallback chain."""
    print(f"\n{Colors.CYAN}🤖 LLM Configuration{Colors.RESET}")
    print("\nAvailable providers:")

    providers = []
    for provider, available in env["llm_keys"].items():
        status = (
            f"{Colors.GREEN}✓ Available{Colors.RESET}"
            if available
            else f"{Colors.YELLOW}○ Not configured{Colors.RESET}"
        )
        print(f"  • {provider.capitalize()}: {status}")
        if available:
            providers.append(provider)

    if not providers:
        print(f"\n{Colors.YELLOW}⚠ No LLM providers configured!{Colors.RESET}")
        print("\nRecommended: Install Ollama for free local LLM")
        print("  • Visit: https://ollama.ai")
        print("  • After install, run: ollama pull llama3.1:8b")

        skip = input("\nContinue without LLM? [y/N]: ").strip().lower()
        if skip != "y":
            print("Installation cancelled. Please configure at least one LLM provider.")
            sys.exit(1)

        return {"providers": [], "default": None, "fallback_chain": []}

    print("\nTesting LLM connections...")

    working_providers = []
    for provider in providers:
        print(f"  • {provider.capitalize()}...", end="", flush=True)
        success, message = test_llm_connection(provider)
        if success:
            print(f" {Colors.GREEN}✓{Colors.RESET} {message}")
            working_providers.append(provider)
        else:
            print(f" {Colors.RED}✗{Colors.RESET} {message}")

    if not working_providers:
        print(f"\n{Colors.RED}✗ No working LLM providers found!{Colors.RESET}")
        return {"providers": [], "default": None, "fallback_chain": []}

    # Set up fallback chain
    print(
        f"\n{Colors.GREEN}✓{Colors.RESET} Found {len(working_providers)} working provider(s)"
    )

    # Recommended fallback order
    priority_order = ["ollama", "groq", "openai", "anthropic", "gemini"]
    fallback_chain = sorted(
        working_providers,
        key=lambda x: priority_order.index(x) if x in priority_order else 99,
    )

    llm_config = {
        "providers": working_providers,
        "default": fallback_chain[0],
        "fallback_chain": fallback_chain,
        "tested_at": datetime.utcnow().isoformat(),
    }

    print(
        f"\nDefault provider: {Colors.BOLD}{llm_config['default'].capitalize()}{Colors.RESET}"
    )
    if len(fallback_chain) > 1:
        print(f"Fallback chain: {' → '.join([p.capitalize() for p in fallback_chain])}")

    return llm_config


# ============================================================================
# ADL INITIALIZATION
# ============================================================================


def initialize_adl(
    config_dir: Path, profile: Dict[str, Any], llm_config: Dict[str, Any]
) -> bool:
    """Initialize ADL (Agentic Definition Language) configuration."""
    print(f"\n{Colors.CYAN}📝 Initializing ADL Configuration{Colors.RESET}\n")

    # Create default brain.adl
    adl_content = f"""# Agentic Brain ADL Configuration
# Generated: {datetime.utcnow().isoformat()}

agent:
  name: "MyBrain"
  version: "1.0.0"
  description: "My personal AI assistant"

user:
  timezone: "{profile.get('timezone', 'UTC')}"
  location: "{profile.get('location', 'Unknown')}"

llm:
  default_provider: "{llm_config.get('default', 'ollama')}"
  fallback_chain: {json.dumps(llm_config.get('fallback_chain', []))}

  models:
    fast: "llama3.2:3b"      # Quick responses
    balanced: "llama3.1:8b"  # Good quality
    smart: "claude-sonnet"   # Best reasoning

chat:
  temperature: 0.7
  max_tokens: 2048
  persist_sessions: true

memory:
  enabled: true
  vector_search: true
  threshold: 0.75

voice:
  enabled: {str(profile.get('voices', {}).get('has_tts', False)).lower()}
  system: "{profile.get('voices', {}).get('system', 'none')}"
  default_voice: "Samantha"
"""

    adl_path = config_dir / "brain.adl"
    adl_path.write_text(adl_content)

    print(f"{Colors.GREEN}✓{Colors.RESET} Created brain.adl")

    # Create config.json
    config = {
        "version": __version__,
        "created_at": datetime.utcnow().isoformat(),
        "user": {
            "timezone": profile.get("timezone", "UTC"),
            "location": profile.get("location"),
        },
        "llm": llm_config,
        "chat": {
            "model": "llama3.1:8b",
            "temperature": 0.7,
            "max_tokens": 2048,
        },
        "memory": {
            "enabled": True,
            "persist_sessions": True,
        },
    }

    config_path = config_dir / "config.json"
    config_path.write_text(json.dumps(config, indent=2))

    print(f"{Colors.GREEN}✓{Colors.RESET} Created config.json")

    return True


# ============================================================================
# HEALTH CHECK
# ============================================================================


def run_health_check(
    env: Dict[str, Any], profile: Dict[str, Any], llm_config: Dict[str, Any]
) -> Dict[str, bool]:
    """Run comprehensive health check."""
    print(f"\n{Colors.CYAN}🏥 Running Health Check{Colors.RESET}\n")

    health = {}

    # Python version
    print("  • Python version...", end="", flush=True)
    python_ok = env["python"]["version_ok"]
    if python_ok:
        print(f" {Colors.GREEN}✓{Colors.RESET} {env['python']['version']} (OK)")
    else:
        print(
            f" {Colors.RED}✗{Colors.RESET} {env['python']['version']} (requires 3.9+)"
        )
    health["python"] = python_ok

    # Virtual environment
    print("  • Virtual environment...", end="", flush=True)
    venv_ok = env["python"]["is_virtualenv"]
    if venv_ok:
        print(f" {Colors.GREEN}✓{Colors.RESET} Active")
    else:
        print(f" {Colors.YELLOW}⚠{Colors.RESET} Not in virtualenv (recommended)")
    health["venv"] = venv_ok

    # GPU acceleration
    print("  • GPU acceleration...", end="", flush=True)
    gpu_ok = env["gpu"]["can_accelerate"]
    if gpu_ok:
        print(f" {Colors.GREEN}✓{Colors.RESET} {env['gpu']['type']}")
    else:
        print(f" {Colors.YELLOW}○{Colors.RESET} CPU only (slower)")
    health["gpu"] = gpu_ok

    # LLM providers
    print("  • LLM providers...", end="", flush=True)
    llm_ok = len(llm_config.get("providers", [])) > 0
    if llm_ok:
        count = len(llm_config["providers"])
        print(f" {Colors.GREEN}✓{Colors.RESET} {count} provider(s) working")
    else:
        print(f" {Colors.RED}✗{Colors.RESET} No providers configured")
    health["llm"] = llm_ok

    # Configuration files
    config_dir = get_config_dir()
    print("  • Configuration files...", end="", flush=True)

    required_files = ["config.json", "brain.adl"]
    all_exist = all((config_dir / f).exists() for f in required_files)

    if all_exist:
        print(f" {Colors.GREEN}✓{Colors.RESET} All present")
    else:
        missing = [f for f in required_files if not (config_dir / f).exists()]
        print(f" {Colors.YELLOW}⚠{Colors.RESET} Missing: {', '.join(missing)}")
    health["config"] = all_exist

    # User profile
    print("  • User profile...", end="", flush=True)
    profile_ok = "timezone" in profile
    if profile_ok:
        print(f" {Colors.GREEN}✓{Colors.RESET} Configured")
    else:
        print(f" {Colors.YELLOW}⚠{Colors.RESET} Missing timezone")
    health["profile"] = profile_ok

    # Overall status
    critical_ok = health.get("python", False) and health.get("llm", False)

    print(f"\n{'='*60}")
    if critical_ok:
        print(f"{Colors.GREEN}{Colors.BOLD}✓ System Ready!{Colors.RESET}")
    else:
        print(f"{Colors.YELLOW}{Colors.BOLD}⚠ System Partially Ready{Colors.RESET}")
        if not health.get("python"):
            print(
                f"  {Colors.RED}•{Colors.RESET} Python version too old - please upgrade"
            )
        if not health.get("llm"):
            print(
                f"  {Colors.RED}•{Colors.RESET} No LLM configured - install Ollama or add API keys"
            )
    print(f"{'='*60}\n")

    health["overall"] = critical_ok
    return health


# ============================================================================
# STATUS DASHBOARD
# ============================================================================


def show_status_dashboard(
    env: Dict[str, Any],
    profile: Dict[str, Any],
    llm_config: Dict[str, Any],
    health: Dict[str, bool],
):
    """Show comprehensive status dashboard."""
    print(
        f"\n{Colors.CYAN}{Colors.BOLD}╔══════════════════════════════════════════════════════════════╗{Colors.RESET}"
    )
    print(
        f"{Colors.CYAN}{Colors.BOLD}║              AGENTIC BRAIN - STATUS DASHBOARD                ║{Colors.RESET}"
    )
    print(
        f"{Colors.CYAN}{Colors.BOLD}╚══════════════════════════════════════════════════════════════╝{Colors.RESET}\n"
    )

    # Environment
    print(f"{Colors.BOLD}Environment:{Colors.RESET}")
    print(
        f"  OS: {env['os']['system']} {env['os']['release']} ({env['os']['machine']})"
    )
    print(f"  Python: {env['python']['version']}")
    if env["gpu"]["has_gpu"]:
        print(f"  GPU: {env['gpu']['type']} - {env['gpu']['name']}")
    else:
        print("  GPU: None (CPU only)")
    print()

    # User Profile
    print(f"{Colors.BOLD}User Profile:{Colors.RESET}")
    print(f"  Timezone: {profile.get('timezone', 'Not set')}")
    if "name" in profile:
        print(f"  Name: {profile['name']}")
    if "location" in profile:
        print(f"  Location: {profile['location']}")
    print()

    # LLM
    print(f"{Colors.BOLD}LLM Configuration:{Colors.RESET}")
    if llm_config.get("providers"):
        print(f"  Default: {llm_config['default'].capitalize()}")
        print(
            f"  Providers: {', '.join([p.capitalize() for p in llm_config['providers']])}"
        )
        if len(llm_config.get("fallback_chain", [])) > 1:
            print(
                f"  Fallback: {' → '.join([p.capitalize() for p in llm_config['fallback_chain']])}"
            )
    else:
        print(f"  {Colors.YELLOW}⚠ No providers configured{Colors.RESET}")
    print()

    # Voices
    print(f"{Colors.BOLD}Text-to-Speech:{Colors.RESET}")
    if env["voices"]["has_tts"]:
        print(f"  System: {env['voices']['system']}")
        print(f"  Voices: {len(env['voices']['voices'])} available")
        if env["voices"]["recommended"]:
            print(f"  Recommended: {', '.join(env['voices']['recommended'][:3])}")
    else:
        print(f"  {Colors.YELLOW}○ Not available{Colors.RESET}")
    print()

    # Health Status
    print(f"{Colors.BOLD}Health Status:{Colors.RESET}")
    for component, status in health.items():
        if component == "overall":
            continue

        if status:
            icon = f"{Colors.GREEN}✓{Colors.RESET}"
        else:
            icon = f"{Colors.YELLOW}⚠{Colors.RESET}"

        print(f"  {icon} {component.capitalize()}")

    print()

    # Configuration Location
    config_dir = get_config_dir()
    print(f"{Colors.BOLD}Configuration:{Colors.RESET}")
    print(f"  Directory: {config_dir}")
    print(f"  Profile: {config_dir / 'private' / 'user_profile.json'}")
    print(f"  ADL Config: {config_dir / 'brain.adl'}")
    print()


# ============================================================================
# MAIN INSTALLER
# ============================================================================


def print_welcome_banner():
    """Print welcome banner."""
    print(
        f"""
{Colors.CYAN}{Colors.BOLD}╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║           Welcome to Agentic Brain Setup Wizard              ║
║                                                              ║
║   This wizard will configure your AI assistant with:         ║
║   • Environment detection (OS, Python, GPU, voices)         ║
║   • User profile setup (timezone, location, preferences)    ║
║   • LLM configuration (API keys, fallback chain)            ║
║   • ADL initialization (default configuration)              ║
║   • Health check (verify everything works)                  ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝{Colors.RESET}
"""
    )


def run_enhanced_installer(non_interactive: bool = False):
    """Run the enhanced installer."""
    print_welcome_banner()

    # Step 1: Environment Detection
    env = run_environment_detection()

    if non_interactive:
        print(
            f"\n{Colors.YELLOW}Running in non-interactive mode - using defaults{Colors.RESET}"
        )

    # Step 2: User Profile Setup
    if non_interactive:
        profile = {
            "timezone": env["timezone"]["name"],
            "timezone_offset": env["timezone"]["offset"],
            "created_at": datetime.utcnow().isoformat(),
        }
        config_dir = get_config_dir()
        private_dir = config_dir / "private"
        private_dir.mkdir(parents=True, exist_ok=True)
        profile_path = private_dir / "user_profile.json"
        profile_path.write_text(json.dumps(profile, indent=2))
        profile_path.chmod(0o600)
    else:
        profile = setup_user_profile(env)

    # Step 3: LLM Configuration
    llm_config = configure_llm(env)

    # Step 4: ADL Initialization
    config_dir = get_config_dir()
    env["voices"] = env.get("voices", {})
    profile["voices"] = env["voices"]
    initialize_adl(config_dir, profile, llm_config)

    # Step 5: Health Check
    health = run_health_check(env, profile, llm_config)

    # Step 6: Show Status Dashboard
    show_status_dashboard(env, profile, llm_config, health)

    # Final message
    if health.get("overall", False):
        print(f"{Colors.GREEN}{Colors.BOLD}✅ Installation Complete!{Colors.RESET}\n")
        print("Next steps:")
        print(f"  1. Try the chatbot: {Colors.CYAN}agentic-brain chat{Colors.RESET}")
        print(f"  2. View config: {Colors.CYAN}agentic-brain config{Colors.RESET}")
        print(f"  3. Check status: {Colors.CYAN}agentic-brain status{Colors.RESET}")
    else:
        print(
            f"{Colors.YELLOW}{Colors.BOLD}⚠ Installation Completed with Warnings{Colors.RESET}\n"
        )
        print("Please address the warnings above before using the system.")

    print(f"\nConfiguration saved to: {config_dir}")
    print("Documentation: https://github.com/joseph-webber/agentic-brain\n")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Enhanced Agentic Brain Installer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Features:
  • Environment detection (OS, Python, GPU, voices)
  • Privacy-first user profile setup
  • LLM configuration with fallback chain
  • ADL initialization
  • Comprehensive health checks
  • Accessible (screen reader compatible)

Examples:
  python -m agentic_brain.installer_enhanced
  python -m agentic_brain.installer_enhanced --non-interactive
        """,
    )

    parser.add_argument(
        "--non-interactive",
        "-y",
        action="store_true",
        help="Run without prompts (use defaults)",
    )

    parser.add_argument(
        "--no-color", action="store_true", help="Disable colored output (accessibility)"
    )

    args = parser.parse_args()

    if args.no_color:
        Colors.disable()

    try:
        run_enhanced_installer(non_interactive=args.non_interactive)
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Installation cancelled by user.{Colors.RESET}")
        sys.exit(1)
    except Exception as e:
        print(
            f"\n{Colors.RED}Error during installation: {e}{Colors.RESET}",
            file=sys.stderr,
        )
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
