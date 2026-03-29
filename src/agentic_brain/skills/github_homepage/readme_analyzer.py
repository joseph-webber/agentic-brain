# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""
README Analyzer - Analyze GitHub READMEs for quality and SEO.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class ReadmeAnalysis:
    """Analysis results for a README file."""

    line_count: int
    size_kb: float
    sections: list[str]
    has_install_command: bool
    has_badges: bool
    has_code_examples: bool
    has_images: bool
    has_table_of_contents: bool
    seo_score: int
    missing_seo_terms: list[str]
    issues: list[str]
    suggestions: list[str]


class ReadmeAnalyzer:
    """
    Analyze GitHub README files for quality, SEO, and best practices.

    Example:
        analyzer = ReadmeAnalyzer()
        analysis = analyzer.analyze("README.md")
        print(f"SEO Score: {analysis.seo_score}")
        print(f"Issues: {analysis.issues}")
    """

    # Key SEO terms for AI/ML projects
    SEO_TERMS = [
        "graphrag",
        "knowledge graph",
        "vector database",
        "embeddings",
        "apple silicon",
        "mlx",
        "cuda",
        "rocm",
        "gpu",
        "enterprise",
        "production-ready",
        "fastapi",
        "neo4j",
        "llm",
        "ai agent",
        "chatbot",
        "rag",
        "retrieval",
        "accessibility",
        "wcag",
        "graphql",
        "kafka",
        "event streaming",
        "python",
        "typescript",
        "docker",
        "kubernetes",
    ]

    def analyze(self, readme_path: Path | str) -> ReadmeAnalysis:
        """
        Analyze a README file.

        Args:
            readme_path: Path to README.md

        Returns:
            Analysis results
        """
        content = Path(readme_path).read_text()
        content_lower = content.lower()
        lines = content.split("\n")

        # Extract sections
        sections = [line[3:].strip() for line in lines if line.startswith("## ")]

        # Check for key elements
        has_install = "pip install" in content_lower or "npm install" in content_lower
        has_badges = "[![" in content
        has_code = "```" in content
        has_images = "![" in content or "<img" in content
        has_toc = "table of contents" in content_lower or "- [" in content[:2000]

        # SEO analysis
        missing_seo = [term for term in self.SEO_TERMS if term not in content_lower]
        seo_score = self._calculate_seo_score(content, missing_seo)

        # Find issues
        issues = []
        suggestions = []

        if len(content) > 500_000:
            issues.append("README exceeds 500KB - will be truncated on GitHub")

        if not has_install:
            issues.append("No install command found")
            suggestions.append("Add pip install command near the top")

        if not has_badges:
            suggestions.append("Add status badges (CI, coverage, version)")

        if not has_code:
            issues.append("No code examples found")
            suggestions.append("Add copy-paste ready code examples")

        # Check Python version consistency
        if "3.10" in content and "3.11" not in content:
            issues.append("Python 3.10 mentioned - verify matches pyproject.toml")

        # Check for broken image syntax
        broken_imgs = re.findall(r"!\[([^\]]*)\]\(\s*\)", content)
        if broken_imgs:
            issues.append(f"Broken image references: {broken_imgs}")

        return ReadmeAnalysis(
            line_count=len(lines),
            size_kb=len(content.encode()) / 1024,
            sections=sections,
            has_install_command=has_install,
            has_badges=has_badges,
            has_code_examples=has_code,
            has_images=has_images,
            has_table_of_contents=has_toc,
            seo_score=seo_score,
            missing_seo_terms=missing_seo[:10],  # Top 10 missing
            issues=issues,
            suggestions=suggestions,
        )

    def _calculate_seo_score(self, content: str, missing: list[str]) -> int:
        """Calculate SEO score 0-100."""
        content_lower = content.lower()

        # Start with base score
        score = 50

        # Points for having key terms (max +30)
        found_terms = len(self.SEO_TERMS) - len(missing)
        score += min(30, found_terms * 2)

        # Points for structure (max +20)
        if "## " in content:
            score += 5
        if "### " in content:
            score += 3
        if "```" in content:
            score += 5
        if "[![" in content:
            score += 4
        if "pip install" in content_lower:
            score += 3

        return min(100, score)

    def quick_check(self, readme_path: Path | str) -> dict:
        """
        Quick health check returning pass/fail status.

        Returns:
            Dict with status and any critical issues
        """
        analysis = self.analyze(readme_path)

        critical = [
            i for i in analysis.issues if "exceeds" in i or "broken" in i.lower()
        ]

        return {
            "status": "pass" if not critical else "fail",
            "seo_score": analysis.seo_score,
            "line_count": analysis.line_count,
            "size_kb": round(analysis.size_kb, 1),
            "critical_issues": critical,
            "section_count": len(analysis.sections),
        }
