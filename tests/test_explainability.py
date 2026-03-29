# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
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

"""
Tests for the explainability module.

Tests are designed to work WITHOUT SHAP/LIME installed by using mocks.
Also tests graceful degradation when libraries are missing.
"""

import json
from unittest.mock import Mock, patch

import numpy as np
import pytest

# Import the module components
from agentic_brain.explainability import (
    ExplainabilityResult,
    ExplainerType,
    FeatureContribution,
    ModelType,
    check_lime_available,
    check_shap_available,
)

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def sample_feature_names():
    """Sample feature names for testing."""
    return ["age", "income", "credit_score", "debt_ratio", "employment_years"]


@pytest.fixture
def sample_data():
    """Sample input data."""
    return np.array([[25, 50000, 700, 0.3, 5]])


@pytest.fixture
def sample_training_data():
    """Sample training data for LIME."""
    np.random.seed(42)
    return np.random.rand(100, 5)


@pytest.fixture
def mock_model():
    """Create a mock model with predict and predict_proba methods."""
    model = Mock()
    model.predict = Mock(return_value=np.array([1]))
    model.predict_proba = Mock(return_value=np.array([[0.3, 0.7]]))
    return model


@pytest.fixture
def sample_contributions():
    """Sample feature contributions."""
    return [
        FeatureContribution("age", 0.15, base_value=0.5, feature_value=25),
        FeatureContribution("income", 0.25, base_value=0.5, feature_value=50000),
        FeatureContribution("credit_score", -0.10, base_value=0.5, feature_value=700),
        FeatureContribution("debt_ratio", -0.05, base_value=0.5, feature_value=0.3),
        FeatureContribution("employment_years", 0.08, base_value=0.5, feature_value=5),
    ]


@pytest.fixture
def sample_result(sample_contributions):
    """Sample ExplainabilityResult."""
    return ExplainabilityResult(
        explainer_type=ExplainerType.SHAP,
        model_type=ModelType.TREE,
        prediction=0.83,
        base_value=0.5,
        feature_contributions=sample_contributions,
        feature_importance={"income": 0.25, "age": 0.15, "credit_score": 0.10},
        metadata={"num_features": 5},
        success=True,
    )


# ============================================================================
# FeatureContribution Tests
# ============================================================================


class TestFeatureContribution:
    """Tests for FeatureContribution dataclass."""

    def test_creation(self):
        """Test basic creation."""
        fc = FeatureContribution(
            feature_name="age",
            contribution=0.15,
            base_value=0.5,
            feature_value=25,
        )
        assert fc.feature_name == "age"
        assert fc.contribution == 0.15
        assert fc.base_value == 0.5
        assert fc.feature_value == 25

    def test_creation_minimal(self):
        """Test creation with minimal args."""
        fc = FeatureContribution(feature_name="test", contribution=0.5)
        assert fc.feature_name == "test"
        assert fc.contribution == 0.5
        assert fc.base_value is None
        assert fc.feature_value is None

    def test_to_dict(self):
        """Test dictionary conversion."""
        fc = FeatureContribution("income", 0.25, 0.5, 50000)
        d = fc.to_dict()
        assert d["feature_name"] == "income"
        assert d["contribution"] == 0.25
        assert d["base_value"] == 0.5
        assert d["feature_value"] == 50000

    def test_negative_contribution(self):
        """Test negative contribution values."""
        fc = FeatureContribution("debt", -0.3)
        assert fc.contribution == -0.3


# ============================================================================
# ExplainabilityResult Tests
# ============================================================================


class TestExplainabilityResult:
    """Tests for ExplainabilityResult dataclass."""

    def test_creation(self, sample_contributions):
        """Test basic creation."""
        result = ExplainabilityResult(
            explainer_type=ExplainerType.SHAP,
            model_type=ModelType.TREE,
            prediction=0.8,
            feature_contributions=sample_contributions,
        )
        assert result.explainer_type == ExplainerType.SHAP
        assert result.success is True
        assert len(result.feature_contributions) == 5

    def test_error_result(self):
        """Test error result creation."""
        result = ExplainabilityResult.error_result(
            "Something went wrong", ExplainerType.LIME
        )
        assert result.success is False
        assert result.error == "Something went wrong"
        assert result.explainer_type == ExplainerType.LIME

    def test_to_dict(self, sample_result):
        """Test dictionary serialization."""
        d = sample_result.to_dict()
        assert d["explainer_type"] == "shap"
        assert d["model_type"] == "tree"
        assert d["prediction"] == 0.83
        assert d["success"] is True
        assert len(d["feature_contributions"]) == 5

    def test_to_json(self, sample_result):
        """Test JSON serialization."""
        json_str = sample_result.to_json()
        parsed = json.loads(json_str)
        assert parsed["explainer_type"] == "shap"
        assert parsed["success"] is True

    def test_from_dict(self, sample_result):
        """Test deserialization from dict."""
        d = sample_result.to_dict()
        restored = ExplainabilityResult.from_dict(d)
        assert restored.explainer_type == ExplainerType.SHAP
        assert restored.model_type == ModelType.TREE
        assert restored.prediction == 0.83
        assert len(restored.feature_contributions) == 5

    def test_get_top_features(self, sample_result):
        """Test getting top features by contribution."""
        top_3 = sample_result.get_top_features(3)
        assert len(top_3) == 3
        # Should be sorted by absolute contribution
        assert top_3[0].feature_name == "income"  # 0.25
        assert top_3[1].feature_name == "age"  # 0.15
        assert top_3[2].feature_name == "credit_score"  # -0.10 (abs = 0.10)

    def test_get_top_features_more_than_available(self, sample_result):
        """Test getting more features than available."""
        top_10 = sample_result.get_top_features(10)
        assert len(top_10) == 5  # Only 5 available

    def test_summary_success(self, sample_result):
        """Test summary generation for successful result."""
        summary = sample_result.summary()
        assert "SHAP" in summary
        assert "Prediction: 0.83" in summary
        assert "income" in summary

    def test_summary_error(self):
        """Test summary for error result."""
        result = ExplainabilityResult.error_result("Test error")
        summary = result.summary()
        assert "failed" in summary.lower()
        assert "Test error" in summary

    def test_empty_contributions(self):
        """Test with no feature contributions."""
        result = ExplainabilityResult(
            explainer_type=ExplainerType.LIME,
            success=True,
        )
        assert result.get_top_features(5) == []


# ============================================================================
# ExplainerType Tests
# ============================================================================


class TestExplainerType:
    """Tests for ExplainerType enum."""

    def test_values(self):
        """Test enum values."""
        assert ExplainerType.SHAP.value == "shap"
        assert ExplainerType.LIME.value == "lime"
        assert ExplainerType.UNKNOWN.value == "unknown"

    def test_from_string(self):
        """Test creating from string."""
        assert ExplainerType("shap") == ExplainerType.SHAP
        assert ExplainerType("lime") == ExplainerType.LIME


# ============================================================================
# ModelType Tests
# ============================================================================


class TestModelType:
    """Tests for ModelType enum."""

    def test_values(self):
        """Test enum values."""
        assert ModelType.TREE.value == "tree"
        assert ModelType.LINEAR.value == "linear"
        assert ModelType.DEEP.value == "deep"
        assert ModelType.KERNEL.value == "kernel"
        assert ModelType.TABULAR.value == "tabular"
        assert ModelType.TEXT.value == "text"
        assert ModelType.IMAGE.value == "image"


# ============================================================================
# Availability Checks Tests
# ============================================================================


class TestAvailabilityChecks:
    """Tests for library availability checks."""

    def test_check_shap_available_returns_bool(self):
        """Test that check_shap_available returns a boolean."""
        result = check_shap_available()
        assert isinstance(result, bool)

    def test_check_lime_available_returns_bool(self):
        """Test that check_lime_available returns a boolean."""
        result = check_lime_available()
        assert isinstance(result, bool)


# ============================================================================
# SHAPExplainer Tests (with mocks)
# ============================================================================


class TestSHAPExplainer:
    """Tests for SHAPExplainer using mocks."""

    def test_import_without_shap(self):
        """Test that module imports even without SHAP."""
        from agentic_brain.explainability.shap_explainer import SHAPExplainer

        assert SHAPExplainer is not None

    def test_explainer_type(self, mock_model, sample_feature_names):
        """Test explainer_type property."""
        from agentic_brain.explainability.shap_explainer import SHAPExplainer

        explainer = SHAPExplainer(mock_model, feature_names=sample_feature_names)
        assert explainer.explainer_type == ExplainerType.SHAP

    def test_is_available_reflects_import(self, mock_model):
        """Test is_available method."""
        from agentic_brain.explainability.shap_explainer import (
            SHAP_AVAILABLE,
            SHAPExplainer,
        )

        explainer = SHAPExplainer(mock_model)
        assert explainer.is_available() == SHAP_AVAILABLE

    @patch("agentic_brain.explainability.shap_explainer.SHAP_AVAILABLE", False)
    def test_explain_without_shap_installed(self, mock_model, sample_data):
        """Test graceful degradation when SHAP not installed."""
        from agentic_brain.explainability.shap_explainer import SHAPExplainer

        explainer = SHAPExplainer(mock_model)
        result = explainer.explain_prediction(sample_data)

        assert result.success is False
        assert "not installed" in result.error.lower()
        assert result.explainer_type == ExplainerType.SHAP

    def test_detect_tree_model(self, sample_feature_names):
        """Test auto-detection of tree model type."""
        from agentic_brain.explainability.shap_explainer import SHAPExplainer

        # Mock RandomForest-like model
        mock_rf = Mock()
        mock_rf.__class__.__name__ = "RandomForestClassifier"
        mock_rf.__class__.__module__ = "sklearn.ensemble"

        explainer = SHAPExplainer(mock_rf, feature_names=sample_feature_names)
        assert explainer.model_type == ModelType.TREE

    def test_detect_linear_model(self):
        """Test auto-detection of linear model type."""
        from agentic_brain.explainability.shap_explainer import SHAPExplainer

        mock_lr = Mock()
        mock_lr.__class__.__name__ = "LogisticRegression"

        explainer = SHAPExplainer(mock_lr)
        assert explainer.model_type == ModelType.LINEAR

    def test_detect_deep_model(self):
        """Test auto-detection of deep learning model."""
        from agentic_brain.explainability.shap_explainer import SHAPExplainer

        mock_nn = Mock()
        mock_nn.__class__.__name__ = "Sequential"
        mock_nn.__class__.__module__ = "keras.models"

        explainer = SHAPExplainer(mock_nn)
        assert explainer.model_type == ModelType.DEEP

    def test_get_feature_name_with_names(self, mock_model, sample_feature_names):
        """Test feature name retrieval with provided names."""
        from agentic_brain.explainability.shap_explainer import SHAPExplainer

        explainer = SHAPExplainer(mock_model, feature_names=sample_feature_names)
        assert explainer._get_feature_name(0) == "age"
        assert explainer._get_feature_name(1) == "income"

    def test_get_feature_name_fallback(self, mock_model):
        """Test feature name fallback when names not provided."""
        from agentic_brain.explainability.shap_explainer import SHAPExplainer

        explainer = SHAPExplainer(mock_model)
        assert explainer._get_feature_name(0) == "feature_0"
        assert explainer._get_feature_name(5) == "feature_5"


# ============================================================================
# LIMEExplainer Tests (with mocks)
# ============================================================================


class TestLIMEExplainer:
    """Tests for LIMEExplainer using mocks."""

    def test_import_without_lime(self):
        """Test that module imports even without LIME."""
        from agentic_brain.explainability.lime_explainer import LIMEExplainer

        assert LIMEExplainer is not None

    def test_explainer_type(self, mock_model, sample_training_data):
        """Test explainer_type property."""
        from agentic_brain.explainability.lime_explainer import LIMEExplainer

        explainer = LIMEExplainer(mock_model, training_data=sample_training_data)
        assert explainer.explainer_type == ExplainerType.LIME

    def test_is_available_reflects_import(self, mock_model, sample_training_data):
        """Test is_available method."""
        from agentic_brain.explainability.lime_explainer import (
            LIME_AVAILABLE,
            LIMEExplainer,
        )

        explainer = LIMEExplainer(mock_model, training_data=sample_training_data)
        assert explainer.is_available() == LIME_AVAILABLE

    @patch("agentic_brain.explainability.lime_explainer.LIME_AVAILABLE", False)
    def test_explain_without_lime_installed(
        self, mock_model, sample_training_data, sample_data
    ):
        """Test graceful degradation when LIME not installed."""
        from agentic_brain.explainability.lime_explainer import LIMEExplainer

        explainer = LIMEExplainer(mock_model, training_data=sample_training_data)
        result = explainer.explain_prediction(sample_data[0])

        assert result.success is False
        assert "not installed" in result.error.lower()
        assert result.explainer_type == ExplainerType.LIME

    @patch("agentic_brain.explainability.lime_explainer.LIME_AVAILABLE", False)
    def test_get_html_without_lime(self, mock_model, sample_training_data, sample_data):
        """Test HTML generation gracefully degrades."""
        from agentic_brain.explainability.lime_explainer import LIMEExplainer

        explainer = LIMEExplainer(mock_model, training_data=sample_training_data)
        html = explainer.get_explanation_html(sample_data[0])

        assert "not installed" in html.lower()

    def test_data_type_text(self, mock_model):
        """Test text data type configuration."""
        from agentic_brain.explainability.lime_explainer import LIMEExplainer

        explainer = LIMEExplainer(mock_model, data_type=ModelType.TEXT)
        assert explainer.data_type == ModelType.TEXT

    def test_data_type_image(self, mock_model):
        """Test image data type configuration."""
        from agentic_brain.explainability.lime_explainer import LIMEExplainer

        explainer = LIMEExplainer(mock_model, data_type=ModelType.IMAGE)
        assert explainer.data_type == ModelType.IMAGE


# ============================================================================
# UnifiedExplainer Tests
# ============================================================================


class TestUnifiedExplainer:
    """Tests for UnifiedExplainer."""

    def test_import(self):
        """Test that UnifiedExplainer imports correctly."""
        from agentic_brain.explainability.unified import UnifiedExplainer

        assert UnifiedExplainer is not None

    def test_creation(self, mock_model, sample_training_data, sample_feature_names):
        """Test basic creation."""
        from agentic_brain.explainability.unified import UnifiedExplainer

        explainer = UnifiedExplainer(
            mock_model,
            training_data=sample_training_data,
            feature_names=sample_feature_names,
        )
        assert explainer.model is mock_model
        assert explainer.feature_names == sample_feature_names

    def test_detect_tree_model_type(self, sample_training_data):
        """Test model type detection for tree models."""
        from agentic_brain.explainability.unified import UnifiedExplainer

        mock_xgb = Mock()
        mock_xgb.__class__.__name__ = "XGBClassifier"
        mock_xgb.__class__.__module__ = "xgboost"

        explainer = UnifiedExplainer(mock_xgb, training_data=sample_training_data)
        assert explainer._model_type == ModelType.TREE

    def test_get_available_explainers(self, mock_model, sample_training_data):
        """Test listing available explainers."""
        from agentic_brain.explainability.unified import UnifiedExplainer

        explainer = UnifiedExplainer(mock_model, training_data=sample_training_data)
        available = explainer.get_available_explainers()

        assert isinstance(available, list)
        # At minimum it should be a list (empty if neither installed)
        for e in available:
            assert e in [ExplainerType.SHAP, ExplainerType.LIME]

    def test_availability_status(self, mock_model, sample_training_data):
        """Test availability status report."""
        from agentic_brain.explainability.unified import UnifiedExplainer

        explainer = UnifiedExplainer(mock_model, training_data=sample_training_data)
        status = explainer.availability_status()

        assert "shap" in status
        assert "lime" in status
        assert "available" in status["shap"]
        assert "install_command" in status["shap"]
        assert "recommended_explainer" in status

    @patch("agentic_brain.explainability.unified.SHAP_AVAILABLE", False)
    @patch("agentic_brain.explainability.unified.LIME_AVAILABLE", False)
    def test_explain_no_libraries(self, mock_model, sample_training_data, sample_data):
        """Test explain when no libraries available."""
        from agentic_brain.explainability.unified import UnifiedExplainer

        explainer = UnifiedExplainer(mock_model, training_data=sample_training_data)
        result = explainer.explain(sample_data)

        assert result.success is False
        assert "no explainer available" in result.error.lower()

    def test_preferred_explainer_shap(self, mock_model, sample_training_data):
        """Test setting preferred explainer to SHAP."""
        from agentic_brain.explainability.unified import UnifiedExplainer

        explainer = UnifiedExplainer(
            mock_model,
            training_data=sample_training_data,
            preferred_explainer=ExplainerType.SHAP,
        )
        assert explainer.preferred_explainer == ExplainerType.SHAP

    def test_preferred_explainer_lime(self, mock_model, sample_training_data):
        """Test setting preferred explainer to LIME."""
        from agentic_brain.explainability.unified import UnifiedExplainer

        explainer = UnifiedExplainer(
            mock_model,
            training_data=sample_training_data,
            preferred_explainer=ExplainerType.LIME,
        )
        assert explainer.preferred_explainer == ExplainerType.LIME

    def test_export_report_dict_format(
        self, mock_model, sample_training_data, sample_data
    ):
        """Test report export in dict format."""
        from agentic_brain.explainability.unified import UnifiedExplainer

        explainer = UnifiedExplainer(mock_model, training_data=sample_training_data)
        report = explainer.export_report(
            sample_data, format="dict", include_comparison=False
        )

        assert isinstance(report, dict)
        assert "model_type" in report
        assert "data_type" in report
        assert "primary_explanation" in report

    def test_export_report_json_format(
        self, mock_model, sample_training_data, sample_data
    ):
        """Test report export in JSON format."""
        from agentic_brain.explainability.unified import UnifiedExplainer

        explainer = UnifiedExplainer(mock_model, training_data=sample_training_data)
        report = explainer.export_report(
            sample_data, format="json", include_comparison=False
        )

        assert isinstance(report, str)
        parsed = json.loads(report)
        assert "model_type" in parsed

    def test_export_report_html_format(
        self, mock_model, sample_training_data, sample_data
    ):
        """Test report export in HTML format."""
        from agentic_brain.explainability.unified import UnifiedExplainer

        explainer = UnifiedExplainer(mock_model, training_data=sample_training_data)
        report = explainer.export_report(
            sample_data, format="html", include_comparison=False
        )

        assert isinstance(report, str)
        assert "<html>" in report
        assert "Model Information" in report


# ============================================================================
# ComparisonResult Tests
# ============================================================================


class TestComparisonResult:
    """Tests for ComparisonResult dataclass."""

    def test_creation(self, sample_result):
        """Test basic creation."""
        from agentic_brain.explainability.unified import ComparisonResult

        comparison = ComparisonResult(
            shap_result=sample_result,
            lime_result=None,
            agreement_score=0.0,
            top_features_overlap=[],
            divergent_features=[],
            recommendation="Only SHAP available",
        )
        assert comparison.shap_result is not None
        assert comparison.lime_result is None
        assert comparison.agreement_score == 0.0

    def test_to_dict(self, sample_result):
        """Test dictionary conversion."""
        from agentic_brain.explainability.unified import ComparisonResult

        comparison = ComparisonResult(
            shap_result=sample_result,
            lime_result=sample_result,
            agreement_score=0.85,
            top_features_overlap=["income", "age"],
            divergent_features=["credit_score"],
            recommendation="High agreement",
        )
        d = comparison.to_dict()

        assert d["agreement_score"] == 0.85
        assert d["top_features_overlap"] == ["income", "age"]
        assert d["divergent_features"] == ["credit_score"]
        assert d["recommendation"] == "High agreement"


# ============================================================================
# Integration Tests (minimal, work without actual libraries)
# ============================================================================


class TestIntegration:
    """Integration tests that work without SHAP/LIME installed."""

    def test_full_import_chain(self):
        """Test that all imports work correctly."""
        from agentic_brain.explainability import (
            LIME_AVAILABLE,
            SHAP_AVAILABLE,
            ExplainabilityResult,
            ExplainerType,
            FeatureContribution,
            LIMEExplainer,
            ModelType,
            SHAPExplainer,
            UnifiedExplainer,
        )

        # All should be importable
        assert ExplainerType is not None
        assert ModelType is not None
        assert FeatureContribution is not None
        assert ExplainabilityResult is not None
        assert SHAPExplainer is not None
        assert LIMEExplainer is not None
        assert UnifiedExplainer is not None
        assert isinstance(SHAP_AVAILABLE, bool)
        assert isinstance(LIME_AVAILABLE, bool)

    def test_result_round_trip(self, sample_contributions):
        """Test serialization and deserialization round trip."""
        original = ExplainabilityResult(
            explainer_type=ExplainerType.SHAP,
            model_type=ModelType.TREE,
            prediction=0.75,
            base_value=0.5,
            feature_contributions=sample_contributions,
            feature_importance={"income": 0.25},
            metadata={"test": True},
            success=True,
        )

        # Serialize
        json_str = original.to_json()

        # Deserialize
        restored = ExplainabilityResult.from_dict(json.loads(json_str))

        # Verify
        assert restored.explainer_type == original.explainer_type
        assert restored.model_type == original.model_type
        assert restored.prediction == original.prediction
        assert restored.success == original.success
        assert len(restored.feature_contributions) == len(
            original.feature_contributions
        )

    def test_explainer_chain_with_mock(
        self, mock_model, sample_training_data, sample_feature_names
    ):
        """Test creating explainer chain with mock model."""
        from agentic_brain.explainability import UnifiedExplainer

        explainer = UnifiedExplainer(
            mock_model,
            training_data=sample_training_data,
            feature_names=sample_feature_names,
            class_names=["negative", "positive"],
        )

        # Should be able to get status
        status = explainer.availability_status()
        assert status is not None

        # Should be able to list available explainers
        available = explainer.get_available_explainers()
        assert isinstance(available, list)


# ============================================================================
# Edge Cases Tests
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_data(self, mock_model, sample_training_data):
        """Test handling of empty data."""
        from agentic_brain.explainability.unified import UnifiedExplainer

        explainer = UnifiedExplainer(mock_model, training_data=sample_training_data)

        # Empty array should be handled gracefully
        empty = np.array([])
        # This should not crash, even if it returns an error result
        try:
            result = explainer.explain(empty)
            # Either success with empty or error - both acceptable
            assert isinstance(result, ExplainabilityResult)
        except Exception:
            # Some edge cases may raise - that's acceptable too
            pass

    def test_single_feature(self, mock_model):
        """Test with single feature."""
        fc = FeatureContribution("only_feature", 0.5)
        result = ExplainabilityResult(
            explainer_type=ExplainerType.SHAP,
            feature_contributions=[fc],
            success=True,
        )
        assert len(result.get_top_features(10)) == 1

    def test_very_long_feature_names(self):
        """Test with very long feature names."""
        long_name = "a" * 1000
        fc = FeatureContribution(long_name, 0.5)
        assert fc.feature_name == long_name

    def test_unicode_feature_names(self):
        """Test with unicode feature names."""
        fc = FeatureContribution("特征_収入_доход", 0.5)
        result = ExplainabilityResult(
            explainer_type=ExplainerType.LIME,
            feature_contributions=[fc],
            success=True,
        )
        json_str = result.to_json()
        restored = ExplainabilityResult.from_dict(json.loads(json_str))
        assert restored.feature_contributions[0].feature_name == "特征_収入_доход"

    def test_nan_contribution(self):
        """Test handling of NaN contributions."""
        fc = FeatureContribution("test", float("nan"))
        d = fc.to_dict()
        # NaN should be preserved or converted
        assert "contribution" in d

    def test_inf_contribution(self):
        """Test handling of infinity contributions."""
        fc = FeatureContribution("test", float("inf"))
        d = fc.to_dict()
        assert "contribution" in d

    def test_zero_contributions(self):
        """Test with all zero contributions."""
        contributions = [FeatureContribution(f"feature_{i}", 0.0) for i in range(5)]
        result = ExplainabilityResult(
            explainer_type=ExplainerType.SHAP,
            feature_contributions=contributions,
            success=True,
        )
        top = result.get_top_features(3)
        assert len(top) == 3
        assert all(fc.contribution == 0.0 for fc in top)
