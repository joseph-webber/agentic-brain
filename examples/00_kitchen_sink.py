#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Kitchen Sink Example Launcher
==============================

Interactive showcase of ALL 94 agentic-brain examples.
Browse categories, read descriptions, and launch examples directly!

Usage:
    python examples/00_kitchen_sink.py              # Interactive mode
    python examples/00_kitchen_sink.py --list       # List all examples
    python examples/00_kitchen_sink.py --random     # Run random example
    python examples/00_kitchen_sink.py --category core  # Browse category

Requirements:
    - pip install rich (optional, for beautiful output)
    - Ollama running for most examples
"""

import os
import random
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Try to import rich for beautiful output, fallback to plain text
try:
    from rich import box
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.table import Table

    RICH_AVAILABLE = True
    console = Console()
except ImportError:
    RICH_AVAILABLE = False
    console = None


# === Data Structures ===


@dataclass
class Example:
    """Represents a single example file."""

    filename: str
    number: str
    name: str
    description: str
    level: str  # beginner, intermediate, advanced
    category: str

    @property
    def path(self) -> Path:
        return EXAMPLES_DIR / self.category / self.filename

    def get_docstring(self) -> str:
        """Extract docstring from file."""
        try:
            content = self.path.read_text()
            if '"""' in content:
                start = content.index('"""') + 3
                end = content.index('"""', start)
                return content[start:end].strip()
        except Exception:
            pass
        return self.description


@dataclass
class Category:
    """Represents a category of examples."""

    name: str
    slug: str
    description: str
    icon: str
    examples: list


# === Configuration ===

EXAMPLES_DIR = Path(__file__).parent

CATEGORIES = {
    "core": Category(
        name="Core Features",
        slug="core",
        description="Fundamental agentic-brain capabilities: chat, memory, streaming, multi-agent",
        icon="🎯",
        examples=[
            Example(
                "01_simple_chat.py",
                "01",
                "Simple Chat",
                "Minimal chatbot in 5 lines",
                "beginner",
                "core",
            ),
            Example(
                "02_with_memory.py",
                "02",
                "Memory Chat",
                "Neo4j persistent memory",
                "beginner",
                "core",
            ),
            Example(
                "03_streaming.py",
                "03",
                "Streaming",
                "Real-time token streaming",
                "intermediate",
                "core",
            ),
            Example(
                "04_multi_user.py",
                "04",
                "Multi-User",
                "Isolated user sessions",
                "intermediate",
                "core",
            ),
            Example(
                "05_rag_basic.py",
                "05",
                "RAG Basic",
                "Document Q&A with retrieval",
                "intermediate",
                "core",
            ),
            Example(
                "06_custom_prompts.py",
                "06",
                "Custom Prompts",
                "Personas and system prompts",
                "intermediate",
                "core",
            ),
            Example(
                "06_cloud_loaders.py",
                "06b",
                "Cloud Loaders",
                "Load docs from S3, GCS, Azure",
                "intermediate",
                "core",
            ),
            Example(
                "07_multi_agent.py",
                "07",
                "Multi-Agent",
                "Crews and workflows",
                "advanced",
                "core",
            ),
            Example(
                "08_api_server.py",
                "08",
                "API Server",
                "FastAPI deployment",
                "advanced",
                "core",
            ),
            Example(
                "09_websocket.py",
                "09",
                "WebSocket",
                "Real-time WebSocket chat",
                "advanced",
                "core",
            ),
            Example(
                "10_with_auth.py",
                "10",
                "Auth",
                "JWT authentication",
                "advanced",
                "core",
            ),
            Example(
                "11_firebase_chat.py",
                "11",
                "Firebase",
                "Firebase real-time sync",
                "advanced",
                "core",
            ),
            Example(
                "12_with_tracing.py",
                "12",
                "Tracing",
                "Observability and tracing",
                "advanced",
                "core",
            ),
        ],
    ),
    "business": Category(
        name="Business Automation",
        slug="business",
        description="Email, invoices, warehouse, retail - automate business operations",
        icon="💼",
        examples=[
            Example(
                "13_email_automation.py",
                "13",
                "Email Automation",
                "AI email classification",
                "intermediate",
                "business",
            ),
            Example(
                "14_business_brain.py",
                "14",
                "Business Brain",
                "Knowledge graph CRM",
                "intermediate",
                "business",
            ),
            Example(
                "15_invoice_processor.py",
                "15",
                "Invoice Processor",
                "PDF invoice extraction",
                "intermediate",
                "business",
            ),
            Example(
                "16_warehouse_assistant.py",
                "16",
                "Warehouse",
                "Stock queries and picking",
                "intermediate",
                "business",
            ),
            Example(
                "17_qa_assistant.py",
                "17",
                "QA Assistant",
                "Quality control workflows",
                "intermediate",
                "business",
            ),
            Example(
                "18_packing_assistant.py",
                "18",
                "Packing",
                "Order packing workflows",
                "intermediate",
                "business",
            ),
            Example(
                "19_store_manager.py",
                "19",
                "Store Manager",
                "Sales and inventory dashboard",
                "intermediate",
                "business",
            ),
        ],
    ),
    "wordpress": Category(
        name="WordPress & WooCommerce",
        slug="wordpress",
        description="WordPress, WooCommerce, Divi - content and e-commerce AI assistants",
        icon="🛒",
        examples=[
            Example(
                "20_wordpress_assistant.py",
                "20",
                "WordPress Assistant",
                "Content management AI",
                "intermediate",
                "wordpress",
            ),
            Example(
                "21_woocommerce_orders.py",
                "21",
                "WooCommerce Orders",
                "Order processing automation",
                "intermediate",
                "wordpress",
            ),
            Example(
                "22_woocommerce_inventory.py",
                "22",
                "WooCommerce Inventory",
                "Stock management AI",
                "intermediate",
                "wordpress",
            ),
            Example(
                "23_woocommerce_analytics.py",
                "23",
                "WooCommerce Analytics",
                "Sales analytics dashboard",
                "intermediate",
                "wordpress",
            ),
            Example(
                "67_woo_electronics_catalog.py",
                "67",
                "Electronics Catalog",
                "Electronics product catalog",
                "advanced",
                "wordpress",
            ),
            Example(
                "71_woo_warehouse_ops.py",
                "71",
                "Warehouse Ops",
                "Full warehouse operations",
                "advanced",
                "wordpress",
            ),
            Example(
                "72_woo_shipping_logistics.py",
                "72",
                "Shipping Logistics",
                "Shipping and tracking",
                "advanced",
                "wordpress",
            ),
            Example(
                "73_woo_inventory_sync.py",
                "73",
                "Inventory Sync",
                "Multi-channel inventory sync",
                "advanced",
                "wordpress",
            ),
            Example(
                "75_wordpress_content_manager.py",
                "75",
                "Content Manager",
                "AI content creation",
                "advanced",
                "wordpress",
            ),
            Example(
                "76_divi_page_builder.py",
                "76",
                "Divi Builder",
                "Divi page builder AI",
                "advanced",
                "wordpress",
            ),
            Example(
                "77_wordpress_seo_assistant.py",
                "77",
                "SEO Assistant",
                "SEO optimization AI",
                "advanced",
                "wordpress",
            ),
            Example(
                "78_divi_ecommerce_theme.py",
                "78",
                "Divi E-commerce",
                "E-commerce theme builder",
                "advanced",
                "wordpress",
            ),
            Example(
                "79_woo_sales_dashboard.py",
                "79",
                "Sales Dashboard",
                "Real-time sales tracking",
                "advanced",
                "wordpress",
            ),
            Example(
                "80_woo_marketing_automation.py",
                "80",
                "Marketing Automation",
                "Marketing campaign AI",
                "advanced",
                "wordpress",
            ),
            Example(
                "81_woo_pricing_optimizer.py",
                "81",
                "Pricing Optimizer",
                "Dynamic pricing AI",
                "advanced",
                "wordpress",
            ),
        ],
    ),
    "deployment": Category(
        name="Deployment Patterns",
        slug="deployment",
        description="On-premise, hybrid, cloud-native, edge - deploy anywhere",
        icon="🚀",
        examples=[
            Example(
                "24_onpremise_private.py",
                "24",
                "On-Premise",
                "Private data deployment",
                "advanced",
                "deployment",
            ),
            Example(
                "25_hybrid_cloud.py",
                "25",
                "Hybrid Cloud",
                "Mixed on-prem + cloud",
                "advanced",
                "deployment",
            ),
            Example(
                "26_cloud_native.py",
                "26",
                "Cloud Native",
                "Kubernetes/serverless",
                "advanced",
                "deployment",
            ),
            Example(
                "27_edge_embedded.py",
                "27",
                "Edge/Embedded",
                "IoT and edge devices",
                "advanced",
                "deployment",
            ),
        ],
    ),
    "enterprise": Category(
        name="Enterprise Apps",
        slug="enterprise",
        description="IT helpdesk, HR, legal, knowledge base - enterprise solutions",
        icon="🏢",
        examples=[
            Example(
                "28_it_helpdesk.py",
                "28",
                "IT Helpdesk",
                "IT support automation",
                "advanced",
                "enterprise",
            ),
            Example(
                "29_hr_assistant.py",
                "29",
                "HR Assistant",
                "HR queries and onboarding",
                "advanced",
                "enterprise",
            ),
            Example(
                "30_legal_compliance.py",
                "30",
                "Legal Compliance",
                "Legal document analysis",
                "advanced",
                "enterprise",
            ),
            Example(
                "31_knowledge_wiki.py",
                "31",
                "Knowledge Wiki",
                "Enterprise knowledge base",
                "advanced",
                "enterprise",
            ),
            Example(
                "32_meeting_assistant.py",
                "32",
                "Meeting Assistant",
                "Meeting notes and actions",
                "advanced",
                "enterprise",
            ),
        ],
    ),
    "customer-service": Category(
        name="Customer Service",
        slug="customer-service",
        description="Live chat, FAQ, multilingual, voice IVR - customer support",
        icon="💬",
        examples=[
            Example(
                "33_live_chat_support.py",
                "33",
                "Live Chat",
                "Real-time chat support",
                "intermediate",
                "customer-service",
            ),
            Example(
                "34_faq_escalation.py",
                "34",
                "FAQ Escalation",
                "Smart FAQ with escalation",
                "intermediate",
                "customer-service",
            ),
            Example(
                "35_multilingual_support.py",
                "35",
                "Multilingual",
                "Multi-language support",
                "advanced",
                "customer-service",
            ),
            Example(
                "36_voice_ivr.py",
                "36",
                "Voice IVR",
                "Voice assistant / IVR",
                "advanced",
                "customer-service",
            ),
        ],
    ),
    "rag": Category(
        name="RAG Examples",
        slug="rag",
        description="Retrieval-Augmented Generation for documents, code, research",
        icon="📚",
        examples=[
            Example(
                "37_rag_documents.py",
                "37",
                "RAG Documents",
                "Document Q&A",
                "intermediate",
                "rag",
            ),
            Example(
                "38_rag_codebase.py",
                "38",
                "RAG Codebase",
                "Code understanding",
                "intermediate",
                "rag",
            ),
            Example(
                "39_rag_research.py",
                "39",
                "RAG Research",
                "Research paper analysis",
                "advanced",
                "rag",
            ),
            Example(
                "40_rag_catalog.py",
                "40",
                "RAG Catalog",
                "Product catalog search",
                "intermediate",
                "rag",
            ),
            Example(
                "41_rag_contracts.py",
                "41",
                "RAG Contracts",
                "Contract analysis",
                "advanced",
                "rag",
            ),
            Example(
                "42_rag_medical.py",
                "42",
                "RAG Medical",
                "Medical knowledge base",
                "advanced",
                "rag",
            ),
        ],
    ),
    "industry": Category(
        name="Industry Verticals",
        slug="industry",
        description="Real estate, travel, education, finance, healthcare, and more",
        icon="🏭",
        examples=[
            Example(
                "43_real_estate.py",
                "43",
                "Real Estate",
                "Property listings AI",
                "intermediate",
                "industry",
            ),
            Example(
                "44_travel_booking.py",
                "44",
                "Travel Booking",
                "Travel assistant",
                "intermediate",
                "industry",
            ),
            Example(
                "45_education_tutor.py",
                "45",
                "Education Tutor",
                "AI tutoring system",
                "intermediate",
                "industry",
            ),
            Example(
                "46_finance_banking.py",
                "46",
                "Finance/Banking",
                "Financial assistant",
                "advanced",
                "industry",
            ),
            Example(
                "47_healthcare_portal.py",
                "47",
                "Healthcare",
                "Patient portal AI",
                "advanced",
                "industry",
            ),
            Example(
                "48_hospitality.py",
                "48",
                "Hospitality",
                "Hotel/restaurant AI",
                "intermediate",
                "industry",
            ),
            Example(
                "49_automotive.py",
                "49",
                "Automotive",
                "Car dealership AI",
                "intermediate",
                "industry",
            ),
            Example(
                "50_insurance.py",
                "50",
                "Insurance",
                "Insurance assistant",
                "intermediate",
                "industry",
            ),
        ],
    ),
    "ndis-disability": Category(
        name="NDIS & Disability",
        slug="ndis-disability",
        description="NDIS providers, SDA housing, SIL - Australian disability services",
        icon="♿",
        examples=[
            Example(
                "51_ndis_provider.py",
                "51",
                "NDIS Provider",
                "Provider management",
                "advanced",
                "ndis-disability",
            ),
            Example(
                "52_ndis_participant.py",
                "52",
                "NDIS Participant",
                "Participant portal",
                "advanced",
                "ndis-disability",
            ),
            Example(
                "53_ndis_compliance.py",
                "53",
                "NDIS Compliance",
                "Compliance tracking",
                "advanced",
                "ndis-disability",
            ),
            Example(
                "54_ndis_support_coordinator.py",
                "54",
                "Support Coordinator",
                "Coordination tools",
                "advanced",
                "ndis-disability",
            ),
            Example(
                "60_sda_housing.py",
                "60",
                "SDA Housing",
                "Specialist housing",
                "advanced",
                "ndis-disability",
            ),
            Example(
                "61_sil_provider.py",
                "61",
                "SIL Provider",
                "Supported living",
                "advanced",
                "ndis-disability",
            ),
            Example(
                "62_ndis_housing_search.py",
                "62",
                "Housing Search",
                "Find SDA properties",
                "advanced",
                "ndis-disability",
            ),
            Example(
                "63_sda_financial_manager.py",
                "63",
                "SDA Finance",
                "Financial management",
                "advanced",
                "ndis-disability",
            ),
            Example(
                "64_sda_dashboard.py",
                "64",
                "SDA Dashboard",
                "Portfolio dashboard",
                "advanced",
                "ndis-disability",
            ),
            Example(
                "65_sda_investor_portal.py",
                "65",
                "SDA Investors",
                "Investor portal",
                "advanced",
                "ndis-disability",
            ),
            Example(
                "66_sda_compliance_tracker.py",
                "66",
                "SDA Compliance",
                "Compliance tracker",
                "advanced",
                "ndis-disability",
            ),
        ],
    ),
    "property": Category(
        name="Property Management",
        slug="property",
        description="Property managers, tenants, landlords, strata - real estate ops",
        icon="🏠",
        examples=[
            Example(
                "55_property_manager.py",
                "55",
                "Property Manager",
                "Property management AI",
                "intermediate",
                "property",
            ),
            Example(
                "56_tenant_portal.py",
                "56",
                "Tenant Portal",
                "Tenant self-service",
                "intermediate",
                "property",
            ),
            Example(
                "57_landlord_portal.py",
                "57",
                "Landlord Portal",
                "Landlord dashboard",
                "intermediate",
                "property",
            ),
            Example(
                "58_property_maintenance.py",
                "58",
                "Maintenance",
                "Maintenance requests",
                "intermediate",
                "property",
            ),
            Example(
                "59_strata_manager.py",
                "59",
                "Strata Manager",
                "Strata/body corporate",
                "intermediate",
                "property",
            ),
        ],
    ),
}


# === Helper Functions ===


def get_all_examples() -> list[Example]:
    """Get all examples from all categories."""
    examples = []
    for cat in CATEGORIES.values():
        examples.extend(cat.examples)
    return examples


def get_level_color(level: str) -> str:
    """Get color for skill level."""
    return {"beginner": "green", "intermediate": "yellow", "advanced": "red"}.get(
        level, "white"
    )


def get_level_emoji(level: str) -> str:
    """Get emoji for skill level."""
    return {"beginner": "🟢", "intermediate": "🟡", "advanced": "🔴"}.get(level, "⚪")


# === Display Functions ===


def print_header():
    """Print the header."""
    if RICH_AVAILABLE:
        console.print(
            Panel.fit(
                "[bold cyan]🧠 Agentic Brain Examples[/bold cyan]\n"
                "[dim]Interactive launcher for 70+ AI examples[/dim]",
                border_style="cyan",
            )
        )
    else:
        print("=" * 60)
        print("🧠 Agentic Brain Examples")
        print("Interactive launcher for 70+ AI examples")
        print("=" * 60)


def print_categories():
    """Print category overview."""
    if RICH_AVAILABLE:
        table = Table(title="📂 Categories", box=box.ROUNDED)
        table.add_column("#", style="dim", width=3)
        table.add_column("Category", style="cyan")
        table.add_column("Examples", justify="center")
        table.add_column("Description")

        for i, (slug, cat) in enumerate(CATEGORIES.items(), 1):
            table.add_row(
                str(i),
                f"{cat.icon} {cat.name}",
                str(len(cat.examples)),
                (
                    cat.description[:50] + "..."
                    if len(cat.description) > 50
                    else cat.description
                ),
            )
        console.print(table)
    else:
        print("\n📂 Categories:")
        print("-" * 60)
        for i, (slug, cat) in enumerate(CATEGORIES.items(), 1):
            print(f"  {i}. {cat.icon} {cat.name} ({len(cat.examples)} examples)")
        print()


def print_category_examples(category: Category):
    """Print examples in a category."""
    if RICH_AVAILABLE:
        table = Table(title=f"{category.icon} {category.name}", box=box.ROUNDED)
        table.add_column("#", style="dim", width=4)
        table.add_column("Example", style="cyan")
        table.add_column("Level", justify="center")
        table.add_column("Description")

        for ex in category.examples:
            level_color = get_level_color(ex.level)
            table.add_row(
                ex.number,
                ex.name,
                f"[{level_color}]{get_level_emoji(ex.level)} {ex.level}[/{level_color}]",
                ex.description,
            )
        console.print(table)
    else:
        print(f"\n{category.icon} {category.name}")
        print("-" * 60)
        for ex in category.examples:
            print(f"  {ex.number}. {ex.name} - {ex.description} [{ex.level}]")
        print()


def print_all_examples():
    """Print all examples grouped by category."""
    if RICH_AVAILABLE:
        for cat in CATEGORIES.values():
            print_category_examples(cat)
            console.print()
    else:
        for cat in CATEGORIES.values():
            print_category_examples(cat)


def print_example_detail(example: Example):
    """Print detailed info about an example."""
    docstring = example.get_docstring()

    if RICH_AVAILABLE:
        console.print(
            Panel(
                f"[bold]{example.name}[/bold] ({example.number})\n\n"
                f"[dim]Category:[/dim] {CATEGORIES[example.category].icon} {CATEGORIES[example.category].name}\n"
                f"[dim]Level:[/dim] {get_level_emoji(example.level)} {example.level}\n"
                f"[dim]File:[/dim] {example.path}\n\n"
                f"[bold]Description:[/bold]\n{docstring[:500]}{'...' if len(docstring) > 500 else ''}",
                title=f"Example {example.number}",
                border_style="cyan",
            )
        )
    else:
        print(f"\n{'=' * 60}")
        print(f"Example {example.number}: {example.name}")
        print(f"{'=' * 60}")
        print(f"Category: {CATEGORIES[example.category].name}")
        print(f"Level: {example.level}")
        print(f"File: {example.path}")
        print("\nDescription:")
        print(docstring[:500])
        print()


def run_example(example: Example):
    """Run an example."""
    if RICH_AVAILABLE:
        console.print(f"\n[bold green]▶ Running {example.filename}...[/bold green]\n")
    else:
        print(f"\n▶ Running {example.filename}...\n")

    subprocess.run([sys.executable, str(example.path)])


# === Interactive Mode ===


def interactive_menu():
    """Run the interactive menu."""
    print_header()

    while True:
        print_categories()

        if RICH_AVAILABLE:
            console.print(
                "[dim]Enter category number, 'q' to quit, or 'r' for random:[/dim]"
            )
        else:
            print("Enter category number, 'q' to quit, or 'r' for random:")

        try:
            choice = input(">>> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye! 👋")
            break

        if choice in ("q", "quit", "exit"):
            print("Goodbye! 👋")
            break

        if choice == "r":
            example = random.choice(get_all_examples())
            print_example_detail(example)
            if input("Run this example? (y/n): ").lower() == "y":
                run_example(example)
            continue

        try:
            cat_idx = int(choice) - 1
            cat_slug = list(CATEGORIES.keys())[cat_idx]
            category = CATEGORIES[cat_slug]
        except (ValueError, IndexError):
            print("Invalid choice. Try again.")
            continue

        # Category selected - show examples
        print_category_examples(category)

        if RICH_AVAILABLE:
            console.print("[dim]Enter example number, 'b' to go back:[/dim]")
        else:
            print("Enter example number, 'b' to go back:")

        try:
            ex_choice = input(">>> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye! 👋")
            break

        if ex_choice == "b":
            continue

        # Find example by number
        example = None
        for ex in category.examples:
            if ex.number == ex_choice or ex.number == ex_choice.zfill(2):
                example = ex
                break

        if not example:
            print("Invalid example number. Try again.")
            continue

        # Show example detail
        print_example_detail(example)

        if RICH_AVAILABLE:
            console.print("[dim]Press Enter to run, or 'b' to go back:[/dim]")
        else:
            print("Press Enter to run, or 'b' to go back:")

        try:
            run_choice = input(">>> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye! 👋")
            break

        if run_choice == "b":
            continue

        run_example(example)


# === CLI Modes ===


def list_mode():
    """List all examples."""
    print_header()
    print_all_examples()

    total = sum(len(cat.examples) for cat in CATEGORIES.values())
    if RICH_AVAILABLE:
        console.print(
            f"\n[bold]Total: {total} examples across {len(CATEGORIES)} categories[/bold]"
        )
    else:
        print(f"\nTotal: {total} examples across {len(CATEGORIES)} categories")


def random_mode():
    """Run a random example."""
    example = random.choice(get_all_examples())
    print_header()
    print_example_detail(example)
    run_example(example)


def category_mode(cat_slug: str):
    """Browse a specific category."""
    if cat_slug not in CATEGORIES:
        print(f"Unknown category: {cat_slug}")
        print(f"Available: {', '.join(CATEGORIES.keys())}")
        sys.exit(1)

    print_header()
    print_category_examples(CATEGORIES[cat_slug])


# === Main ===


def main():
    """Main entry point."""
    args = sys.argv[1:]

    if not args:
        interactive_menu()
    elif args[0] == "--list":
        list_mode()
    elif args[0] == "--random":
        random_mode()
    elif args[0] == "--category" and len(args) > 1:
        category_mode(args[1])
    elif args[0] in ("--help", "-h"):
        print(__doc__)
    else:
        print(f"Unknown argument: {args[0]}")
        print("Use --help for usage info")
        sys.exit(1)


if __name__ == "__main__":
    main()
