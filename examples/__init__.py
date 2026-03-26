# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
Agentic Brain Examples
=======================

88 production-ready examples demonstrating agentic-brain capabilities.

Categories:
    - core: Fundamental patterns (chat, memory, streaming, multi-agent)
    - business: Business automation (email, invoices, warehouse)
    - enterprise: Professional solutions (skills, defence, government)
    - wordpress: WordPress/WooCommerce integration
    - ndis-disability: Australian disability services
    - industry: Sector-specific solutions
    - property: Property management
    - rag: Retrieval-Augmented Generation
    - customer-service: Customer-facing assistants
    - deployment: Deployment patterns

Usage:
    >>> from examples.core import simple_chat
    >>> from examples.enterprise import skills_graph

Note:
    Most examples require Ollama and/or Neo4j to be running.
    See the category README files for specific requirements.
"""

__version__ = "1.0.0"
__author__ = "Joseph Webber"

# Example categories
CATEGORIES = [
    "core",
    "business",
    "enterprise",
    "wordpress",
    "ndis-disability",
    "industry",
    "property",
    "rag",
    "customer-service",
    "deployment",
]
