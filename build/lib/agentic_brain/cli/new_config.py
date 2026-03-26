# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
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

#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Joseph Webber <joseph.webber@me.com>
"""
Agentic Brain Configuration Wizard
===================================

Interactive configuration wizard using questionary.
Inspired by Freqtrade's new-config command.

Creates:
    - config.json: Main configuration file
    - .env: Environment variables with secrets

Usage:
    agentic new-config
    agentic new-config -c path/to/config.json
    agentic new-config --non-interactive
"""

import json
import secrets
import sys
from pathlib import Path
from typing import Any

try:
    import questionary
    from questionary import Style
except ImportError:
    questionary = None
    Style = None


# Custom style for the wizard (accessible colors)
WIZARD_STYLE = None
if Style:
    WIZARD_STYLE = Style(
        [
            ("qmark", "fg:cyan bold"),
            ("question", "bold"),
            ("answer", "fg:green bold"),
            ("pointer", "fg:cyan bold"),
            ("highlighted", "fg:cyan bold"),
            ("selected", "fg:green"),
            ("separator", "fg:gray"),
            ("instruction", "fg:gray italic"),
            ("text", ""),
            ("disabled", "fg:gray italic"),
        ]
    )


# Template definitions
TEMPLATES = {
    "minimal": {
        "name": "Minimal",
        "description": "Clean chatbot ready for any business. No domain-specific code.",
        "features": ["chat", "memory"],
    },
    "retail": {
        "name": "Retail / E-Commerce",
        "description": "Online store with inventory, orders, and customer support.",
        "features": ["chat", "memory", "rag", "business.retail"],
    },
    "support": {
        "name": "Customer Support",
        "description": "Support ticketing with knowledge base and escalation.",
        "features": ["chat", "memory", "rag", "business.support"],
    },
    "enterprise": {
        "name": "Enterprise",
        "description": "Multi-tenant with audit logging and advanced security.",
        "features": ["chat", "memory", "rag", "auth", "audit"],
    },
}


# LLM provider definitions
LLM_PROVIDERS = {
    "ollama": {
        "name": "Ollama (Local)",
        "description": "Free, runs locally, no API key needed",
        "requires_key": False,
        "models": [
            "llama3.2:3b",
            "llama3.1:8b",
            "llama3.1:70b",
            "mistral:7b",
            "mixtral:8x7b",
            "codellama:13b",
            "phi3:mini",
            "qwen2:7b",
        ],
        "default_model": "llama3.2:3b",
        "base_url": "http://localhost:11434",
    },
    "openai": {
        "name": "OpenAI",
        "description": "GPT-4, GPT-3.5 - requires API key",
        "requires_key": True,
        "key_env": "OPENAI_API_KEY",
        "models": [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-4",
            "gpt-3.5-turbo",
            "o1-preview",
            "o1-mini",
        ],
        "default_model": "gpt-4o-mini",
        "base_url": "https://api.openai.com/v1",
    },
    "anthropic": {
        "name": "Anthropic",
        "description": "Claude 3.5, Claude 3 - requires API key",
        "requires_key": True,
        "key_env": "ANTHROPIC_API_KEY",
        "models": [
            "claude-sonnet-4-20250514",
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
        ],
        "default_model": "claude-sonnet-4-20250514",
        "base_url": "https://api.anthropic.com",
    },
    "openrouter": {
        "name": "OpenRouter",
        "description": "Access multiple providers through one API",
        "requires_key": True,
        "key_env": "OPENROUTER_API_KEY",
        "models": [
            "anthropic/claude-sonnet-4",
            "anthropic/claude-3.5-sonnet",
            "openai/gpt-4o",
            "openai/gpt-4o-mini",
            "meta-llama/llama-3.1-70b-instruct",
            "google/gemini-pro-1.5",
            "mistralai/mixtral-8x7b-instruct",
        ],
        "default_model": "anthropic/claude-sonnet-4",
        "base_url": "https://openrouter.ai/api/v1",
    },
}


# Optional integrations
INTEGRATIONS = [
    {"name": "Slack", "key": "slack", "env_var": "SLACK_BOT_TOKEN"},
    {"name": "Discord", "key": "discord", "env_var": "DISCORD_BOT_TOKEN"},
    {"name": "Telegram", "key": "telegram", "env_var": "TELEGRAM_BOT_TOKEN"},
    {"name": "Redis Cache", "key": "redis", "env_var": "REDIS_URL"},
    {"name": "Firebase Auth", "key": "firebase", "env_var": "FIREBASE_PROJECT_ID"},
    {"name": "Pinecone Vector DB", "key": "pinecone", "env_var": "PINECONE_API_KEY"},
]


def print_banner() -> None:
    """Print wizard banner."""
    print(
        """
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║     █████╗  ██████╗ ███████╗███╗   ██╗████████╗██╗ ██████╗       ║
║    ██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝██║██╔════╝       ║
║    ███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║   ██║██║            ║
║    ██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║   ██║██║            ║
║    ██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║   ██║╚██████╗       ║
║    ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝   ╚═╝ ╚═════╝       ║
║                                                                  ║
║            C O N F I G U R A T I O N   W I Z A R D               ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
    """
    )


def check_questionary() -> bool:
    """Check if questionary is available."""
    if questionary is None:
        print("Error: questionary package not installed.")
        print(
            "Install with: pip install 'agentic-brain[all]' or pip install questionary"
        )
        return False
    return True


def generate_api_key() -> str:
    """Generate a secure random API key."""
    return f"ab_{secrets.token_urlsafe(32)}"


def ask_template() -> str:
    """Ask user to select a template."""
    choices = [
        questionary.Choice(
            title=f"{info['name']} - {info['description']}",
            value=key,
        )
        for key, info in TEMPLATES.items()
    ]

    return questionary.select(
        "Select installation template:",
        choices=choices,
        style=WIZARD_STYLE,
        instruction="(Use arrow keys)",
    ).ask()


def ask_neo4j_config() -> dict[str, Any]:
    """Ask user for Neo4j configuration."""
    print("\n📦 Neo4j Database Configuration")
    print("   Neo4j is used for persistent memory and knowledge graphs.\n")

    use_neo4j = questionary.confirm(
        "Enable Neo4j for persistent memory?",
        default=True,
        style=WIZARD_STYLE,
    ).ask()

    if not use_neo4j:
        return {"enabled": False}

    uri = questionary.text(
        "Neo4j URI:",
        default="bolt://localhost:7687",
        style=WIZARD_STYLE,
    ).ask()

    username = questionary.text(
        "Neo4j username:",
        default="neo4j",
        style=WIZARD_STYLE,
    ).ask()

    password = questionary.password(
        "Neo4j password:",
        style=WIZARD_STYLE,
    ).ask()

    return {
        "enabled": True,
        "uri": uri,
        "username": username,
        "password": password,
    }


def ask_llm_provider() -> dict[str, Any]:
    """Ask user to select LLM provider and model."""
    print("\n🤖 LLM Provider Configuration")
    print("   Choose which LLM provider to use for chat and agents.\n")

    # Select provider
    provider_choices = [
        questionary.Choice(
            title=f"{info['name']} - {info['description']}",
            value=key,
        )
        for key, info in LLM_PROVIDERS.items()
    ]

    provider = questionary.select(
        "Select LLM provider:",
        choices=provider_choices,
        style=WIZARD_STYLE,
        instruction="(Use arrow keys)",
    ).ask()

    if provider is None:
        return None

    provider_info = LLM_PROVIDERS[provider]
    result = {
        "provider": provider,
        "base_url": provider_info["base_url"],
    }

    # Select model with autocomplete for long lists
    if len(provider_info["models"]) > 5:
        model = questionary.autocomplete(
            f"Select {provider_info['name']} model:",
            choices=provider_info["models"],
            default=provider_info["default_model"],
            style=WIZARD_STYLE,
            instruction="(Type to filter, arrows to select)",
        ).ask()
    else:
        model = questionary.select(
            f"Select {provider_info['name']} model:",
            choices=provider_info["models"],
            default=provider_info["default_model"],
            style=WIZARD_STYLE,
        ).ask()

    result["model"] = model

    # Ask for API key if required
    if provider_info["requires_key"]:
        api_key = questionary.password(
            f"Enter {provider_info['name']} API key:",
            style=WIZARD_STYLE,
        ).ask()
        result["api_key"] = api_key
        result["key_env"] = provider_info["key_env"]

    return result


def ask_memory_config() -> dict[str, Any]:
    """Ask user about memory/RAG configuration."""
    print("\n🧠 Memory & Knowledge Configuration")
    print("   Configure how the brain remembers and learns.\n")

    enable_memory = questionary.confirm(
        "Enable persistent memory (remembers conversations)?",
        default=True,
        style=WIZARD_STYLE,
    ).ask()

    enable_rag = questionary.confirm(
        "Enable RAG (Retrieval-Augmented Generation)?",
        default=False,
        style=WIZARD_STYLE,
        instruction="(Use for knowledge base features)",
    ).ask()

    result = {
        "persistent_memory": enable_memory,
        "rag_enabled": enable_rag,
    }

    if enable_rag:
        # Ask about embedding provider
        embedding_provider = questionary.select(
            "Select embedding provider for RAG:",
            choices=[
                questionary.Choice("Ollama (local, free)", value="ollama"),
                questionary.Choice("OpenAI embeddings", value="openai"),
                questionary.Choice(
                    "Sentence Transformers (local)", value="sentence-transformers"
                ),
            ],
            style=WIZARD_STYLE,
        ).ask()
        result["embedding_provider"] = embedding_provider

    return result


def ask_api_config() -> dict[str, Any]:
    """Ask user about API server configuration."""
    print("\n🌐 API Server Configuration")
    print("   Configure the HTTP API for external access.\n")

    start_api = questionary.confirm(
        "Start API server?",
        default=True,
        style=WIZARD_STYLE,
    ).ask()

    if not start_api:
        return {"enabled": False}

    port = questionary.text(
        "API server port:",
        default="8000",
        validate=lambda x: x.isdigit() and 1024 <= int(x) <= 65535,
        style=WIZARD_STYLE,
    ).ask()

    generate_key = questionary.confirm(
        "Generate secure API key for authentication?",
        default=True,
        style=WIZARD_STYLE,
    ).ask()

    api_key = None
    if generate_key:
        api_key = generate_api_key()
        print(f"\n   🔑 Generated API key: {api_key}")
        print("   Save this key - you'll need it for API access!\n")

    cors_origins = questionary.text(
        "CORS allowed origins (comma-separated, or * for all):",
        default="http://localhost:3000",
        style=WIZARD_STYLE,
    ).ask()

    return {
        "enabled": True,
        "port": int(port),
        "api_key": api_key,
        "cors_origins": [o.strip() for o in cors_origins.split(",")],
    }


def ask_integrations() -> list[dict[str, Any]]:
    """Ask user about optional integrations."""
    print("\n🔌 Optional Integrations")
    print("   Enable additional platform integrations.\n")

    enable_integrations = questionary.confirm(
        "Configure optional integrations?",
        default=False,
        style=WIZARD_STYLE,
    ).ask()

    if not enable_integrations:
        return []

    selected = questionary.checkbox(
        "Select integrations to enable:",
        choices=[questionary.Choice(i["name"], value=i) for i in INTEGRATIONS],
        style=WIZARD_STYLE,
        instruction="(Space to select, Enter to confirm)",
    ).ask()

    result = []
    for integration in selected or []:
        print(f"\n   Configuring {integration['name']}...")
        token = questionary.password(
            f"Enter {integration['name']} token/key:",
            style=WIZARD_STYLE,
        ).ask()
        result.append(
            {
                "name": integration["key"],
                "env_var": integration["env_var"],
                "token": token,
            }
        )

    return result


def generate_config(
    template: str,
    neo4j: dict[str, Any],
    llm: dict[str, Any],
    memory: dict[str, Any],
    api: dict[str, Any],
    integrations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Generate the configuration dictionary."""
    config = {
        "$schema": "https://agentic-brain.dev/schemas/config.json",
        "version": "1.0.0",
        "template": template,
        "llm": {
            "provider": llm["provider"],
            "model": llm["model"],
            "base_url": llm["base_url"],
            "temperature": 0.7,
            "max_tokens": 2048,
        },
        "memory": {
            "enabled": memory.get("persistent_memory", True),
            "similarity_threshold": 0.7,
        },
        "rag": {
            "enabled": memory.get("rag_enabled", False),
            "embedding_provider": memory.get("embedding_provider", "ollama"),
            "chunk_size": 512,
            "chunk_overlap": 50,
        },
    }

    if neo4j.get("enabled"):
        config["neo4j"] = {
            "uri": neo4j["uri"],
            "username": neo4j["username"],
            # Password goes to .env, not config
        }

    if api.get("enabled"):
        config["api"] = {
            "enabled": True,
            "port": api["port"],
            "cors_origins": api["cors_origins"],
            # API key goes to .env
        }
    else:
        config["api"] = {"enabled": False}

    if integrations:
        config["integrations"] = {i["name"]: {"enabled": True} for i in integrations}

    return config


def generate_env_file(
    neo4j: dict[str, Any],
    llm: dict[str, Any],
    api: dict[str, Any],
    integrations: list[dict[str, Any]],
) -> str:
    """Generate .env file content."""
    lines = [
        "# Agentic Brain Configuration",
        "# Generated by new-config wizard",
        "# ⚠️ Keep this file secure - contains secrets!",
        "",
    ]

    # Neo4j
    if neo4j.get("enabled"):
        lines.extend(
            [
                "# Neo4j Database",
                f"NEO4J_URI={neo4j['uri']}",
                f"NEO4J_USER={neo4j['username']}",
                f"NEO4J_PASSWORD={neo4j.get('password', '')}",
                "",
            ]
        )

    # LLM
    lines.append("# LLM Provider")
    lines.append(f"LLM_PROVIDER={llm['provider']}")
    lines.append(f"LLM_MODEL={llm['model']}")
    if llm.get("api_key"):
        lines.append(f"{llm['key_env']}={llm['api_key']}")
    lines.append("")

    # API
    if api.get("enabled"):
        lines.extend(
            [
                "# API Server",
                f"API_PORT={api['port']}",
            ]
        )
        if api.get("api_key"):
            lines.append(f"API_KEY={api['api_key']}")
        lines.append("")

    # Integrations
    if integrations:
        lines.append("# Integrations")
        for integration in integrations:
            lines.append(f"{integration['env_var']}={integration['token']}")
        lines.append("")

    return "\n".join(lines)


def save_config(
    config: dict[str, Any],
    env_content: str,
    output_path: Path,
) -> tuple[Path, Path]:
    """Save configuration files."""
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Save config.json
    config_path = output_path
    config_path.write_text(json.dumps(config, indent=2))

    # Save .env in same directory
    env_path = output_path.parent / ".env"
    env_path.write_text(env_content)

    # Set restrictive permissions on .env (contains secrets)
    try:
        env_path.chmod(0o600)
    except OSError:
        pass  # Windows doesn't support chmod

    return config_path, env_path


def print_summary(
    config: dict[str, Any],
    config_path: Path,
    env_path: Path,
) -> None:
    """Print configuration summary."""
    print(
        """
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║  ✅ Configuration Complete!                                      ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
"""
    )

    print("📄 Files created:")
    print(f"   • {config_path}")
    print(f"   • {env_path}")

    print("\n📋 Configuration summary:")
    print(f"   • Template: {TEMPLATES[config['template']]['name']}")
    print(f"   • LLM: {config['llm']['provider']} / {config['llm']['model']}")
    print(f"   • Memory: {'Enabled' if config['memory']['enabled'] else 'Disabled'}")
    print(f"   • RAG: {'Enabled' if config['rag']['enabled'] else 'Disabled'}")
    print(
        f"   • API: {'Port ' + str(config['api']['port']) if config['api']['enabled'] else 'Disabled'}"
    )

    if config.get("integrations"):
        print(f"   • Integrations: {', '.join(config['integrations'].keys())}")

    print(
        """
🚀 Next steps:

   1. Review and edit config.json if needed
   2. Start Neo4j: docker-compose up -d neo4j
   3. Run the brain: python -m agentic_brain.cli chat
   4. Or start API: python -m agentic_brain.cli serve

📚 Documentation: https://github.com/joseph-webber/agentic-brain
"""
    )


def ask_self_bootstrap() -> bool:
    """Ask if user wants the brain to help configure advanced settings."""
    print("\n🧠 Self-Bootstrap Feature")
    print("   The brain itself can help you configure advanced features.\n")

    return questionary.confirm(
        "Would you like me to help you set up more features?",
        default=True,
        style=WIZARD_STYLE,
        instruction="(Start a chat session to configure advanced settings)",
    ).ask()


def test_configuration(config: dict[str, Any]) -> bool:
    """Test the configuration by attempting connections."""
    print("\n🔍 Testing configuration...")

    all_good = True

    # Test Neo4j
    if config.get("neo4j", {}).get("uri"):
        print("   • Testing Neo4j connection... ", end="", flush=True)
        try:
            from agentic_brain.neo4j import Neo4jPool

            pool = Neo4jPool(
                uri=config["neo4j"]["uri"],
                auth=(config["neo4j"]["username"], ""),  # Password from env
            )
            pool.close()
            print("✅")
        except Exception as e:
            print(f"❌ ({e})")
            all_good = False

    # Test Ollama
    if config["llm"]["provider"] == "ollama":
        print("   • Testing Ollama connection... ", end="", flush=True)
        try:
            import asyncio

            import aiohttp

            async def check_ollama():
                async with aiohttp.ClientSession() as session:
                    async with session.get(
                        f"{config['llm']['base_url']}/api/tags"
                    ) as resp:
                        return resp.status == 200

            if asyncio.run(check_ollama()):
                print("✅")
            else:
                print("❌ (Ollama not responding)")
                all_good = False
        except Exception as e:
            print(f"❌ ({e})")
            all_good = False

    return all_good


def run_wizard(
    output_path: Path | None = None,
    non_interactive: bool = False,
) -> int:
    """Run the interactive configuration wizard.

    Args:
        output_path: Path to save config.json (default: ./config.json)
        non_interactive: Use defaults without prompting

    Returns:
        Exit code (0 for success)
    """
    if not check_questionary():
        return 1

    print_banner()

    if non_interactive:
        print("Running in non-interactive mode with defaults...\n")
        template = "minimal"
        neo4j = {
            "enabled": True,
            "uri": "bolt://localhost:7687",
            "username": "neo4j",
            "password": "password",
        }
        llm = {
            "provider": "ollama",
            "model": "llama3.2:3b",
            "base_url": "http://localhost:11434",
        }
        memory = {"persistent_memory": True, "rag_enabled": False}
        api = {
            "enabled": True,
            "port": 8000,
            "api_key": generate_api_key(),
            "cors_origins": ["*"],
        }
        integrations = []
    else:
        try:
            # Interactive prompts
            template = ask_template()
            if template is None:
                print("\nConfiguration cancelled.")
                return 1

            neo4j = ask_neo4j_config()
            if neo4j is None:
                print("\nConfiguration cancelled.")
                return 1

            llm = ask_llm_provider()
            if llm is None:
                print("\nConfiguration cancelled.")
                return 1

            memory = ask_memory_config()
            if memory is None:
                print("\nConfiguration cancelled.")
                return 1

            api = ask_api_config()
            if api is None:
                print("\nConfiguration cancelled.")
                return 1

            integrations = ask_integrations()
            if integrations is None:
                integrations = []

        except KeyboardInterrupt:
            print("\n\nConfiguration cancelled.")
            return 130

    # Generate configuration
    config = generate_config(template, neo4j, llm, memory, api, integrations)
    env_content = generate_env_file(neo4j, llm, api, integrations)

    # Determine output path
    if output_path is None:
        output_path = Path.cwd() / "config.json"

    # Save files
    config_path, env_path = save_config(config, env_content, output_path)

    # Print summary
    print_summary(config, config_path, env_path)

    # Offer to test configuration
    if not non_interactive:
        test_config = questionary.confirm(
            "Test the configuration now?",
            default=True,
            style=WIZARD_STYLE,
        ).ask()

        if test_config:
            test_configuration(config)

        # Offer self-bootstrap
        if ask_self_bootstrap():
            print("\n🧠 Starting brain chat session for advanced configuration...")
            print("   (Type 'help' for available configuration commands)\n")
            # This would start a chat session - placeholder for now
            # from agentic_brain.cli.commands import chat_command
            # return chat_command(args_with_config)

    return 0


def new_config_command(args) -> int:
    """CLI command handler for new-config.

    Args:
        args: Parsed command-line arguments

    Returns:
        Exit code
    """
    output_path = Path(args.config) if hasattr(args, "config") and args.config else None
    non_interactive = getattr(args, "non_interactive", False)

    return run_wizard(output_path=output_path, non_interactive=non_interactive)


def main() -> int:
    """Standalone entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Agentic Brain Configuration Wizard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-c",
        "--config",
        type=str,
        default=None,
        help="Output path for config.json (default: ./config.json)",
    )
    parser.add_argument(
        "-y",
        "--non-interactive",
        action="store_true",
        help="Use defaults without prompting",
    )

    args = parser.parse_args()
    return run_wizard(
        output_path=Path(args.config) if args.config else None,
        non_interactive=args.non_interactive,
    )


if __name__ == "__main__":
    sys.exit(main())
