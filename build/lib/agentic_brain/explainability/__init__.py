# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
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
Explainability module for agentic-brain.

Provides SHAP and LIME integration for model interpretability.
Both libraries are optional - code gracefully degrades if not installed.

Usage:
    from agentic_brain.explainability import UnifiedExplainer, ExplainabilityResult

    explainer = UnifiedExplainer(model)
    result = explainer.explain(data)
"""

import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class ExplainerType(Enum):
    """Supported explainer types."""

    SHAP = "shap"
    LIME = "lime"
    UNKNOWN = "unknown"


class ModelType(Enum):
    """Supported model types for auto-selection."""

    TREE = "tree"  # Random Forest, XGBoost, LightGBM, etc.
    LINEAR = "linear"  # Linear/Logistic regression
    DEEP = "deep"  # Neural networks
    KERNEL = "kernel"  # Any model (slower, model-agnostic)
    TABULAR = "tabular"  # Tabular data (LIME)
    TEXT = "text"  # Text data (LIME)
    IMAGE = "image"  # Image data (LIME)


@dataclass
class FeatureContribution:
    """Single feature's contribution to a prediction."""

    feature_name: str
    contribution: float
    base_value: Optional[float] = None
    feature_value: Optional[Any] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "feature_name": self.feature_name,
            "contribution": self.contribution,
            "base_value": self.base_value,
            "feature_value": self.feature_value,
        }


@dataclass
class ExplainabilityResult:
    """Result of an explainability analysis."""

    explainer_type: ExplainerType
    model_type: Optional[ModelType] = None
    prediction: Optional[Any] = None
    base_value: Optional[float] = None
    feature_contributions: list[FeatureContribution] = field(default_factory=list)
    feature_importance: dict[str, float] = field(default_factory=dict)
    raw_explanation: Optional[Any] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    success: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "explainer_type": self.explainer_type.value,
            "model_type": self.model_type.value if self.model_type else None,
            "prediction": self.prediction,
            "base_value": self.base_value,
            "feature_contributions": [
                fc.to_dict() for fc in self.feature_contributions
            ],
            "feature_importance": self.feature_importance,
            "metadata": self.metadata,
            "error": self.error,
            "success": self.success,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2, default=str)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExplainabilityResult":
        """Create from dictionary."""
        feature_contributions = [
            FeatureContribution(**fc) for fc in data.get("feature_contributions", [])
        ]
        return cls(
            explainer_type=ExplainerType(data.get("explainer_type", "unknown")),
            model_type=(
                ModelType(data["model_type"]) if data.get("model_type") else None
            ),
            prediction=data.get("prediction"),
            base_value=data.get("base_value"),
            feature_contributions=feature_contributions,
            feature_importance=data.get("feature_importance", {}),
            metadata=data.get("metadata", {}),
            error=data.get("error"),
            success=data.get("success", True),
        )

    @classmethod
    def error_result(
        cls, error_message: str, explainer_type: ExplainerType = ExplainerType.UNKNOWN
    ) -> "ExplainabilityResult":
        """Create an error result."""
        return cls(
            explainer_type=explainer_type,
            error=error_message,
            success=False,
        )

    def get_top_features(self, n: int = 10) -> list[FeatureContribution]:
        """Get top N most important features by absolute contribution."""
        sorted_contributions = sorted(
            self.feature_contributions,
            key=lambda x: abs(x.contribution),
            reverse=True,
        )
        return sorted_contributions[:n]

    def summary(self) -> str:
        """Generate a human-readable summary."""
        if not self.success:
            return f"Explanation failed: {self.error}"

        lines = [
            f"Explainer: {self.explainer_type.value.upper()}",
            f"Prediction: {self.prediction}",
        ]

        if self.base_value is not None:
            lines.append(f"Base value: {self.base_value:.4f}")

        if self.feature_contributions:
            lines.append("\nTop contributing features:")
            for fc in self.get_top_features(5):
                sign = "+" if fc.contribution >= 0 else ""
                lines.append(f"  {fc.feature_name}: {sign}{fc.contribution:.4f}")

        return "\n".join(lines)


class ModelExplainer(ABC):
    """Base class for model explainability."""

    def __init__(self, model: Any, feature_names: Optional[list[str]] = None):
        """
        Initialize the explainer.

        Args:
            model: The model to explain
            feature_names: Names of input features
        """
        self.model = model
        self.feature_names = feature_names
        self._explainer: Optional[Any] = None

    @property
    @abstractmethod
    def explainer_type(self) -> ExplainerType:
        """Return the type of explainer."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the underlying library is available."""
        pass

    @abstractmethod
    def explain_prediction(self, data: Any, **kwargs) -> ExplainabilityResult:
        """
        Explain a single prediction.

        Args:
            data: Input data to explain
            **kwargs: Additional arguments

        Returns:
            ExplainabilityResult with explanation details
        """
        pass

    @abstractmethod
    def feature_importance(self, data: Any, **kwargs) -> dict[str, float]:
        """
        Calculate global feature importance.

        Args:
            data: Background/training data
            **kwargs: Additional arguments

        Returns:
            Dictionary mapping feature names to importance scores
        """
        pass

    def _get_feature_name(self, index: int) -> str:
        """Get feature name by index, with fallback."""
        if self.feature_names and index < len(self.feature_names):
            return self.feature_names[index]
        return f"feature_{index}"


# Check for library availability
def check_shap_available() -> bool:
    """Check if SHAP library is available."""
    try:
        import shap  # noqa: F401

        return True
    except ImportError:
        return False


def check_lime_available() -> bool:
    """Check if LIME library is available."""
    try:
        import lime  # noqa: F401

        return True
    except ImportError:
        return False


SHAP_AVAILABLE = check_shap_available()
LIME_AVAILABLE = check_lime_available()


# Import submodules
from .lime_explainer import LIMEExplainer  # noqa: E402
from .shap_explainer import SHAPExplainer  # noqa: E402
from .unified import UnifiedExplainer  # noqa: E402

__all__ = [
    "ExplainerType",
    "ModelType",
    "FeatureContribution",
    "ExplainabilityResult",
    "ModelExplainer",
    "SHAPExplainer",
    "LIMEExplainer",
    "UnifiedExplainer",
    "SHAP_AVAILABLE",
    "LIME_AVAILABLE",
    "check_shap_available",
    "check_lime_available",
]
