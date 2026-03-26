# SPDX-License-Identifier: Apache-2.0
# Copyright 2025 Joseph Webber
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""
User Regional Data Storage with Real-Time Learning

Stores and learns regional language preferences on user's disk.
Each user can customize their own regional slang and expressions.
Auto-learns from corrections and usage patterns.
"""

import json
import os
import statistics
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

DEFAULT_DATA_DIR = Path.home() / ".agentic-brain" / "regions"


@dataclass
class UserRegion:
    """User's regional language configuration"""

    city: str
    state: str
    country: str = "Australia"
    timezone: str = "Australia/Adelaide"
    custom_expressions: Dict[str, str] = field(default_factory=dict)
    learned_expressions: Dict[str, str] = field(default_factory=dict)
    expression_usage: Dict[str, int] = field(default_factory=dict)
    favorite_greetings: List[str] = field(default_factory=list)
    favorite_farewells: List[str] = field(default_factory=list)
    local_knowledge: Dict[str, str] = field(default_factory=dict)
    corrections_history: List[Dict] = field(default_factory=list)
    last_updated: str = ""
    last_learning: str = ""

    def __post_init__(self):
        if not self.last_updated:
            self.last_updated = datetime.utcnow().isoformat()
        if not self.last_learning:
            self.last_learning = datetime.utcnow().isoformat()


class UserRegionStorage:
    """Persistent storage for user regional preferences with real-time learning"""

    def __init__(self, data_dir: Optional[Path] = None):
        self._data_dir = data_dir or DEFAULT_DATA_DIR
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._config_file = self._data_dir / "user_region.json"
        self._corrections_file = self._data_dir / "corrections.jsonl"
        self._learnings_file = self._data_dir / "learnings.jsonl"
        self._region: Optional[UserRegion] = None
        self._load()

    def _load(self):
        """Load region from disk"""
        if self._config_file.exists():
            try:
                with open(self._config_file) as f:
                    data = json.load(f)
                    self._region = UserRegion(**data)
            except Exception as e:
                print(f"Error loading region config: {e}")

    def _save(self):
        """Save region to disk"""
        if self._region:
            self._region.last_updated = datetime.utcnow().isoformat()
            with open(self._config_file, "w") as f:
                json.dump(asdict(self._region), f, indent=2)

    def get_region(self) -> Optional[UserRegion]:
        """Get current user region"""
        return self._region

    def set_region(self, city: str, state: str, country: str = "Australia"):
        """Set user's region"""
        from agentic_brain.voice.australian_regions import AUSTRALIAN_CITIES

        # Load defaults for this city
        city_key = city.lower()
        defaults = AUSTRALIAN_CITIES.get(city_key, {})

        self._region = UserRegion(
            city=city,
            state=state,
            country=country,
            timezone=defaults.get("timezone", "Australia/Adelaide"),
            custom_expressions={},
            learned_expressions={},
            expression_usage={},
            favorite_greetings=defaults.get("greetings", []),
            favorite_farewells=defaults.get("farewells", []),
            local_knowledge=defaults.get("local_knowledge", {}),
        )
        self._save()
        return self._region

    def add_expression(self, standard: str, regional: str):
        """Add a custom regional expression"""
        if self._region:
            self._region.custom_expressions[standard.lower()] = regional
            self._save()

    def learn_expression(self, standard: str, regional: str, confidence: float = 0.8):
        """Auto-learn an expression from usage"""
        if self._region:
            standard_lower = standard.lower()

            # Record the learning event
            learning_event = {
                "timestamp": datetime.utcnow().isoformat(),
                "standard": standard,
                "regional": regional,
                "confidence": confidence,
                "source": "auto_learn",
            }

            # Append to learnings file for analysis
            with open(self._learnings_file, "a") as f:
                f.write(json.dumps(learning_event) + "\n")

            # Store in learned_expressions
            self._region.learned_expressions[standard_lower] = regional
            self._region.last_learning = datetime.utcnow().isoformat()
            self._save()

    def learn_from_correction(
        self, original: str, corrected: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Learn when user corrects speech
        Returns (standard_term, regional_term) if extraction successful, else (None, None)
        """
        if not self._region:
            return None, None

        # Record correction event
        correction_event = {
            "timestamp": datetime.utcnow().isoformat(),
            "original": original,
            "corrected": corrected,
        }

        # Append to corrections file
        with open(self._corrections_file, "a") as f:
            f.write(json.dumps(correction_event) + "\n")

        # Simple extraction: find differences
        words_original = original.lower().split()
        words_corrected = corrected.lower().split()

        if len(words_original) == len(words_corrected):
            for _i, (orig_word, corr_word) in enumerate(
                zip(words_original, words_corrected)
            ):
                if orig_word != corr_word:
                    self.learn_expression(orig_word, corr_word, confidence=0.9)
                    return orig_word, corr_word

        return None, None

    def add_local_knowledge(self, topic: str, info: str):
        """Add local knowledge"""
        if self._region:
            self._region.local_knowledge[topic] = info
            self._save()

    def track_expression_usage(self, expression: str):
        """Track when expressions are used"""
        if self._region:
            expr_lower = expression.lower()
            if expr_lower not in self._region.expression_usage:
                self._region.expression_usage[expr_lower] = 0
            self._region.expression_usage[expr_lower] += 1
            self._save()

    def get_all_expressions(self) -> Dict[str, str]:
        """Get all expressions (custom + learned)"""
        if not self._region:
            return {}

        # Merge: custom takes priority over learned
        expressions = {}
        expressions.update(self._region.learned_expressions)
        expressions.update(self._region.custom_expressions)
        return expressions

    def get_top_expressions(self, limit: int = 10) -> List[Tuple[str, str, int]]:
        """Get most-used expressions"""
        if not self._region:
            return []

        all_expr = self.get_all_expressions()
        usage_data = []

        for expr, regional in all_expr.items():
            count = self._region.expression_usage.get(expr, 0)
            usage_data.append((expr, regional, count))

        # Sort by usage count
        return sorted(usage_data, key=lambda x: x[2], reverse=True)[:limit]

    def regionalize(self, text: str) -> str:
        """Apply regional expressions to text"""
        expressions = self.get_all_expressions()
        result = text
        for standard, regional in expressions.items():
            # Replace whole words only
            import re

            pattern = r"\b" + re.escape(standard) + r"\b"
            result = re.sub(pattern, regional, result, flags=re.IGNORECASE)
            # Track usage
            self.track_expression_usage(standard)
        return result

    def get_learning_stats(self) -> Dict:
        """Get statistics about learning"""
        stats = {
            "total_custom": len(self._region.custom_expressions) if self._region else 0,
            "total_learned": (
                len(self._region.learned_expressions) if self._region else 0
            ),
            "total_expressions": len(self.get_all_expressions()),
            "corrections_count": 0,
            "learnings_count": 0,
            "last_learning": self._region.last_learning if self._region else None,
        }

        # Count from files
        if self._corrections_file.exists():
            with open(self._corrections_file) as f:
                stats["corrections_count"] = sum(1 for _ in f)

        if self._learnings_file.exists():
            with open(self._learnings_file) as f:
                stats["learnings_count"] = sum(1 for _ in f)

        return stats

    def get_corrections_history(self, limit: int = 20) -> List[Dict]:
        """Get recent corrections"""
        corrections = []
        if self._corrections_file.exists():
            with open(self._corrections_file) as f:
                for line in f:
                    try:
                        corrections.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return corrections[-limit:]

    def get_learnings_history(self, limit: int = 20) -> List[Dict]:
        """Get recent learnings"""
        learnings = []
        if self._learnings_file.exists():
            with open(self._learnings_file) as f:
                for line in f:
                    try:
                        learnings.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
        return learnings[-limit:]

    def export_config(self, filepath: Path) -> bool:
        """Export region config to file"""
        try:
            export_data = {
                "region": asdict(self._region) if self._region else {},
                "exported_at": datetime.utcnow().isoformat(),
            }
            with open(filepath, "w") as f:
                json.dump(export_data, f, indent=2)
            return True
        except Exception as e:
            print(f"Export failed: {e}")
            return False

    def import_config(self, filepath: Path) -> bool:
        """Import region config from file"""
        try:
            with open(filepath) as f:
                data = json.load(f)
                region_data = data.get("region", {})
                self._region = UserRegion(**region_data)
                self._save()
                return True
        except Exception as e:
            print(f"Import failed: {e}")
            return False


# Global instance
_storage: Optional[UserRegionStorage] = None


def get_user_region_storage() -> UserRegionStorage:
    """Get or create user region storage"""
    global _storage
    if _storage is None:
        _storage = UserRegionStorage()
    return _storage


def set_user_region(city: str, state: str = None) -> UserRegion:
    """Set user's region (e.g., 'Adelaide', 'South Australia')"""
    storage = get_user_region_storage()

    # Auto-detect state if not provided
    state_map = {
        "adelaide": "South Australia",
        "brisbane": "Queensland",
        "sydney": "New South Wales",
        "melbourne": "Victoria",
        "perth": "Western Australia",
        "darwin": "Northern Territory",
        "hobart": "Tasmania",
        "canberra": "Australian Capital Territory",
    }

    if state is None:
        state = state_map.get(city.lower(), "")

    return storage.set_region(city, state)


def learn_regional_expression(standard: str, regional: str):
    """Learn a new regional expression"""
    storage = get_user_region_storage()
    storage.learn_expression(standard, regional)


def regionalize_text(text: str) -> str:
    """Apply regional expressions to text"""
    storage = get_user_region_storage()
    return storage.regionalize(text)


def get_region_stats() -> Dict:
    """Get regional learning statistics"""
    storage = get_user_region_storage()
    return storage.get_learning_stats()
