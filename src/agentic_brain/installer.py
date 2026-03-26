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
# Copyright (C) 2026 Joseph Webber <joseph.webber@me.com>
"""
Agentic Brain Installer
=======================

Interactive installer that sets up agentic-brain for your use case.

Installation Modes:
    - minimal: Clean chatbot, ready for any business
    - retail: E-commerce with inventory, orders, customers
    - support: Customer support with ticketing
    - custom: Choose your own components

Usage:
    python -m agentic_brain.installer
    python -m agentic_brain.installer --mode minimal
    python -m agentic_brain.installer --mode retail
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

__all__ = [
    "run_installer",
    "main",
    "show_llm_help",
    "show_llm_tutorial",
    # Additional exports for tests
    "TEMPLATES",
    "NEO4J_SCHEMAS",
    "LLM_TEMPLATES",
    "get_platform",
    "get_config_dir",
    "get_home_dir",
    "print_progress",
    "print_progress_bar",
    "print_welcome_banner",
    "print_success_banner",
    "show_template_confirmation",
    "copy_llm_template",
]


# Installation templates
TEMPLATES = {
    "minimal": {
        "name": "Minimal",
        "description": "Clean chatbot ready for any business. No domain-specific code.",
        "components": ["chat", "memory", "session"],
        "examples": ["simple_chat.py"],
        "neo4j_schema": "minimal",
    },
    "retail": {
        "name": "Retail / E-Commerce",
        "description": "Online store with inventory, orders, customers, and support bot.",
        "components": ["chat", "memory", "session", "rag", "business.retail"],
        "examples": ["simple_chat.py", "retail_bot.py", "inventory_query.py"],
        "neo4j_schema": "retail",
    },
    "support": {
        "name": "Customer Support",
        "description": "Support ticketing with knowledge base and escalation.",
        "components": ["chat", "memory", "session", "rag", "business.support"],
        "examples": ["simple_chat.py", "support_bot.py"],
        "neo4j_schema": "support",
    },
    "enterprise": {
        "name": "Enterprise",
        "description": "Full features with multi-tenant isolation and audit logging.",
        "components": ["chat", "memory", "session", "rag", "business.enterprise"],
        "examples": ["simple_chat.py", "enterprise_bot.py"],
        "neo4j_schema": "enterprise",
    },
}

# Neo4j schema templates
NEO4J_SCHEMAS = {
    "minimal": """
// Minimal Schema - Conversations and Memory Only
CREATE CONSTRAINT conversation_id IF NOT EXISTS FOR (c:Conversation) REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT memory_id IF NOT EXISTS FOR (m:Memory) REQUIRE m.id IS UNIQUE;
CREATE CONSTRAINT user_id IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE;

CREATE INDEX conversation_timestamp IF NOT EXISTS FOR (c:Conversation) ON (c.timestamp);
CREATE INDEX memory_embedding IF NOT EXISTS FOR (m:Memory) ON (m.embedding);
""",
    "retail": """
// Retail E-Commerce Schema
// Core entities
CREATE CONSTRAINT conversation_id IF NOT EXISTS FOR (c:Conversation) REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT memory_id IF NOT EXISTS FOR (m:Memory) REQUIRE m.id IS UNIQUE;
CREATE CONSTRAINT user_id IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE;

// Retail entities
CREATE CONSTRAINT product_sku IF NOT EXISTS FOR (p:Product) REQUIRE p.sku IS UNIQUE;
CREATE CONSTRAINT order_id IF NOT EXISTS FOR (o:Order) REQUIRE o.id IS UNIQUE;
CREATE CONSTRAINT customer_id IF NOT EXISTS FOR (c:Customer) REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT category_id IF NOT EXISTS FOR (c:Category) REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT supplier_id IF NOT EXISTS FOR (s:Supplier) REQUIRE s.id IS UNIQUE;

// Indexes for common queries
CREATE INDEX product_name IF NOT EXISTS FOR (p:Product) ON (p.name);
CREATE INDEX order_status IF NOT EXISTS FOR (o:Order) ON (o.status);
CREATE INDEX order_date IF NOT EXISTS FOR (o:Order) ON (o.created_at);
CREATE INDEX customer_email IF NOT EXISTS FOR (c:Customer) ON (c.email);
CREATE INDEX inventory_level IF NOT EXISTS FOR (p:Product) ON (p.stock_quantity);

// Relationships
// (:Customer)-[:PLACED]->(:Order)
// (:Order)-[:CONTAINS]->(:OrderItem)-[:FOR_PRODUCT]->(:Product)
// (:Product)-[:IN_CATEGORY]->(:Category)
// (:Product)-[:SUPPLIED_BY]->(:Supplier)
// (:Conversation)-[:WITH_CUSTOMER]->(:Customer)
// (:Conversation)-[:ABOUT_ORDER]->(:Order)
""",
    "support": """
// Customer Support Schema
CREATE CONSTRAINT conversation_id IF NOT EXISTS FOR (c:Conversation) REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT memory_id IF NOT EXISTS FOR (m:Memory) REQUIRE m.id IS UNIQUE;
CREATE CONSTRAINT user_id IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE;

// Support entities
CREATE CONSTRAINT ticket_id IF NOT EXISTS FOR (t:Ticket) REQUIRE t.id IS UNIQUE;
CREATE CONSTRAINT article_id IF NOT EXISTS FOR (a:Article) REQUIRE a.id IS UNIQUE;
CREATE CONSTRAINT agent_id IF NOT EXISTS FOR (a:Agent) REQUIRE a.id IS UNIQUE;

// Indexes
CREATE INDEX ticket_status IF NOT EXISTS FOR (t:Ticket) ON (t.status);
CREATE INDEX ticket_priority IF NOT EXISTS FOR (t:Ticket) ON (t.priority);
CREATE INDEX article_category IF NOT EXISTS FOR (a:Article) ON (a.category);
""",
    "enterprise": """
// Enterprise Multi-Tenant Schema
CREATE CONSTRAINT conversation_id IF NOT EXISTS FOR (c:Conversation) REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT memory_id IF NOT EXISTS FOR (m:Memory) REQUIRE m.id IS UNIQUE;
CREATE CONSTRAINT user_id IF NOT EXISTS FOR (u:User) REQUIRE u.id IS UNIQUE;

// Multi-tenant
CREATE CONSTRAINT tenant_id IF NOT EXISTS FOR (t:Tenant) REQUIRE t.id IS UNIQUE;
CREATE CONSTRAINT audit_id IF NOT EXISTS FOR (a:AuditLog) REQUIRE a.id IS UNIQUE;

// Indexes
CREATE INDEX tenant_name IF NOT EXISTS FOR (t:Tenant) ON (t.name);
CREATE INDEX audit_timestamp IF NOT EXISTS FOR (a:AuditLog) ON (a.timestamp);
CREATE INDEX audit_action IF NOT EXISTS FOR (a:AuditLog) ON (a.action);

// All entities should have tenant_id for isolation
// (:Conversation {tenant_id: 'xxx'})
// (:Memory {tenant_id: 'xxx'})
""",
}

# LLM Templates for AI model configuration
LLM_TEMPLATES = {
    "privacy-first": {
        "number": 1,
        "emoji": "🔒",
        "name": "Privacy First",
        "tagline": "Local LLM - Your data never leaves your machine",
        "template_file": "privacy_first.yaml",
        "best_for": "Privacy-sensitive applications, offline use",
        "features": ["100% local processing", "No API keys needed", "Works offline"],
        "requirements": ["Ollama installed", "16GB RAM recommended"],
        "cost": "Free (hardware costs only)",
    },
    "budget-zero": {
        "number": 2,
        "emoji": "💰",
        "name": "Budget Zero",
        "tagline": "Free cloud APIs - Start without spending a cent",
        "template_file": "budget_zero.yaml",
        "best_for": "Learning, prototyping, small projects",
        "features": ["Free tier APIs", "Quick setup", "Good quality"],
        "requirements": ["Internet connection", "Free API keys"],
        "cost": "Free (within limits)",
    },
    "speed-demon": {
        "number": 3,
        "emoji": "⚡",
        "name": "Speed Demon",
        "tagline": "Fastest response times - Sub-second replies",
        "template_file": "speed_demon.yaml",
        "best_for": "Real-time applications, chat interfaces",
        "features": ["<500ms responses", "Groq acceleration", "High throughput"],
        "requirements": ["Groq API key"],
        "cost": "Free tier available, paid for heavy use",
    },
    "business-standard": {
        "number": 4,
        "emoji": "💼",
        "name": "Business Standard",
        "tagline": "Production-ready - Reliable and professional",
        "template_file": "business_standard.yaml",
        "best_for": "Business applications, customer-facing products",
        "features": ["High reliability", "Enterprise support", "SLA guarantees"],
        "requirements": ["OpenAI API key", "Budget ~$20-100/month"],
        "cost": "$20-100/month typical",
    },
    "developer": {
        "number": 5,
        "emoji": "🛠️",
        "name": "Developer",
        "tagline": "Best for coding - Optimized for code generation",
        "template_file": "developer.yaml",
        "best_for": "Code generation, debugging, documentation",
        "features": ["Code-optimized models", "Long context", "Tool use"],
        "requirements": ["Anthropic or OpenAI key"],
        "cost": "$10-50/month typical",
    },
    "aussie-default": {
        "number": 6,
        "emoji": "🦘",
        "name": "Aussie Default",
        "tagline": "Joseph's Setup - Balanced local + cloud",
        "template_file": "aussie_default.yaml",
        "best_for": "Australian users, accessibility focus",
        "features": ["Local primary", "Cloud fallback", "Voice optimized"],
        "requirements": ["Ollama installed", "Optional API keys"],
        "cost": "Mostly free, cloud costs on demand",
    },
}


def get_platform() -> str:
    """Get the current platform identifier."""
    import platform

    system = platform.system().lower()
    return {"darwin": "macos", "windows": "windows", "linux": "linux"}.get(
        system, system
    )


def get_home_dir() -> Path:
    """Get the user's home directory."""
    return Path.home()


def get_config_dir() -> Path:
    """Get the configuration directory for agentic-brain."""
    home = get_home_dir()
    platform = get_platform()
    if platform == "macos":
        return home / "Library" / "Application Support" / "agentic-brain"
    elif platform == "windows":
        return home / "AppData" / "Local" / "agentic-brain"
    else:
        return home / ".config" / "agentic-brain"


def print_progress(message: str, current: int = 0, total: int = 0) -> None:
    """Print progress message."""
    if total > 0:
        percentage = int((current / total) * 100)
        print(f"[{percentage:3d}%] {message}")
    else:
        print(f"[...] {message}")


def print_progress_bar(
    current: int, total: int, width: int = 40, prefix: str = ""
) -> None:
    """Print a progress bar."""
    if total <= 0:
        return
    filled = int(width * current / total)
    bar = "█" * filled + "░" * (width - filled)
    percentage = int((current / total) * 100)
    print(f"\r{prefix}[{bar}] {percentage}%", end="", flush=True)
    if current >= total:
        print()


def print_welcome_banner() -> None:
    """Print a welcome banner for the installer."""
    print(
        """
╔══════════════════════════════════════════════════════════════╗
║           Welcome to Agentic Brain Setup Wizard              ║
║                                                              ║
║   This wizard will help you configure your AI assistant.    ║
╚══════════════════════════════════════════════════════════════╝
"""
    )


def print_success_banner(message: str = "Setup Complete!") -> None:
    """Print a success banner.

    Args:
        message: Message or path to display. If a path, shows completion message.
    """
    msg_str = str(message)
    # If it looks like a path, show a "Complete" message
    if "/" in msg_str or "\\" in msg_str:
        display = "Installation Complete!"
        extra = f"\n  Quick Start: cd {msg_str} && agentic-brain"
    else:
        display = msg_str
        extra = ""
    print(
        f"""
╔══════════════════════════════════════════════════════════════╗
║  ✅ {display:^54}  ║
╚══════════════════════════════════════════════════════════════╝{extra}
"""
    )


def show_template_confirmation(template_name: str, config: dict) -> None:
    """Show confirmation of selected template."""
    print(f"\n📋 Selected Template: {template_name}")
    print(f"   Name: {config.get('name', template_name)}")
    if "tagline" in config:
        print(f"   Description: {config.get('tagline')}")
    if "best_for" in config:
        print(f"   Best for: {config.get('best_for')}")
    if "requirements" in config:
        reqs = config.get("requirements", [])
        if reqs:
            print(f"   Requirements: {', '.join(reqs)}")
    if "cost" in config:
        print(f"   Cost: {config.get('cost')}")
    print(
        f"   Config File: {config.get('template_file', config.get('config_file', 'N/A'))}"
    )


def copy_llm_template(template_id: str, dest_dir: Path) -> bool:
    """Copy an LLM template configuration to the destination directory.

    Args:
        template_id: The template name (e.g., "privacy-first", "budget-zero")
        dest_dir: Destination directory for the config file

    Returns:
        True if successful, False otherwise
    """
    if template_id not in LLM_TEMPLATES:
        return False

    template = LLM_TEMPLATES[template_id]
    config_file = template.get("template_file", template.get("config_file", ""))

    # Look for template in package data
    import importlib.resources

    try:
        # Python 3.9+
        if hasattr(importlib.resources, "files"):
            pkg_files = importlib.resources.files("agentic_brain")
            template_path = pkg_files.joinpath("templates", "llm", config_file)
            if template_path.is_file():
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest_path = dest_dir / config_file
                dest_path.write_text(template_path.read_text())
                # Also create .env file
                env_path = dest_dir / ".env"
                env_path.write_text(template_path.read_text())
                return True
    except Exception:
        pass

    # Fallback: create minimal config
    dest_dir.mkdir(parents=True, exist_ok=True)

    config_content = f"""# Agentic Brain LLM Configuration
# Template: {template['name']}
# {template.get('tagline', '')}
name: {template['name']}
number: {template.get('number', 0)}
"""

    # Write to both config file and .env
    if config_file:
        dest_path = dest_dir / config_file
        dest_path.write_text(config_content)

    env_path = dest_dir / ".env"
    env_path.write_text(config_content)

    return True


def print_banner():
    """Print installer banner."""
    print(
        """
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║     █████╗  ██████╗ ███████╗███╗   ██╗████████╗██╗ ██████╗   ║
║    ██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝██║██╔════╝   ║
║    ███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║   ██║██║        ║
║    ██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║   ██║██║        ║
║    ██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║   ██║╚██████╗   ║
║    ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝   ╚═╝ ╚═════╝   ║
║                                                              ║
║              B R A I N    I N S T A L L E R                  ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
    """
    )


def choose_template() -> str:
    """Interactive template selection."""
    print("\n📦 Choose your installation template:\n")

    templates = list(TEMPLATES.items())
    for i, (_key, template) in enumerate(templates, 1):
        print(f"  {i}. {template['name']}")
        print(f"     {template['description']}")
        print()

    while True:
        try:
            choice = input("Enter number (1-4) or template name: ").strip()

            # Handle numeric choice
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(templates):
                    return templates[idx][0]

            # Handle name choice
            if choice.lower() in TEMPLATES:
                return choice.lower()

            print("Invalid choice. Please try again.")
        except (ValueError, KeyboardInterrupt):
            print("\nInstallation cancelled.")
            sys.exit(0)


def get_project_dir() -> Path:
    """Get or create project directory."""
    default_dir = Path.cwd() / "my_chatbot"

    print(f"\n📁 Project directory (default: {default_dir})")
    user_dir = input("   Press Enter for default or enter path: ").strip()

    project_dir = Path(user_dir).expanduser().resolve() if user_dir else default_dir

    return project_dir


def get_neo4j_config() -> dict[str, str]:
    """Get Neo4j connection details."""
    print("\n🔗 Neo4j Configuration")
    print("   Press Enter for defaults\n")

    uri = input("   URI [bolt://localhost:7687]: ").strip() or "bolt://localhost:7687"
    user = input("   Username [neo4j]: ").strip() or "neo4j"
    password = input("   Password [password]: ").strip() or "password"

    return {"uri": uri, "user": user, "password": password}


def create_project_structure(project_dir: Path, template: str):
    """Create project directory structure."""
    TEMPLATES[template]

    # Create directories
    dirs = [
        project_dir,
        project_dir / "src",
        project_dir / "examples",
        project_dir / "docs",
        project_dir / "tests",
        project_dir / "data",
        project_dir / "sessions",
    ]

    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)

    print(f"\n✅ Created project structure at {project_dir}")


def create_config_file(project_dir: Path, template: str, neo4j_config: dict[str, str]):
    """Create configuration file."""
    config = {
        "template": template,
        "version": "1.0.0",
        "neo4j": neo4j_config,
        "chat": {
            "model": "llama3.1:8b",
            "temperature": 0.7,
            "max_tokens": 1024,
            "persist_sessions": True,
            "session_dir": str(project_dir / "sessions"),
        },
        "memory": {"enabled": True, "threshold": 0.7},
    }

    config_path = project_dir / "config.json"
    config_path.write_text(json.dumps(config, indent=2))
    print("✅ Created config.json")


def create_env_file(project_dir: Path, neo4j_config: dict[str, str]):
    """Create .env file for credentials."""
    env_content = f"""# Agentic Brain Configuration
# Generated by installer - customize as needed

# Neo4j
NEO4J_URI={neo4j_config['uri']}
NEO4J_USER={neo4j_config['user']}
NEO4J_PASSWORD={neo4j_config['password']}

# LLM (Ollama default - no key needed)
# OPENAI_API_KEY=your_key_here
# ANTHROPIC_API_KEY=your_key_here

# Optional
# LOG_LEVEL=INFO
"""

    env_path = project_dir / ".env"
    env_path.write_text(env_content)
    print("✅ Created .env file")


def create_schema_file(project_dir: Path, template: str):
    """Create Neo4j schema file."""
    schema = NEO4J_SCHEMAS.get(template, NEO4J_SCHEMAS["minimal"])

    schema_path = project_dir / "schema.cypher"
    schema_path.write_text(schema)
    print("✅ Created schema.cypher")


def create_main_file(project_dir: Path, template: str):
    """Create main.py entry point."""
    template_info = TEMPLATES[template]

    if template == "minimal":
        main_content = '''#!/usr/bin/env python3
"""
My Chatbot - Powered by Agentic Brain
======================================

A clean, minimal chatbot ready for your business.
Customize this file to add your own logic.
"""

from agentic_brain.chat import Chatbot, ChatConfig


def main():
    # Create your chatbot
    config = ChatConfig(
        persist_sessions=True,
        use_memory=True
    )

    bot = Chatbot("assistant", config=config)

    print("🤖 My Chatbot")
    print("Type 'quit' to exit\\n")

    while True:
        try:
            user_input = input("You: ").strip()
            if user_input.lower() == 'quit':
                break

            response = bot.chat(user_input)
            print(f"Bot: {response}\\n")

        except KeyboardInterrupt:
            break

    print("Goodbye!")


if __name__ == "__main__":
    main()
'''
    elif template == "retail":
        main_content = '''#!/usr/bin/env python3
"""
Retail Chatbot - Powered by Agentic Brain
==========================================

E-commerce chatbot with inventory, orders, and customer support.
"""

from agentic_brain.chat import Chatbot, ChatConfig
from agentic_brain import Neo4jMemory


# Retail-specific system prompt
RETAIL_PROMPT = """You are a helpful retail assistant for an online store.

You can help customers with:
- Product information and recommendations
- Order status and tracking
- Returns and exchanges
- General questions

Be friendly, helpful, and concise. If you don't know something,
offer to connect them with a human agent."""


def main():
    # Connect to Neo4j for memory and inventory
    memory = Neo4jMemory()

    config = ChatConfig(
        persist_sessions=True,
        use_memory=True,
        customer_isolation=True,  # Each customer sees only their data
        system_prompt=RETAIL_PROMPT
    )

    bot = Chatbot("retail-assistant", memory=memory, config=config)

    print("🛒 Retail Assistant")
    print("Type 'quit' to exit\\n")

    # In production, customer_id comes from authentication
    customer_id = input("Customer ID (or press Enter for guest): ").strip() or "guest"

    while True:
        try:
            user_input = input("Customer: ").strip()
            if user_input.lower() == 'quit':
                break

            response = bot.chat(user_input, user_id=customer_id)
            print(f"Assistant: {response}\\n")

        except KeyboardInterrupt:
            break

    print("Thank you for shopping with us!")


if __name__ == "__main__":
    main()
'''
    else:
        # Generic template
        main_content = f'''#!/usr/bin/env python3
"""
{template_info["name"]} Chatbot - Powered by Agentic Brain
"""

from agentic_brain.chat import Chatbot, ChatConfig


def main():
    config = ChatConfig(persist_sessions=True, use_memory=True)
    bot = Chatbot("assistant", config=config)

    print("🤖 {template_info["name"]} Chatbot")
    print("Type \\'quit\\' to exit\\n")

    while True:
        try:
            user_input = input("You: ").strip()
            if user_input.lower() == \\'quit\\':
                break
            response = bot.chat(user_input)
            print(f"Bot: {{response}}\\n")
        except KeyboardInterrupt:
            break

    print("Goodbye!")


if __name__ == "__main__":
    main()
'''

    main_path = project_dir / "main.py"
    main_path.write_text(main_content)
    print("✅ Created main.py")


def create_readme(project_dir: Path, template: str):
    """Create README.md."""
    template_info = TEMPLATES[template]

    readme = f"""# My Chatbot

Powered by [Agentic Brain](https://github.com/joseph-webber/agentic-brain) - {template_info['name']} template.

## Quick Start

```bash
# Install dependencies
pip install agentic-brain

# Start Neo4j (if using Docker)
docker-compose up -d neo4j

# Apply schema
cat schema.cypher | cypher-shell -u neo4j -p Brain2026

# Run chatbot
python main.py
```

## Configuration

Edit `config.json` or `.env` to customize:
- Neo4j connection
- LLM settings (Ollama/OpenAI)
- Session persistence

## Components

{chr(10).join(f'- {c}' for c in template_info['components'])}

## License

Your choice - this is your project!
"""

    readme_path = project_dir / "README.md"
    readme_path.write_text(readme)
    print("✅ Created README.md")


def smart_llm_setup() -> dict:
    """
    Smart LLM setup - get user running with an LLM as FAST as possible.

    Priority order:
    1. Check if they already have API keys - use immediately!
    2. Ask preference (local vs cloud)
    3. If cloud + have keys -> instant start
    4. If local -> guide Ollama setup
    5. Once ANY LLM works -> continue with rest of setup

    Returns:
        dict with 'provider', 'model_code', 'ready' status
    """
    import os
    import shutil
    import subprocess

    print(
        """
================================================================================
                         LLM SETUP - GET RUNNING FAST
================================================================================

Agentic Brain needs an LLM (AI model) to work. Let's set one up now.

I'll check what you already have, then get you running in under a minute.
"""
    )

    # Step 1: Check what's already available
    print("Checking your current setup...\n")

    available = []

    # Check for API keys
    if os.environ.get("ANTHROPIC_API_KEY"):
        available.append(("CL", "Claude", "API key found in environment"))
    if os.environ.get("OPENAI_API_KEY"):
        available.append(("OP", "OpenAI", "API key found in environment"))
    if os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"):
        available.append(("GO", "Gemini", "API key found in environment"))
    if os.environ.get("GROQ_API_KEY"):
        available.append(("GR", "Groq", "API key found in environment"))

    # Check for Ollama
    ollama_running = False
    try:
        import urllib.request

        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=2) as resp:
            if resp.status == 200:
                ollama_running = True
                available.append(("L1", "Local (Ollama)", "Running at localhost:11434"))
    except Exception:
        pass

    # Check if Ollama is installed but not running
    ollama_installed = shutil.which("ollama") is not None

    if available:
        print("Great news! I found these LLM options already configured:\n")
        for code, name, status in available:
            print(f"  {code} - {name}: {status}")
        print()

        # Recommend fastest option
        if any(code == "GR" for code, _, _ in available):
            recommended = "GR"
            reason = "fastest free cloud"
        elif any(code == "L1" for code, _, _ in available):
            recommended = "L1"
            reason = "local, no internet needed"
        elif any(code == "GO" for code, _, _ in available):
            recommended = "GO"
            reason = "free Google"
        elif any(code == "CL" for code, _, _ in available):
            recommended = "CL"
            reason = "best quality"
        else:
            recommended = available[0][0]
            reason = "already configured"

        print(f"Recommended: {recommended} ({reason})\n")

        choice = input(f"Use {recommended}? [Y/n] or enter different code: ").strip()

        if not choice or choice.lower() == "y":
            selected = recommended
        elif choice.upper() in [a[0] for a in available]:
            selected = choice.upper()
        else:
            selected = recommended

        print(f"\nUsing {selected}. You're ready to go!\n")
        return {"provider": selected, "model_code": selected, "ready": True}

    # Step 2: Nothing found - guide them
    print("No LLM configured yet. Let's fix that!\n")

    print(
        """Which option works best for you?

  1. LOCAL  - Download a model (2GB, runs offline, FREE forever)
  2. CLOUD  - Use API key you already have (instant, paid)
  3. FREE   - Get free API key (Gemini or Groq, takes 2 mins)
  4. SKIP   - I'll configure LLM later manually

Local (option 1) is recommended - it ALWAYS works, even offline.
"""
    )

    choice = input("Enter 1, 2, 3, or 4 [1]: ").strip() or "1"

    if choice == "4":
        print("\nOK! You can run 'agentic setup-llm' later to configure.\n")
        return {"provider": None, "model_code": None, "ready": False}

    if choice == "1":
        # Local LLM setup
        print("\nSetting up local LLM (Ollama)...\n")

        if not ollama_installed:
            print("Ollama not found. Install it from: https://ollama.ai\n")

            # Platform-specific install
            import platform

            system = platform.system().lower()

            if system == "darwin":
                print("On Mac, run: brew install ollama")
            elif system == "linux":
                print("On Linux, run: curl -fsSL https://ollama.com/install.sh | sh")
            elif system == "windows":
                print("On Windows, download from: https://ollama.com/download/windows")

            print("\nAfter installing, run this installer again.\n")
            return {"provider": "L1", "model_code": "L1", "ready": False}

        # Ollama installed, check if running
        if not ollama_running:
            print("Starting Ollama...")
            try:
                subprocess.Popen(
                    ["ollama", "serve"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                import time

                time.sleep(2)
                print("Ollama started!\n")
            except Exception:
                print("Please start Ollama manually: ollama serve\n")

        # Pull the model
        print("Downloading L1 model (llama3.2:3b, about 2GB)...")
        print("This may take a few minutes on first run.\n")

        try:
            subprocess.run(["ollama", "pull", "llama3.2:3b"], check=True)
            print("\nLocal LLM ready! Using L1.\n")
            return {"provider": "L1", "model_code": "L1", "ready": True}
        except subprocess.CalledProcessError:
            print("\nDownload failed. Check internet connection.\n")
            print("You can try later: ollama pull llama3.2:3b\n")
            return {"provider": "L1", "model_code": "L1", "ready": False}

    if choice == "2":
        # Cloud API key
        print(
            """
Which cloud provider do you have an API key for?

  CL - Claude (Anthropic) - https://console.anthropic.com
  OP - OpenAI - https://platform.openai.com
  GO - Gemini (Google) - https://ai.google.dev
  GR - Groq - https://console.groq.com
"""
        )
        provider = input("Enter CL, OP, GO, or GR: ").strip().upper()

        if provider not in ["CL", "OP", "GO", "GR"]:
            provider = "CL"  # default

        env_var_map = {
            "CL": "ANTHROPIC_API_KEY",
            "OP": "OPENAI_API_KEY",
            "GO": "GOOGLE_API_KEY",
            "GR": "GROQ_API_KEY",
        }

        env_var = env_var_map[provider]
        print(f"\nEnter your {env_var} (or paste it):")
        api_key = input("> ").strip()

        if api_key:
            # Save to .env or environment
            home = Path.home()
            env_file = home / ".agentic" / ".env"
            env_file.parent.mkdir(parents=True, exist_ok=True)

            with open(env_file, "a") as f:
                f.write(f"\n{env_var}={api_key}\n")

            # Also set in current environment
            os.environ[env_var] = api_key

            print(f"\nAPI key saved! Using {provider}.\n")
            return {"provider": provider, "model_code": provider, "ready": True}
        else:
            print("\nNo key entered. You can add it later in .env\n")
            return {"provider": provider, "model_code": provider, "ready": False}

    if choice == "3":
        # Free API key guide
        print(
            """
================================================================================
                        GET A FREE API KEY (2 MINUTES)
================================================================================

Option A: GROQ (Recommended - Fastest)
--------------------------------------
1. Go to: https://console.groq.com
2. Sign up with Google or GitHub (free)
3. Click "API Keys" in sidebar
4. Click "Create API Key"
5. Copy the key (starts with gsk_)

Option B: GEMINI (Google - Very generous free tier)
---------------------------------------------------
1. Go to: https://ai.google.dev
2. Click "Get API key in Google AI Studio"
3. Sign in with Google account
4. Click "Create API key"
5. Copy the key (starts with AIza)

================================================================================
"""
        )
        print("Which did you sign up for?")
        provider = input("Enter GR (Groq) or GO (Gemini): ").strip().upper()

        if provider not in ["GR", "GO"]:
            provider = "GR"

        env_var = "GROQ_API_KEY" if provider == "GR" else "GOOGLE_API_KEY"
        print(f"\nPaste your {env_var}:")
        api_key = input("> ").strip()

        if api_key:
            home = Path.home()
            env_file = home / ".agentic" / ".env"
            env_file.parent.mkdir(parents=True, exist_ok=True)

            with open(env_file, "a") as f:
                f.write(f"\n{env_var}={api_key}\n")

            os.environ[env_var] = api_key

            print(f"\nFree API key saved! Using {provider}.\n")
            return {"provider": provider, "model_code": provider, "ready": True}
        else:
            print("\nNo key entered. You can add it later.\n")
            return {"provider": provider, "model_code": provider, "ready": False}

    # Fallback
    return {"provider": None, "model_code": None, "ready": False}


def run_installer(mode: Optional[str] = None, project_dir: Optional[Path] = None):
    """Run the installer."""
    print_banner()

    # Choose template
    if mode and mode in TEMPLATES:
        template = mode
        print(f"\n📦 Using template: {TEMPLATES[template]['name']}")
    else:
        template = choose_template()

    # Get project directory
    proj_dir = Path(project_dir) if project_dir else get_project_dir()

    # Get Neo4j config
    neo4j_config = get_neo4j_config()

    # Confirm
    print("\n" + "=" * 50)
    print("📋 Installation Summary")
    print("=" * 50)
    print(f"   Template:  {TEMPLATES[template]['name']}")
    print(f"   Directory: {proj_dir}")
    print(f"   Neo4j:     {neo4j_config['uri']}")
    print()

    confirm = input("Proceed with installation? [Y/n]: ").strip().lower()
    if confirm and confirm != "y":
        print("Installation cancelled.")
        return

    # Create project
    print("\n🚀 Installing...\n")

    create_project_structure(proj_dir, template)
    create_config_file(proj_dir, template, neo4j_config)
    create_env_file(proj_dir, neo4j_config)
    create_schema_file(proj_dir, template)
    create_main_file(proj_dir, template)
    create_readme(proj_dir, template)

    # Success message
    print(
        f"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║  ✅ Installation Complete!                                   ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝

Next steps:

  1. cd {proj_dir}
  2. pip install agentic-brain
  3. docker-compose up -d  # Start Neo4j
  4. python main.py        # Run your chatbot

Documentation: https://github.com/joseph-webber/agentic-brain

Happy building! 🚀
"""
    )


def main():
    parser = argparse.ArgumentParser(
        description="Agentic Brain Installer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Templates:
  minimal   - Clean chatbot for any business
  retail    - E-commerce with inventory & orders
  support   - Customer support with ticketing
  enterprise - Multi-tenant with audit logging

Examples:
  python -m agentic_brain.installer
  python -m agentic_brain.installer --mode minimal
  python -m agentic_brain.installer --mode retail --dir ./my_store
        """,
    )

    parser.add_argument(
        "--mode", "-m", choices=list(TEMPLATES.keys()), help="Installation template"
    )

    parser.add_argument("--dir", "-d", type=Path, help="Project directory")

    parser.add_argument(
        "--non-interactive", "-y", action="store_true", help="Use defaults, no prompts"
    )

    args = parser.parse_args()

    run_installer(mode=args.mode, project_dir=args.dir)


def show_llm_help():
    """
    Display LLM model selection help and documentation.

    Shows all available model codes, what each is good for, how to switch,
    fallback behavior, and cost information. Designed for accessibility
    with screen readers - plain text, no emoji dependencies.
    """
    help_text = """
================================================================================
                      AGENTIC BRAIN - LLM MODELS HELP
================================================================================

QUICK START:
  Each LLM is identified by a short code like L1, CL, OP, GO, or GR.
  Use the code to select which model to use for your tasks.

NAMING PATTERN:
  [PROVIDER][TIER]

  Provider (2 letters):
    L  = Local (Ollama) - runs on your computer
    CL = Claude (Anthropic) - best for reasoning
    OP = OpenAI - best for coding
    GO = Gemini (Google) - free fast model
    GR = Groq - fastest cloud, free

  Tier (number):
    (blank) or 1 = Best/default for that provider
    2 = Cheap/fast version
    3 = Premium/special version
    4 = Embeddings only (not for chat)

================================================================================
                         LOCAL MODELS (FREE, NO INTERNET)
================================================================================

L1 - llama3.2:3b
  Best for: Quick drafts, simple Q&A, testing
  Speed: Very fast
  Cost: FREE
  Good with: When you need instant response, don't care about quality

L2 - llama3.1:8b
  Best for: Reasoning, code, complex tasks
  Speed: Fast
  Cost: FREE
  Good with: When you want better quality and have a few seconds
  Fallback to: L2 if cloud models fail

L3 - mistral:7b
  Best for: Creative writing, European language tasks
  Speed: Fast
  Cost: FREE
  Good with: Alternative to L2, different model architecture

L4 - nomic-embed-text
  Best for: Search, document retrieval, embeddings only
  Speed: Very fast
  Cost: FREE
  Important: Cannot do chat, only used for vector search in RAG

================================================================================
                    CLAUDE (ANTHROPIC) - BEST FOR REASONING
================================================================================

CL or CL1 - Claude Sonnet 4
  Best for: Complex reasoning, analysis, creative tasks
  Speed: Fast
  Cost: Moderate ($$$ - pay per token)
  Good with: When you need excellent quality and reasoning
  Fallback to: L2 if Claude is unavailable or rate limited

CL2 - Claude Haiku
  Best for: Budget tasks, fast responses
  Speed: Very fast
  Cost: Cheap ($ - lowest cost Claude)
  Good with: When speed and cost matter more than reasoning
  Fallback to: L1 if Haiku is unavailable

CL3 - Claude Opus 4
  Best for: Maximum quality, research, difficult problems
  Speed: Slow
  Cost: Expensive ($$$$)
  Good with: When you absolutely need the best answer
  Fallback to: CL if Opus is unavailable

================================================================================
                         OPENAI - BEST FOR CODING
================================================================================

OP or OP1 - GPT-4o
  Best for: Coding, technical tasks, tools and APIs
  Speed: Fast
  Cost: Moderate ($$$ - pay per token)
  Good with: When you need excellent coding ability
  Fallback to: L2 if OpenAI is unavailable

OP2 - GPT-4o-mini
  Best for: Budget coding, simple tasks, fast responses
  Speed: Very fast
  Cost: Cheap ($ - much cheaper than GPT-4o)
  Good with: When speed and cost matter for coding
  Fallback to: L1 if GPT-4o-mini is unavailable

OP3 - o1 (Reasoning Model)
  Best for: Deep thinking, complex math, research, difficult problems
  Speed: Slow
  Cost: Expensive ($$$$)
  Good with: When you have time and need exceptional reasoning
  Fallback to: OP if reasoning fails or times out

================================================================================
                       GEMINI (GOOGLE) - FREE FAST
================================================================================

GO or GO1 - Gemini Flash 2.5
  Best for: Quick answers, general purpose, free tier
  Speed: Very fast
  Cost: FREE (generous free tier from Google)
  Good with: When you want free cloud speed
  Fallback to: L1 if Gemini is unavailable

GO2 - Gemini Pro 2.5
  Best for: Better quality than Flash, still reasonable cost
  Speed: Fast
  Cost: Moderate ($$)
  Good with: When you need better quality than Flash
  Fallback to: GO if Pro is unavailable

================================================================================
                        GROQ - FASTEST CLOUD, FREE
================================================================================

GR or GR1 - Llama 70B via Groq
  Best for: Blazing fast responses, free tier, general purpose
  Speed: Extremely fast
  Cost: FREE (generous free tier from Groq)
  Good with: When you need fastest possible response for free
  Fallback to: L1 if Groq is unavailable

GR2 - Mixtral via Groq
  Best for: Alternative to Llama, different capabilities, fast
  Speed: Very fast
  Cost: FREE
  Good with: When you want variety while staying free and fast
  Fallback to: L1 if Mixtral is unavailable

================================================================================
                          HOW TO SWITCH MODELS
================================================================================

To use a model in your code:

  from agentic_brain import router

  # Use local fast model
  response = router.chat("L1", "Quick question?")

  # Use Claude for better reasoning
  response = router.chat("CL", "Complex problem to solve")

  # Use OpenAI for coding
  response = router.chat("OP", "Write Python function for...")

  # Use free fast models
  response = router.chat("GR", "Answer this quickly")
  response = router.chat("GO", "Another quick answer")

In configuration or environment variables:

  # In config.json
  {"model": "L2"}

  # Or in .env
  LLM_MODEL=CL

================================================================================
                         FALLBACK BEHAVIOR
================================================================================

Each cloud model has a fallback if it fails or is rate limited:

  CL, CL2, CL3 -> Falls back to L2 or L1 (local models)
  OP, OP2, OP3 -> Falls back to L2 or L1 (local models)
  GO, GO2      -> Falls back to L1 (local models)
  GR, GR2      -> Falls back to L1 (local models)
  L1, L2, L3   -> No fallback (local has no internet)

This means your chatbot never crashes - worst case it uses local models.

================================================================================
                           COST SUMMARY
================================================================================

FREE (no payment needed):
  L1, L2, L3, L4 - Local Ollama (runs on your computer)
  GO, GO1        - Gemini Flash (Google's free tier)
  GR, GR1, GR2   - Groq (Groq's free tier)

CHEAP ($ - very affordable):
  CL2            - Claude Haiku
  OP2            - GPT-4o-mini

MODERATE ($$$):
  CL, CL1        - Claude Sonnet
  OP, OP1        - GPT-4o
  GO2            - Gemini Pro

EXPENSIVE ($$$$):
  CL3            - Claude Opus
  OP3            - o1

Note: Prices change. Check provider websites for current rates.

================================================================================
                         CHOOSING YOUR MODEL
================================================================================

Pick based on your use case:

For Speed:
  1. GR (Groq) - Fastest cloud, free
  2. GO (Gemini) - Very fast, free
  3. L1 - Fast local, free
  4. OP2 - Fast cloud, cheap

For Quality:
  1. CL3 (Opus) - Best reasoning
  2. CL (Sonnet) - Excellent reasoning
  3. OP (GPT-4o) - Excellent coding
  4. OP3 (o1) - Deep thinking

For Cost:
  1. L1, L2, L3 - Free (local)
  2. GR - Free (cloud, fast)
  3. GO - Free (cloud, Google)
  4. CL2 - Cheap Claude
  5. OP2 - Cheap OpenAI

For Reliability (with fallback):
  1. CL - Claude with L2 fallback
  2. OP - OpenAI with L2 fallback
  3. GR - Groq with L1 fallback
  4. L2 - Local always works

================================================================================
                         SCREEN READER NOTES
================================================================================

This help is designed for VoiceOver and NVDA screen readers:

- No emoji or special symbols (they read as individual characters)
- Plain ASCII characters for structure (-, =, spaces)
- Section headers marked with multiple equals signs
- Numbered and bulleted lists for clarity
- Code examples in simple format

If you need audio help, ask your assistant for detailed explanations.

================================================================================
"""
    print(help_text)


def show_llm_tutorial():
    """
    Quick walkthrough tutorial for LLM model selection and switching.

    Guides users through choosing a model for their first task, understanding
    costs, and switching models. Screen reader friendly with plain text.
    """
    tutorial_text = """
================================================================================
                    QUICK START - CHOOSING YOUR FIRST MODEL
================================================================================

Welcome to Agentic Brain!

This tutorial will help you pick your first LLM model in about 2 minutes.

================================================================================
                              STEP 1: YOUR GOAL
================================================================================

What do you want to do first?

A) Quick test or demo
   Use: L1 (local, instant)
   Why: Free, no setup, instant response

B) Good quality chat for your business
   Use: L2 (local) or GR (free cloud)
   Why: L2 is free and good, GR is free and fast

C) Best possible answers (willing to pay)
   Use: CL (Claude) or OP (OpenAI)
   Why: Excellent reasoning and quality

D) Coding and technical tasks
   Use: OP (OpenAI GPT-4o)
   Why: Best at code generation and technical problems

E) Budget conscious (free cloud)
   Use: GO (Gemini) or GR (Groq)
   Why: Both free with generous limits

================================================================================
                           STEP 2: YOUR SETUP
================================================================================

Local models (L1, L2, L3):
  1. Install Ollama from https://ollama.ai
  2. Run: ollama pull llama3.2:3b
  3. Start: ollama serve
  4. Models ready - no API key needed!

Cloud models (CL, OP, GO, GR):
  You need ONE of these:

  - Claude: Get API key from https://console.anthropic.com
  - OpenAI: Get API key from https://platform.openai.com
  - Gemini: Get API key from https://ai.google.dev
  - Groq: Get API key from https://console.groq.com

  Set in environment or .env file

================================================================================
                        STEP 3: YOUR FIRST TASK
================================================================================

Try this now:

  from agentic_brain import router

  # Pick a model from Step 1 (e.g., L1, GR, CL, OP)
  response = router.chat("L1", "What's 2 + 2?")
  print(response)

If that works, great! Your setup is correct.

If it fails:
  - Check model is installed/key is set
  - Check internet connection
  - Try fallback model (e.g., L1 if cloud failed)

================================================================================
                       STEP 4: UNDERSTANDING SPEED
================================================================================

Response time matters. Different models respond at different speeds:

Local Models (Instant):
  L1 - Ultra fast (3 seconds for most responses)
  L2 - Fast (5 seconds for complex tasks)
  L3 - Fast (5 seconds, same speed as L2)

Free Cloud (Very Fast):
  GR - Blazing (1-2 seconds)
  GO - Fast (2-3 seconds)

Paid Cloud (Fast):
  CL2 - Fast (2-3 seconds)
  OP2 - Fast (2-3 seconds)
  CL - Medium (3-5 seconds)
  OP - Medium (3-5 seconds)

Slow (For Complex Problems):
  OP3 - Slow (30-60 seconds, very thorough)
  CL3 - Slow (5-10 seconds for complex tasks)

For interactive chatbots, use fast models (L1, L2, GR, GO, CL2, OP2).

================================================================================
                        STEP 5: UNDERSTANDING COST
================================================================================

Free Options (No payment):
  L1, L2, L3 - Local Ollama
  GR - Groq (very generous free tier)
  GO - Gemini Flash (Google's free tier)

  These work great for most applications. No credit card needed.

Budget Options ($ - very affordable):
  CL2 - Claude Haiku
  OP2 - GPT-4o-mini

  Good if you want cloud quality at low cost.

Standard Options ($$):
  CL - Claude Sonnet
  OP - GPT-4o
  GO2 - Gemini Pro

  Excellent quality, moderate cost (depends on usage).

Premium Options ($$$$):
  CL3 - Claude Opus
  OP3 - o1 (most expensive)

  Best quality, higher cost. Use for important tasks.

Rule of thumb:
  - For testing: Use free models (L1, GR, GO)
  - For production: Use L2 + paid backup (CL or OP)
  - For budget: Use GR or GO (free cloud)
  - For best quality: Use CL or OP (small cost)

================================================================================
                       STEP 6: SWITCHING MODELS
================================================================================

You don't have to pick one forever. Switch anytime:

  # Monday: Try local
  response = router.chat("L1", "question")

  # Tuesday: Try cloud free
  response = router.chat("GR", "question")

  # Wednesday: Try Claude for quality
  response = router.chat("CL", "question")

Each task can use a different model. Your code stays the same.

Common pattern:
  - Use L2 for most tasks (free, good)
  - Use CL for important/complex tasks (small cost)
  - Fall back to L1 if anything fails (always works)

In config:
  {
    "default_model": "L2",
    "fast_model": "L1",
    "quality_model": "CL"
  }

================================================================================
                      STEP 7: FIRST REAL APPLICATION
================================================================================

Now you're ready. Here's a template for your first bot:

  from agentic_brain import router, Neo4jMemory, ChatConfig

  # Choose one: L1, L2, GR, GO, CL, OP
  model = "L2"  # Free, good quality

  # Create memory (stores conversations)
  memory = Neo4jMemory()

  # Create config
  config = ChatConfig(
      persist_sessions=True,
      use_memory=True,
      temperature=0.7
  )

  # Use it
  response = router.chat(model, "Your question here")
  print(response)

That's it! You now have a working AI chatbot.

================================================================================
                           QUICK REFERENCE
================================================================================

Need speed?          -> Use GR (Groq) or L1 (local)
Need quality?        -> Use CL (Claude) or OP (OpenAI)
Need free?           -> Use L2 (local), GR, or GO
Need coding help?    -> Use OP (OpenAI)
Not sure?            -> Use L2 (free, good balance)

Codes to remember:
  L1 - Quick local
  L2 - Good quality local
  GR - Free fast cloud
  GO - Free Google
  CL - Best Claude
  OP - Best OpenAI

================================================================================
                              YOU'RE SET!
================================================================================

Pick a model from this tutorial and try it:

  from agentic_brain import router

  # Replace "L2" with your chosen model code
  response = router.chat("L2", "Hello AI!")
  print(response)

For full documentation, see: show_llm_help()

Questions? Check the model_aliases.py file for complete details.

Happy building!

================================================================================
"""
    print(tutorial_text)


if __name__ == "__main__":
    main()
