# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

"""
GitHub Homepage Skill - Learning README Management

Learns from every README change to make better homepages over time.
Stores snapshots, tracks what works, remembers good patterns.
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ReadmeSnapshot:
    """A point-in-time snapshot of the README."""

    timestamp: str
    content_hash: str
    description: str
    line_count: int
    size_bytes: int
    sections: list[str]
    good_points: list[str] = field(default_factory=list)
    bad_points: list[str] = field(default_factory=list)
    seo_score: int = 0


@dataclass
class HomepageLearning:
    """A learning about what works for GitHub homepages."""

    timestamp: str
    category: str  # seo, structure, content, visuals, badges
    learning: str
    source: str  # user_feedback, analytics, comparison
    confidence: float = 0.8


class HomepageSkill:
    """
    Skill for creating and maintaining excellent GitHub homepages.

    Learns from experience - remembers what worked, what didn't,
    and suggests improvements based on accumulated knowledge.

    Example:
        skill = HomepageSkill()

        # Take a snapshot before changes
        skill.snapshot("Before GraphRAG section")

        # Make changes...

        # Record what worked
        skill.learn("GraphRAG ASCII diagram gets good feedback", category="visuals")
        skill.learn("Python 3.11+ badge must match pyproject.toml", category="accuracy")

        # Get suggestions for improvements
        suggestions = skill.suggest_improvements()
    """

    # Built-in learnings - accumulated knowledge about GitHub READMEs
    CORE_LEARNINGS: list[dict] = [
        {
            "category": "seo",
            "learning": "GitHub renders up to 500KB - use the space wisely for SEO keywords",
            "confidence": 1.0,
        },
        {
            "category": "seo",
            "learning": "Repository description and topics (up to 20) boost discoverability",
            "confidence": 1.0,
        },
        {
            "category": "structure",
            "learning": "Single H1 heading (project name), then H2/H3 for sections",
            "confidence": 1.0,
        },
        {
            "category": "structure",
            "learning": "Table of contents helps navigation for long READMEs",
            "confidence": 0.9,
        },
        {
            "category": "badges",
            "learning": "Badges at top provide quick validation - CI, coverage, version, license",
            "confidence": 1.0,
        },
        {
            "category": "badges",
            "learning": "Python version badge MUST match pyproject.toml requires-python",
            "confidence": 1.0,
        },
        {
            "category": "content",
            "learning": "One-liner install command near top increases adoption",
            "confidence": 0.95,
        },
        {
            "category": "content",
            "learning": "ASCII diagrams work great - no external image hosting needed",
            "confidence": 0.9,
        },
        {
            "category": "content",
            "learning": "Code examples should be copy-paste ready and actually work",
            "confidence": 1.0,
        },
        {
            "category": "visuals",
            "learning": "Screenshots and diagrams increase engagement and dwell time",
            "confidence": 0.9,
        },
        {
            "category": "visuals",
            "learning": "Don't rely on external image hosting - images can break",
            "confidence": 0.95,
        },
        {
            "category": "accessibility",
            "learning": "All images need alt text for screen readers",
            "confidence": 1.0,
        },
        {
            "category": "seo",
            "learning": "Key terms to include: GraphRAG, Knowledge Graph, Vector Database, Enterprise AI",
            "confidence": 0.85,
        },
        {
            "category": "seo",
            "learning": "Hardware terms: Apple Silicon, M2, M3, M4, MLX, CUDA, ROCm, GPU acceleration",
            "confidence": 0.85,
        },
        {
            "category": "content",
            "learning": "Highlight differentiators early - what makes this unique vs competitors",
            "confidence": 0.9,
        },
        {
            "category": "structure",
            "learning": "Keep existing good content - don't throw baby out with bathwater",
            "confidence": 1.0,
        },
    ]

    def __init__(self, storage_dir: Optional[Path] = None):
        """
        Initialize the homepage skill.

        Args:
            storage_dir: Where to store snapshots and learnings.
                        Defaults to ~/.agentic-brain/homepage-skill/
        """
        if storage_dir is None:
            storage_dir = Path.home() / ".agentic-brain" / "homepage-skill"

        self.storage_dir = Path(storage_dir)
        self.snapshots_dir = self.storage_dir / "snapshots"
        self.learnings_file = self.storage_dir / "learnings.json"

        # Create directories
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)

        # Load learnings
        self.learnings: list[HomepageLearning] = []
        self._load_learnings()

    def _load_learnings(self) -> None:
        """Load learnings from disk."""
        if self.learnings_file.exists():
            try:
                data = json.loads(self.learnings_file.read_text())
                self.learnings = [
                    HomepageLearning(**l) for l in data.get("learnings", [])
                ]
                logger.info(f"Loaded {len(self.learnings)} learnings")
            except Exception as e:
                logger.warning(f"Failed to load learnings: {e}")

    def _save_learnings(self) -> None:
        """Save learnings to disk."""
        data = {
            "learnings": [
                {
                    "timestamp": l.timestamp,
                    "category": l.category,
                    "learning": l.learning,
                    "source": l.source,
                    "confidence": l.confidence,
                }
                for l in self.learnings
            ]
        }
        self.learnings_file.write_text(json.dumps(data, indent=2))

    def snapshot(
        self,
        readme_path: Path | str,
        description: str,
        good_points: Optional[list[str]] = None,
        bad_points: Optional[list[str]] = None,
    ) -> ReadmeSnapshot:
        """
        Take a snapshot of the current README state.

        Args:
            readme_path: Path to the README.md file
            description: Description of this version (e.g., "Added GraphRAG section")
            good_points: What's good about this version
            bad_points: What needs improvement

        Returns:
            The created snapshot
        """
        readme_path = Path(readme_path)
        content = readme_path.read_text()

        # Extract sections (H2 headings)
        sections = []
        for line in content.split("\n"):
            if line.startswith("## "):
                sections.append(line[3:].strip())

        # Create snapshot
        snapshot = ReadmeSnapshot(
            timestamp=datetime.now().isoformat(),
            content_hash=hashlib.sha256(content.encode()).hexdigest()[:12],
            description=description,
            line_count=len(content.split("\n")),
            size_bytes=len(content.encode()),
            sections=sections,
            good_points=good_points or [],
            bad_points=bad_points or [],
            seo_score=self._calculate_seo_score(content),
        )

        # Save snapshot
        snapshot_file = (
            self.snapshots_dir / f"{snapshot.timestamp.replace(':', '-')}.json"
        )
        snapshot_file.write_text(
            json.dumps(
                {
                    "timestamp": snapshot.timestamp,
                    "content_hash": snapshot.content_hash,
                    "description": snapshot.description,
                    "line_count": snapshot.line_count,
                    "size_bytes": snapshot.size_bytes,
                    "sections": snapshot.sections,
                    "good_points": snapshot.good_points,
                    "bad_points": snapshot.bad_points,
                    "seo_score": snapshot.seo_score,
                },
                indent=2,
            )
        )

        # Also save the actual content
        content_file = self.snapshots_dir / f"{snapshot.content_hash}.md"
        content_file.write_text(content)

        logger.info(f"Snapshot saved: {description} ({snapshot.content_hash})")
        return snapshot

    def _calculate_seo_score(self, content: str) -> int:
        """Calculate a simple SEO score for the README."""
        score = 0
        content_lower = content.lower()

        # Key terms to check
        seo_terms = [
            "graphrag",
            "knowledge graph",
            "vector",
            "embeddings",
            "apple silicon",
            "m2",
            "m3",
            "m4",
            "mlx",
            "cuda",
            "rocm",
            "enterprise",
            "production",
            "fastapi",
            "neo4j",
            "llm",
            "ai agent",
            "chatbot",
            "rag",
            "accessibility",
            "wcag",
            "screen reader",
            "graphql",
            "kafka",
            "event",
            "streaming",
        ]

        for term in seo_terms:
            if term in content_lower:
                score += 3

        # Check for good structure
        if "## " in content:
            score += 10  # Has sections
        if "```" in content:
            score += 10  # Has code examples
        if "[![" in content:
            score += 5  # Has badges
        if "pip install" in content_lower:
            score += 10  # Has install command

        return min(score, 100)

    def learn(
        self,
        learning: str,
        category: str = "content",
        source: str = "user_feedback",
        confidence: float = 0.8,
    ) -> HomepageLearning:
        """
        Record a learning about what works for GitHub homepages.

        Args:
            learning: The insight (e.g., "ASCII diagrams get good engagement")
            category: Type of learning (seo, structure, content, visuals, badges, accessibility)
            source: Where this came from (user_feedback, analytics, comparison)
            confidence: How confident we are (0.0-1.0)

        Returns:
            The recorded learning
        """
        new_learning = HomepageLearning(
            timestamp=datetime.now().isoformat(),
            category=category,
            learning=learning,
            source=source,
            confidence=confidence,
        )

        self.learnings.append(new_learning)
        self._save_learnings()

        logger.info(f"Learning recorded: {learning}")
        return new_learning

    def get_all_learnings(self) -> list[dict]:
        """
        Get all learnings including core and user-added.

        Returns:
            List of all learnings sorted by confidence
        """
        all_learnings = []

        # Add core learnings
        for core in self.CORE_LEARNINGS:
            all_learnings.append(
                {
                    "category": core["category"],
                    "learning": core["learning"],
                    "confidence": core["confidence"],
                    "source": "core",
                }
            )

        # Add user learnings
        for l in self.learnings:
            all_learnings.append(
                {
                    "category": l.category,
                    "learning": l.learning,
                    "confidence": l.confidence,
                    "source": l.source,
                }
            )

        # Sort by confidence
        all_learnings.sort(key=lambda x: x["confidence"], reverse=True)
        return all_learnings

    def suggest_improvements(self, readme_path: Optional[Path] = None) -> list[str]:
        """
        Suggest improvements based on accumulated learnings.

        Args:
            readme_path: Optional path to README to analyze

        Returns:
            List of suggested improvements
        """
        suggestions = []

        # Get high-confidence learnings
        learnings = self.get_all_learnings()

        if readme_path and Path(readme_path).exists():
            content = Path(readme_path).read_text().lower()

            # Check for missing SEO terms
            seo_terms = [
                "graphrag",
                "knowledge graph",
                "graphql",
                "vector",
                "mlx",
                "cuda",
            ]
            missing = [t for t in seo_terms if t not in content]
            if missing:
                suggestions.append(f"Consider adding SEO terms: {', '.join(missing)}")

            # Check badge accuracy
            if "3.10" in content and "requires-python" not in content:
                suggestions.append("Verify Python version badge matches pyproject.toml")

        # Add general suggestions from learnings
        for l in learnings[:5]:  # Top 5 highest confidence
            if l["confidence"] >= 0.9:
                suggestions.append(f"[{l['category']}] {l['learning']}")

        return suggestions

    def list_snapshots(self) -> list[dict]:
        """List all saved snapshots."""
        snapshots = []
        for f in sorted(self.snapshots_dir.glob("*.json")):
            try:
                data = json.loads(f.read_text())
                snapshots.append(data)
            except Exception:
                pass
        return snapshots

    def restore_snapshot(self, content_hash: str, target_path: Path | str) -> bool:
        """
        Restore a README from a snapshot.

        Args:
            content_hash: The hash of the snapshot to restore
            target_path: Where to write the restored content

        Returns:
            True if successful
        """
        content_file = self.snapshots_dir / f"{content_hash}.md"
        if not content_file.exists():
            logger.error(f"Snapshot not found: {content_hash}")
            return False

        Path(target_path).write_text(content_file.read_text())
        logger.info(f"Restored snapshot {content_hash} to {target_path}")
        return True

    def compare_snapshots(self, hash1: str, hash2: str) -> dict:
        """
        Compare two snapshots.

        Args:
            hash1: First snapshot hash
            hash2: Second snapshot hash

        Returns:
            Comparison results
        """
        file1 = self.snapshots_dir / f"{hash1}.md"
        file2 = self.snapshots_dir / f"{hash2}.md"

        if not file1.exists() or not file2.exists():
            return {"error": "Snapshot not found"}

        content1 = file1.read_text()
        content2 = file2.read_text()

        return {
            "hash1": hash1,
            "hash2": hash2,
            "lines_diff": len(content2.split("\n")) - len(content1.split("\n")),
            "size_diff": len(content2) - len(content1),
            "seo_score1": self._calculate_seo_score(content1),
            "seo_score2": self._calculate_seo_score(content2),
        }
