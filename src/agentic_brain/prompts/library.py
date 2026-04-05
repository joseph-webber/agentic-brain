# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""Pre-built prompt library for RAG workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from textwrap import dedent
from typing import Any

from .few_shot import FewShotCollection, FewShotExample
from .optimizer import PromptOptimizer
from .template import PromptTemplate


def _rag_examples() -> FewShotCollection:
    return FewShotCollection(
        title="RAG examples",
        examples=[
            FewShotExample(
                input_text="What is GraphRAG?",
                output_text=(
                    "GraphRAG combines vector retrieval with knowledge graphs to "
                    "answer questions using connected context."
                ),
                explanation="Ground the answer in the retrieved context and avoid invention.",
            ),
            FewShotExample(
                input_text="Rewrite: 'Tell me everything about sales.'",
                output_text="sales overview and supporting data",
                explanation="Convert broad requests into concise search-friendly queries.",
            ),
        ],
    )


def _build_default_templates() -> dict[str, PromptTemplate]:
    examples = _rag_examples().render()
    return {
        "rag.answer": PromptTemplate.from_string(
            "rag.answer",
            dedent(
                """
You are a retrieval-augmented assistant.
Use the retrieved context to answer the question.
If the context is insufficient, say so clearly.

Question:
{{ question }}

Retrieved context:
{{ context }}

{% if citations %}
Citations:
{{ citations }}
{% endif %}

{% if examples %}
Reference examples:
{{ examples }}
{% endif %}

Response requirements:
- Be concise and factual.
- Prefer information from the provided context.
- Do not invent missing facts.
"""
            ).strip(),
            variables={"examples": examples, "citations": ""},
            tags=("rag", "answer", "core"),
        ),
        "rag.rewrite_query": PromptTemplate.from_string(
            "rag.rewrite_query",
            dedent(
                """
Rewrite the user query into a short search query for retrieval.
Focus on concrete entities, topics, and key constraints.

User query:
{{ question }}

Return only the rewritten query.
"""
            ).strip(),
            tags=("rag", "retrieval", "rewrite"),
        ),
        "rag.summarize_context": PromptTemplate.from_string(
            "rag.summarize_context",
            dedent(
                """
Summarize the retrieved context in a compact, factual way.
Keep names, dates, and key evidence.

Context:
{{ context }}

Summary:
"""
            ).strip(),
            tags=("rag", "summary"),
        ),
        "rag.rank_context": PromptTemplate.from_string(
            "rag.rank_context",
            dedent(
                """
Rank the retrieved passages by relevance to the question.
Return a JSON-style list of passage ids from most to least relevant.

Question:
{{ question }}

Passages:
{{ passages }}
"""
            ).strip(),
            tags=("rag", "ranking"),
        ),
        "rag.cite_sources": PromptTemplate.from_string(
            "rag.cite_sources",
            dedent(
                """
Convert the following notes into a short answer with inline citations.
Use only the provided source ids.

Notes:
{{ notes }}

Sources:
{{ sources }}

Answer:
"""
            ).strip(),
            tags=("rag", "citations"),
        ),
    }


@dataclass
class PromptLibrary:
    """Named registry of prompt templates."""

    templates: dict[str, PromptTemplate] = field(default_factory=dict)

    def register(self, template: PromptTemplate) -> PromptLibrary:
        """Register or replace a template."""
        self.templates[template.name] = template
        return self

    def get(self, name: str) -> PromptTemplate | None:
        """Retrieve a template by name."""
        return self.templates.get(name)

    def names(self) -> list[str]:
        """List template names."""
        return sorted(self.templates)

    def render(self, prompt_name: str, **context: Any) -> str:
        """Render a registered template."""
        template = self.templates[prompt_name]
        return template.render(**context)

    def optimize(self, name: str, optimizer: PromptOptimizer | None = None) -> PromptTemplate:
        """Optimize a stored template."""
        template = self.templates[name]
        return (optimizer or PromptOptimizer()).optimize_template(template)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the library."""
        return {name: template.to_dict() for name, template in self.templates.items()}


_DEFAULT_LIBRARY: PromptLibrary | None = None


def get_default_prompt_library() -> PromptLibrary:
    """Get the shared built-in prompt library."""
    global _DEFAULT_LIBRARY
    if _DEFAULT_LIBRARY is None:
        _DEFAULT_LIBRARY = PromptLibrary()
        for template in _build_default_templates().values():
            _DEFAULT_LIBRARY.register(template)
    return _DEFAULT_LIBRARY


def get_rag_prompts() -> dict[str, PromptTemplate]:
    """Return the built-in RAG prompts."""
    return dict(get_default_prompt_library().templates)
