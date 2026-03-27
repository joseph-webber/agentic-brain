# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

"""
Tests for user regional data storage and learning system
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from agentic_brain.voice.user_regions import (
    UserRegion,
    UserRegionStorage,
    get_region_stats,
    get_user_region_storage,
    regionalize_text,
    set_user_region,
)


@pytest.fixture
def temp_data_dir():
    """Create temporary data directory for tests"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def storage(temp_data_dir):
    """Create a storage instance with temp directory"""
    return UserRegionStorage(data_dir=temp_data_dir)


class TestUserRegion:
    """Test UserRegion dataclass"""

    def test_create_region(self):
        """Test creating a user region"""
        region = UserRegion(
            city="Adelaide", state="South Australia", timezone="Australia/Adelaide"
        )
        assert region.city == "Adelaide"
        assert region.state == "South Australia"
        assert region.country == "Australia"
        assert region.last_updated is not None

    def test_region_defaults(self):
        """Test region has proper defaults"""
        region = UserRegion(city="Brisbane", state="Queensland")
        assert region.custom_expressions == {}
        assert region.learned_expressions == {}
        assert region.expression_usage == {}
        assert region.favorite_greetings == []
        assert isinstance(region.last_updated, str)


class TestUserRegionStorage:
    """Test UserRegionStorage functionality"""

    def test_storage_creation(self, temp_data_dir):
        """Test creating storage"""
        storage = UserRegionStorage(data_dir=temp_data_dir)
        assert storage.get_region() is None

    def test_set_region(self, storage):
        """Test setting a region"""
        region = storage.set_region("Adelaide", "South Australia")
        assert region.city == "Adelaide"
        assert region.state == "South Australia"
        assert storage.get_region() is not None

    def test_region_persistence(self, temp_data_dir):
        """Test region persists to disk"""
        storage1 = UserRegionStorage(data_dir=temp_data_dir)
        storage1.set_region("Sydney", "New South Wales")

        # Create new storage instance
        storage2 = UserRegionStorage(data_dir=temp_data_dir)
        region = storage2.get_region()

        assert region is not None
        assert region.city == "Sydney"
        assert region.state == "New South Wales"

    def test_add_custom_expression(self, storage):
        """Test adding custom expression"""
        storage.set_region("Adelaide", "South Australia")
        storage.add_expression("great", "heaps good")

        expressions = storage.get_all_expressions()
        assert expressions["great"] == "heaps good"

    def test_learn_expression(self, storage):
        """Test learning an expression"""
        storage.set_region("Brisbane", "Queensland")
        storage.learn_expression("very", "dead set")

        expressions = storage.get_all_expressions()
        assert expressions["very"] == "dead set"

    def test_learn_from_correction(self, storage):
        """Test learning from user correction"""
        storage.set_region("Adelaide", "South Australia")

        original = "That is very great"
        corrected = "That is heaps good"

        std, regional = storage.learn_from_correction(original, corrected)

        # Should extract one difference
        assert std is not None
        assert regional is not None

        # Verify it was learned
        expressions = storage.get_all_expressions()
        assert expressions.get(std.lower()) == regional

    def test_track_expression_usage(self, storage):
        """Test tracking expression usage"""
        storage.set_region("Adelaide", "South Australia")
        storage.add_expression("great", "heaps good")

        storage.track_expression_usage("great")
        storage.track_expression_usage("great")
        storage.track_expression_usage("great")

        region = storage.get_region()
        assert region.expression_usage["great"] == 3

    def test_get_all_expressions(self, storage):
        """Test getting all expressions merged"""
        storage.set_region("Adelaide", "South Australia")

        storage.add_expression("great", "awesome")
        storage.learn_expression("very", "super")

        expressions = storage.get_all_expressions()
        assert expressions["great"] == "awesome"
        assert expressions["very"] == "super"

    def test_custom_priority_over_learned(self, storage):
        """Test custom expressions take priority"""
        storage.set_region("Adelaide", "South Australia")

        storage.learn_expression("great", "bonzer")
        storage.add_expression("great", "heaps good")  # Custom overrides

        expressions = storage.get_all_expressions()
        assert expressions["great"] == "heaps good"

    def test_regionalize_text(self, storage):
        """Test regionalizing text"""
        storage.set_region("Adelaide", "South Australia")
        storage.add_expression("great", "heaps good")
        storage.add_expression("thank you", "ta")

        original = "That is great! Thank you!"
        regionalized = storage.regionalize(original)

        # Should contain at least one regional variant
        assert "heaps good" in regionalized or "ta" in regionalized

    def test_get_top_expressions(self, storage):
        """Test getting most-used expressions"""
        storage.set_region("Adelaide", "South Australia")

        storage.add_expression("great", "heaps good")
        storage.add_expression("very", "dead set")

        # Simulate usage
        for _ in range(10):
            storage.track_expression_usage("great")

        for _ in range(5):
            storage.track_expression_usage("very")

        top = storage.get_top_expressions(limit=2)

        assert len(top) <= 2
        # Most used should be first
        if len(top) > 0:
            assert top[0][2] >= top[-1][2]  # usage count

    def test_add_local_knowledge(self, storage):
        """Test adding local knowledge"""
        storage.set_region("Adelaide", "South Australia")
        storage.add_local_knowledge("coffee", "Aussies love flat whites")

        region = storage.get_region()
        assert region.local_knowledge["coffee"] == "Aussies love flat whites"

    def test_get_learning_stats(self, storage):
        """Test getting learning statistics"""
        storage.set_region("Adelaide", "South Australia")
        storage.add_expression("great", "heaps good")
        storage.learn_expression("very", "dead set")

        stats = storage.get_learning_stats()

        assert stats["total_custom"] == 1
        assert stats["total_learned"] == 1
        assert stats["total_expressions"] == 2
        assert stats["last_learning"] is not None

    def test_corrections_history(self, storage):
        """Test recording corrections history"""
        storage.set_region("Adelaide", "South Australia")

        storage.learn_from_correction("that is great", "that is heaps good")
        storage.learn_from_correction("very good", "dead set good")

        history = storage.get_corrections_history(limit=10)

        assert len(history) >= 2
        assert history[0]["original"] == "that is great"
        assert history[1]["original"] == "very good"

    def test_learnings_history(self, storage):
        """Test recording learnings history"""
        storage.set_region("Adelaide", "South Australia")

        storage.learn_expression("great", "heaps good")
        storage.learn_expression("very", "dead set", confidence=0.95)

        history = storage.get_learnings_history(limit=10)

        assert len(history) >= 2
        assert any(h["standard"] == "great" for h in history)
        assert any(h["standard"] == "very" for h in history)

    def test_export_config(self, storage, temp_data_dir):
        """Test exporting configuration"""
        storage.set_region("Adelaide", "South Australia")
        storage.add_expression("great", "heaps good")

        export_file = temp_data_dir / "export.json"

        assert storage.export_config(export_file)
        assert export_file.exists()

        with open(export_file) as f:
            data = json.load(f)
            assert data["region"]["city"] == "Adelaide"
            assert data["region"]["custom_expressions"]["great"] == "heaps good"

    def test_import_config(self, temp_data_dir):
        """Test importing configuration"""
        # Create export file
        export_data = {
            "region": {
                "city": "Brisbane",
                "state": "Queensland",
                "country": "Australia",
                "timezone": "Australia/Brisbane",
                "custom_expressions": {"very": "bonzer"},
                "learned_expressions": {},
                "expression_usage": {},
                "favorite_greetings": [],
                "favorite_farewells": [],
                "local_knowledge": {},
                "corrections_history": [],
                "last_updated": datetime.utcnow().isoformat(),
                "last_learning": datetime.utcnow().isoformat(),
            }
        }

        export_file = temp_data_dir / "import.json"
        with open(export_file, "w") as f:
            json.dump(export_data, f)

        # Import into new storage
        storage = UserRegionStorage(data_dir=temp_data_dir)
        assert storage.import_config(export_file)

        region = storage.get_region()
        assert region.city == "Brisbane"
        assert region.custom_expressions["very"] == "bonzer"


class TestModuleFunctions:
    """Test module-level convenience functions"""

    def test_set_user_region_auto_detect_state(self, monkeypatch):
        """Test set_user_region auto-detects state"""
        # Mock global storage
        temp_dir = tempfile.mkdtemp()

        import agentic_brain.voice.user_regions as user_regions_module

        user_regions_module._storage = UserRegionStorage(Path(temp_dir))

        region = set_user_region("Adelaide")
        assert region.city == "Adelaide"
        assert region.state == "South Australia"

    def test_regionalize_text_module_function(self, monkeypatch):
        """Test regionalize_text module function"""
        temp_dir = tempfile.mkdtemp()

        import agentic_brain.voice.user_regions as user_regions_module

        storage = UserRegionStorage(Path(temp_dir))
        monkeypatch.setattr(user_regions_module, "_storage", storage)
        monkeypatch.setattr(
            user_regions_module, "get_user_region_storage", lambda: storage
        )

        storage.set_region("Adelaide", "South Australia")
        storage.add_expression("good", "heaps good")

        result = regionalize_text("That is good!")
        assert "heaps good" in result


class TestIntegration:
    """Integration tests"""

    def test_full_workflow(self, temp_data_dir):
        """Test complete workflow: set → learn → regionalize"""
        storage = UserRegionStorage(data_dir=temp_data_dir)

        # 1. Set region
        storage.set_region("Adelaide", "South Australia")

        # 2. Add custom expressions
        storage.add_expression("great", "heaps good")
        storage.add_expression("thank you", "ta")

        # 3. Directly learn an expression (simulating correction learning)
        storage.learn_expression("very", "dead set")

        # 4. Track usage
        storage.track_expression_usage("great")
        storage.track_expression_usage("great")

        # 5. Regionalize text
        text = "That is great and thank you very much"
        storage.regionalize(text)

        # 6. Get stats
        stats = storage.get_learning_stats()

        assert stats["total_custom"] >= 2
        assert stats["total_learned"] >= 1
        assert stats["total_expressions"] >= 3

    def test_multi_user_regions(self, temp_data_dir):
        """Test using different regions"""
        storage = UserRegionStorage(data_dir=temp_data_dir)

        # Adelaide region
        storage.set_region("Adelaide", "South Australia")
        storage.add_expression("great", "heaps good")

        # Change to Brisbane
        storage.set_region("Brisbane", "Queensland")
        storage.add_expression("great", "bonzer")

        # Verify Brisbane is current
        region = storage.get_region()
        assert region.city == "Brisbane"
        expressions = storage.get_all_expressions()
        assert expressions["great"] == "bonzer"
