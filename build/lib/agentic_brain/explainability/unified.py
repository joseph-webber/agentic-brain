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
Unified explainability interface combining SHAP and LIME.

Provides a single interface that auto-selects the best explainer
based on model type and data characteristics.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Optional, Union

from . import (
    LIME_AVAILABLE,
    SHAP_AVAILABLE,
    ExplainabilityResult,
    ExplainerType,
    ModelType,
)
from .lime_explainer import LIMEExplainer
from .shap_explainer import SHAPExplainer

logger = logging.getLogger(__name__)


@dataclass
class ComparisonResult:
    """Result of comparing SHAP and LIME explanations."""

    shap_result: Optional[ExplainabilityResult]
    lime_result: Optional[ExplainabilityResult]
    agreement_score: float
    top_features_overlap: list[str]
    divergent_features: list[str]
    recommendation: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "shap_result": self.shap_result.to_dict() if self.shap_result else None,
            "lime_result": self.lime_result.to_dict() if self.lime_result else None,
            "agreement_score": self.agreement_score,
            "top_features_overlap": self.top_features_overlap,
            "divergent_features": self.divergent_features,
            "recommendation": self.recommendation,
        }


class UnifiedExplainer:
    """
    Unified interface for model explainability using SHAP and LIME.

    Auto-selects the best explainer based on:
    - Model type (tree, linear, deep learning)
    - Data type (tabular, text, image)
    - Library availability

    Usage:
        explainer = UnifiedExplainer(model, training_data, feature_names)
        result = explainer.explain(instance)
        comparison = explainer.compare_explanations(instance)
        report = explainer.export_report(instance)
    """

    def __init__(
        self,
        model: Any,
        training_data: Optional[Any] = None,
        feature_names: Optional[list[str]] = None,
        class_names: Optional[list[str]] = None,
        model_type: Optional[ModelType] = None,
        data_type: ModelType = ModelType.TABULAR,
        preferred_explainer: Optional[ExplainerType] = None,
    ):
        """
        Initialize the unified explainer.

        Args:
            model: Model to explain
            training_data: Training/background data
            feature_names: Names of features
            class_names: Names of output classes
            model_type: Type of model (auto-detected if None)
            data_type: Type of data (TABULAR, TEXT, IMAGE)
            preferred_explainer: Force use of specific explainer
        """
        self.model = model
        self.training_data = training_data
        self.feature_names = feature_names
        self.class_names = class_names
        self.data_type = data_type
        self.preferred_explainer = preferred_explainer

        # Auto-detect model type
        if model_type is None:
            self._model_type = self._detect_model_type()
        else:
            self._model_type = model_type

        # Initialize explainers lazily
        self._shap_explainer: Optional[SHAPExplainer] = None
        self._lime_explainer: Optional[LIMEExplainer] = None

    def _detect_model_type(self) -> ModelType:
        """Detect model type from the model object."""
        model_class = type(self.model).__name__.lower()
        module = getattr(type(self.model), "__module__", "").lower()

        # Tree models
        tree_keywords = ["forest", "tree", "xgb", "lgbm", "catboost", "gradient"]
        if any(k in model_class or k in module for k in tree_keywords):
            return ModelType.TREE

        # Linear models
        linear_keywords = ["linear", "logistic", "ridge", "lasso"]
        if any(k in model_class for k in linear_keywords):
            return ModelType.LINEAR

        # Deep learning
        deep_keywords = ["keras", "torch", "tensorflow", "neural", "nn", "sequential"]
        if any(k in model_class or k in module for k in deep_keywords):
            return ModelType.DEEP

        return ModelType.KERNEL

    @property
    def shap_explainer(self) -> SHAPExplainer:
        """Get or create SHAP explainer."""
        if self._shap_explainer is None:
            self._shap_explainer = SHAPExplainer(
                self.model,
                feature_names=self.feature_names,
                model_type=self._model_type,
                background_data=self.training_data,
            )
        return self._shap_explainer

    @property
    def lime_explainer(self) -> LIMEExplainer:
        """Get or create LIME explainer."""
        if self._lime_explainer is None:
            self._lime_explainer = LIMEExplainer(
                self.model,
                training_data=self.training_data,
                feature_names=self.feature_names,
                class_names=self.class_names,
                data_type=self.data_type,
            )
        return self._lime_explainer

    def _select_explainer(self) -> ExplainerType:
        """Select the best explainer based on model and data type."""
        # Honor user preference if set
        if self.preferred_explainer:
            if self.preferred_explainer == ExplainerType.SHAP and SHAP_AVAILABLE:
                return ExplainerType.SHAP
            elif self.preferred_explainer == ExplainerType.LIME and LIME_AVAILABLE:
                return ExplainerType.LIME

        # Selection logic based on model type
        if self._model_type == ModelType.TREE:
            # SHAP TreeExplainer is optimal for tree models
            if SHAP_AVAILABLE:
                return ExplainerType.SHAP
            elif LIME_AVAILABLE:
                return ExplainerType.LIME

        elif self._model_type == ModelType.LINEAR:
            # Both work well, prefer SHAP for consistency
            if SHAP_AVAILABLE:
                return ExplainerType.SHAP
            elif LIME_AVAILABLE:
                return ExplainerType.LIME

        elif self._model_type == ModelType.DEEP:
            # SHAP DeepExplainer is good, but LIME is simpler
            if LIME_AVAILABLE and self.training_data is not None:
                return ExplainerType.LIME
            elif SHAP_AVAILABLE and self.training_data is not None:
                return ExplainerType.SHAP

        elif self.data_type == ModelType.TEXT:
            # LIME is better for text
            if LIME_AVAILABLE:
                return ExplainerType.LIME
            elif SHAP_AVAILABLE:
                return ExplainerType.SHAP

        elif self.data_type == ModelType.IMAGE:
            # LIME has dedicated image support
            if LIME_AVAILABLE:
                return ExplainerType.LIME

        # Default: prefer SHAP, fall back to LIME
        if SHAP_AVAILABLE:
            return ExplainerType.SHAP
        elif LIME_AVAILABLE:
            return ExplainerType.LIME

        return ExplainerType.UNKNOWN

    def explain(
        self,
        data: Any,
        explainer_type: Optional[ExplainerType] = None,
        num_features: int = 10,
        **kwargs,
    ) -> ExplainabilityResult:
        """
        Explain a prediction using the best available explainer.

        Args:
            data: Instance to explain
            explainer_type: Force specific explainer (auto-select if None)
            num_features: Number of features in explanation
            **kwargs: Additional arguments passed to explainer

        Returns:
            ExplainabilityResult
        """
        selected = explainer_type or self._select_explainer()

        if selected == ExplainerType.SHAP:
            if not SHAP_AVAILABLE:
                return ExplainabilityResult.error_result(
                    "SHAP requested but not available", ExplainerType.SHAP
                )
            return self.shap_explainer.explain_prediction(data, **kwargs)

        elif selected == ExplainerType.LIME:
            if not LIME_AVAILABLE:
                return ExplainabilityResult.error_result(
                    "LIME requested but not available", ExplainerType.LIME
                )
            return self.lime_explainer.explain_instance(
                data, num_features=num_features, **kwargs
            )

        return ExplainabilityResult.error_result(
            "No explainer available. Install SHAP or LIME.",
            ExplainerType.UNKNOWN,
        )

    def compare_explanations(
        self,
        data: Any,
        top_n: int = 10,
        **kwargs,
    ) -> ComparisonResult:
        """
        Compare SHAP and LIME explanations for the same instance.

        Args:
            data: Instance to explain
            top_n: Number of top features to compare
            **kwargs: Additional arguments

        Returns:
            ComparisonResult with both explanations and comparison metrics
        """
        shap_result = None
        lime_result = None

        # Get SHAP explanation
        if SHAP_AVAILABLE:
            try:
                shap_result = self.shap_explainer.explain_prediction(data, **kwargs)
            except Exception as e:
                logger.warning(f"SHAP explanation failed: {e}")

        # Get LIME explanation
        if LIME_AVAILABLE:
            try:
                lime_result = self.lime_explainer.explain_instance(
                    data, num_features=top_n, **kwargs
                )
            except Exception as e:
                logger.warning(f"LIME explanation failed: {e}")

        # Compare results
        agreement_score = 0.0
        top_features_overlap: list[str] = []
        divergent_features: list[str] = []
        recommendation = "Unable to compare"

        if shap_result and shap_result.success and lime_result and lime_result.success:
            # Get top features from each
            shap_top = {fc.feature_name for fc in shap_result.get_top_features(top_n)}
            lime_top = set(lime_result.feature_importance.keys())

            # Calculate overlap
            overlap = shap_top.intersection(lime_top)
            top_features_overlap = list(overlap)

            # Calculate divergence
            divergent_features = list(shap_top.symmetric_difference(lime_top))

            # Agreement score: Jaccard similarity
            union = shap_top.union(lime_top)
            if union:
                agreement_score = len(overlap) / len(union)

            # Generate recommendation
            if agreement_score > 0.7:
                recommendation = "High agreement - explanations are consistent"
            elif agreement_score > 0.4:
                recommendation = "Moderate agreement - consider both perspectives"
            else:
                recommendation = "Low agreement - investigate model behavior further"

        elif shap_result and shap_result.success:
            recommendation = "Only SHAP available - use SHAP explanation"
        elif lime_result and lime_result.success:
            recommendation = "Only LIME available - use LIME explanation"

        return ComparisonResult(
            shap_result=shap_result,
            lime_result=lime_result,
            agreement_score=agreement_score,
            top_features_overlap=top_features_overlap,
            divergent_features=divergent_features,
            recommendation=recommendation,
        )

    def export_report(
        self,
        data: Any,
        format: str = "json",
        include_comparison: bool = True,
        **kwargs,
    ) -> Union[str, dict[str, Any]]:
        """
        Export a comprehensive explainability report.

        Args:
            data: Instance to explain
            format: Output format ('json', 'dict', 'html')
            include_comparison: Include SHAP vs LIME comparison
            **kwargs: Additional arguments

        Returns:
            Report in requested format
        """
        report: dict[str, Any] = {
            "model_type": self._model_type.value,
            "data_type": self.data_type.value,
            "shap_available": SHAP_AVAILABLE,
            "lime_available": LIME_AVAILABLE,
            "selected_explainer": self._select_explainer().value,
        }

        # Primary explanation
        primary_result = self.explain(data, **kwargs)
        report["primary_explanation"] = primary_result.to_dict()

        # Comparison if requested
        if include_comparison and SHAP_AVAILABLE and LIME_AVAILABLE:
            comparison = self.compare_explanations(data, **kwargs)
            report["comparison"] = comparison.to_dict()

        # Feature importance summary
        if primary_result.success:
            report["feature_importance_summary"] = {
                "top_5": [
                    {"name": fc.feature_name, "contribution": fc.contribution}
                    for fc in primary_result.get_top_features(5)
                ]
            }

        # Format output
        if format == "dict":
            return report
        elif format == "html":
            return self._format_html_report(report)
        else:  # json
            return json.dumps(report, indent=2, default=str)

    def _format_html_report(self, report: dict[str, Any]) -> str:
        """Format report as HTML."""
        html = [
            "<!DOCTYPE html>",
            "<html><head>",
            "<title>Explainability Report</title>",
            "<style>",
            "body { font-family: Arial, sans-serif; margin: 20px; }",
            "table { border-collapse: collapse; margin: 10px 0; }",
            "th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }",
            "th { background-color: #4CAF50; color: white; }",
            ".positive { color: green; }",
            ".negative { color: red; }",
            ".section { margin: 20px 0; padding: 15px; border: 1px solid #ddd; }",
            "</style>",
            "</head><body>",
            "<h1>Model Explainability Report</h1>",
        ]

        # Model info
        html.append("<div class='section'>")
        html.append("<h2>Model Information</h2>")
        html.append(f"<p><strong>Model Type:</strong> {report['model_type']}</p>")
        html.append(f"<p><strong>Data Type:</strong> {report['data_type']}</p>")
        html.append(
            f"<p><strong>Selected Explainer:</strong> {report['selected_explainer']}</p>"
        )
        html.append("</div>")

        # Primary explanation
        if "primary_explanation" in report:
            exp = report["primary_explanation"]
            html.append("<div class='section'>")
            html.append(
                f"<h2>{exp.get('explainer_type', 'Unknown').upper()} Explanation</h2>"
            )

            if exp.get("prediction") is not None:
                html.append(f"<p><strong>Prediction:</strong> {exp['prediction']}</p>")

            if exp.get("feature_contributions"):
                html.append("<h3>Feature Contributions</h3>")
                html.append("<table><tr><th>Feature</th><th>Contribution</th></tr>")
                for fc in exp["feature_contributions"][:10]:
                    css_class = "positive" if fc["contribution"] >= 0 else "negative"
                    html.append(
                        f"<tr><td>{fc['feature_name']}</td>"
                        f"<td class='{css_class}'>{fc['contribution']:+.4f}</td></tr>"
                    )
                html.append("</table>")

            html.append("</div>")

        # Comparison
        if "comparison" in report:
            comp = report["comparison"]
            html.append("<div class='section'>")
            html.append("<h2>SHAP vs LIME Comparison</h2>")
            html.append(
                f"<p><strong>Agreement Score:</strong> {comp['agreement_score']:.2%}</p>"
            )
            html.append(
                f"<p><strong>Recommendation:</strong> {comp['recommendation']}</p>"
            )

            if comp["top_features_overlap"]:
                html.append(
                    f"<p><strong>Overlapping Features:</strong> {', '.join(comp['top_features_overlap'])}</p>"
                )

            html.append("</div>")

        html.append("</body></html>")
        return "\n".join(html)

    def get_available_explainers(self) -> list[ExplainerType]:
        """Return list of available explainers."""
        available = []
        if SHAP_AVAILABLE:
            available.append(ExplainerType.SHAP)
        if LIME_AVAILABLE:
            available.append(ExplainerType.LIME)
        return available

    def availability_status(self) -> dict[str, Any]:
        """Get status of all explainability tools."""
        return {
            "shap": {
                "available": SHAP_AVAILABLE,
                "install_command": "pip install shap",
            },
            "lime": {
                "available": LIME_AVAILABLE,
                "install_command": "pip install lime",
            },
            "recommended_explainer": self._select_explainer().value,
            "model_type_detected": self._model_type.value,
            "data_type": self.data_type.value,
        }
