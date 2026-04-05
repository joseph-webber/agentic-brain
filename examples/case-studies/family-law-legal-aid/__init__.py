#!/usr/bin/env python3
"""
Australian Family Law Legal Aid - Case Study
=============================================

A comprehensive RAG-powered legal aid chatbot framework for Australian
family law matters.

24/7 CLIENT ACCESS
------------------
Parents and children can ask questions anytime via chatbot:
- Simple questions → Instant guidance
- Complex questions → Flagged for lawyer follow-up
- Emergencies → Immediate safety resources

DESIGNED FOR
------------
- Legal Aid services (Legal Aid NSW, Victoria Legal Aid, etc.)
- Family law firms (familylaw.com.au, etc.)
- Community Legal Centres
- Court support services

NOT FOR
-------
- Individual users seeking legal advice
- Self-help divorce/separation
- Replacing qualified lawyers

MODULES
-------
- family_law_bot: Main chatbot with RAG integration
- knowledge_base: RAG knowledge system for family law
- case_manager: Lightweight case tracking (CMMS-compatible)
- cmms_adapters: Integration with Dynamics 365, Alfresco, etc.
- templates: Document structure guidance

EXAMPLE USAGE
-------------
    from family_law_legal_aid import FamilyLawBot, FamilyLawKnowledgeBase

    # Legal firm builds their knowledge base
    kb = FamilyLawKnowledgeBase(organization="Smith Family Law")
    kb.add_documents_from_path("/firm/legal-resources", ...)
    kb.build_index()

    # Create chatbot with firm's knowledge
    bot = FamilyLawBot(
        knowledge_base=kb,
        supervised_mode=True,  # Flag complex queries for lawyer
    )

    # Client asks question at 2am
    response = bot.chat("What should I expect at my first court date?")

Copyright (C) 2025-2026 Joseph Webber / Iris Lumina
SPDX-License-Identifier: GPL-3.0-or-later

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
"""

__version__ = "1.0.0"
__author__ = "Joseph Webber / Iris Lumina"
__license__ = "GPL-3.0-or-later"

# Core imports
from .cmms_adapters import (
    AlfrescoAdapter,
    CaseStatus,
    CMMSAdapter,
    CMMSCase,
    CMMSDocument,
    CMMSEvent,
    CMMSRAGBridge,
    CMMSRegistry,
    Dynamics365Adapter,
    LocalCMMSAdapter,
    WorkflowAction,
)
from .knowledge_base import (
    FamilyLawKnowledgeBase,
    KnowledgeCategory,
    KnowledgeDocument,
    SearchResult,
    create_knowledge_base,
)


# Lazy imports for heavier modules
def get_family_law_bot():
    """Get FamilyLawBot class (lazy import)."""
    from .family_law_bot import FamilyLawBot

    return FamilyLawBot


def get_case_manager():
    """Get case management classes (lazy import)."""
    from .case_manager import (
        CasePhase,
        DeadlineTracker,
        DocumentTracker,
        FamilyLawCase,
    )

    return {
        "CasePhase": CasePhase,
        "FamilyLawCase": FamilyLawCase,
        "DeadlineTracker": DeadlineTracker,
        "DocumentTracker": DocumentTracker,
    }


def get_templates():
    """Get template guidance functions (lazy import)."""
    from .templates import (
        get_checklist,
        get_common_mistakes,
        get_filing_instructions,
        get_template_guidance,
    )

    return {
        "get_template_guidance": get_template_guidance,
        "get_checklist": get_checklist,
        "get_common_mistakes": get_common_mistakes,
        "get_filing_instructions": get_filing_instructions,
    }


__all__ = [
    # Version info
    "__version__",
    "__author__",
    "__license__",
    # Knowledge base
    "FamilyLawKnowledgeBase",
    "KnowledgeCategory",
    "KnowledgeDocument",
    "SearchResult",
    "create_knowledge_base",
    # CMMS adapters
    "CMMSAdapter",
    "CMMSCase",
    "CMMSDocument",
    "CMMSEvent",
    "CaseStatus",
    "WorkflowAction",
    "CMMSRegistry",
    "CMMSRAGBridge",
    "LocalCMMSAdapter",
    "Dynamics365Adapter",
    "AlfrescoAdapter",
    # Lazy loaders
    "get_family_law_bot",
    "get_case_manager",
    "get_templates",
]


# Quick summary for interactive use
def info():
    """Print module information."""
    print(
        f"""
╔══════════════════════════════════════════════════════════════════════╗
║  Australian Family Law Legal Aid - Case Study                        ║
║  Version: {__version__}                                                      ║
║  License: {__license__}                                              ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                      ║
║  24/7 CLIENT ACCESS via chatbot:                                     ║
║  • Parents and children ask questions anytime                        ║
║  • Simple → Instant guidance                                         ║
║  • Complex → Flagged for lawyer                                      ║
║  • Emergency → Safety resources                                      ║
║                                                                      ║
║  DESIGNED FOR: Legal Aid, Family Law Firms, Community Legal Centres ║
║  NOT FOR: Individual users seeking legal advice                      ║
║                                                                      ║
║  Modules:                                                            ║
║  • FamilyLawKnowledgeBase - RAG knowledge system                    ║
║  • FamilyLawBot - Main chatbot (get_family_law_bot())               ║
║  • CMMSAdapter - Dynamics 365, Alfresco integration                 ║
║  • Templates - Document guidance (get_templates())                   ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝
"""
    )
