#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
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

import os
import sys
import json
import shutil
import argparse
from pathlib import Path
from typing import Optional, Dict, List, Any

__all__ = [
    "run_installer",
    "main",
]


# Installation templates
TEMPLATES = {
    "minimal": {
        "name": "Minimal",
        "description": "Clean chatbot ready for any business. No domain-specific code.",
        "components": ["chat", "memory", "session"],
        "examples": ["simple_chat.py"],
        "neo4j_schema": "minimal"
    },
    "retail": {
        "name": "Retail / E-Commerce",
        "description": "Online store with inventory, orders, customers, and support bot.",
        "components": ["chat", "memory", "session", "rag", "business.retail"],
        "examples": ["simple_chat.py", "retail_bot.py", "inventory_query.py"],
        "neo4j_schema": "retail"
    },
    "support": {
        "name": "Customer Support",
        "description": "Support ticketing with knowledge base and escalation.",
        "components": ["chat", "memory", "session", "rag", "business.support"],
        "examples": ["simple_chat.py", "support_bot.py"],
        "neo4j_schema": "support"
    },
    "enterprise": {
        "name": "Enterprise",
        "description": "Full features with multi-tenant isolation and audit logging.",
        "components": ["chat", "memory", "session", "rag", "business.enterprise"],
        "examples": ["simple_chat.py", "enterprise_bot.py"],
        "neo4j_schema": "enterprise"
    }
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
"""
}


def print_banner():
    """Print installer banner."""
    print("""
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
    """)


def choose_template() -> str:
    """Interactive template selection."""
    print("\n📦 Choose your installation template:\n")
    
    templates = list(TEMPLATES.items())
    for i, (key, template) in enumerate(templates, 1):
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
    
    if user_dir:
        project_dir = Path(user_dir).expanduser().resolve()
    else:
        project_dir = default_dir
    
    return project_dir


def get_neo4j_config() -> Dict[str, str]:
    """Get Neo4j connection details."""
    print("\n🔗 Neo4j Configuration")
    print("   Press Enter for defaults\n")
    
    uri = input("   URI [bolt://localhost:7687]: ").strip() or "bolt://localhost:7687"
    user = input("   Username [neo4j]: ").strip() or "neo4j"
    password = input("   Password [password]: ").strip() or "password"
    
    return {
        "uri": uri,
        "user": user,
        "password": password
    }


def create_project_structure(project_dir: Path, template: str):
    """Create project directory structure."""
    template_info = TEMPLATES[template]
    
    # Create directories
    dirs = [
        project_dir,
        project_dir / "src",
        project_dir / "examples",
        project_dir / "docs",
        project_dir / "tests",
        project_dir / "data",
        project_dir / "sessions"
    ]
    
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    
    print(f"\n✅ Created project structure at {project_dir}")


def create_config_file(project_dir: Path, template: str, neo4j_config: Dict[str, str]):
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
            "session_dir": str(project_dir / "sessions")
        },
        "memory": {
            "enabled": True,
            "threshold": 0.7
        }
    }
    
    config_path = project_dir / "config.json"
    config_path.write_text(json.dumps(config, indent=2))
    print(f"✅ Created config.json")


def create_env_file(project_dir: Path, neo4j_config: Dict[str, str]):
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
    print(f"✅ Created .env file")


def create_schema_file(project_dir: Path, template: str):
    """Create Neo4j schema file."""
    schema = NEO4J_SCHEMAS.get(template, NEO4J_SCHEMAS["minimal"])
    
    schema_path = project_dir / "schema.cypher"
    schema_path.write_text(schema)
    print(f"✅ Created schema.cypher")


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
    print(f"✅ Created main.py")


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
cat schema.cypher | cypher-shell -u neo4j -p password

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
    print(f"✅ Created README.md")


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
    if project_dir:
        proj_dir = Path(project_dir)
    else:
        proj_dir = get_project_dir()
    
    # Get Neo4j config
    neo4j_config = get_neo4j_config()
    
    # Confirm
    print(f"\n" + "="*50)
    print(f"📋 Installation Summary")
    print(f"="*50)
    print(f"   Template:  {TEMPLATES[template]['name']}")
    print(f"   Directory: {proj_dir}")
    print(f"   Neo4j:     {neo4j_config['uri']}")
    print()
    
    confirm = input("Proceed with installation? [Y/n]: ").strip().lower()
    if confirm and confirm != 'y':
        print("Installation cancelled.")
        return
    
    # Create project
    print(f"\n🚀 Installing...\n")
    
    create_project_structure(proj_dir, template)
    create_config_file(proj_dir, template, neo4j_config)
    create_env_file(proj_dir, neo4j_config)
    create_schema_file(proj_dir, template)
    create_main_file(proj_dir, template)
    create_readme(proj_dir, template)
    
    # Success message
    print(f"""
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
""")


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
        """
    )
    
    parser.add_argument(
        "--mode", "-m",
        choices=list(TEMPLATES.keys()),
        help="Installation template"
    )
    
    parser.add_argument(
        "--dir", "-d",
        type=Path,
        help="Project directory"
    )
    
    parser.add_argument(
        "--non-interactive", "-y",
        action="store_true",
        help="Use defaults, no prompts"
    )
    
    args = parser.parse_args()
    
    run_installer(mode=args.mode, project_dir=args.dir)


if __name__ == "__main__":
    main()
