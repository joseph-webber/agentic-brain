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
SHAP (SHapley Additive exPlanations) integration for model explainability.

SHAP is an optional dependency. Code gracefully degrades if not installed.
"""

import logging
from typing import Any, Optional

import numpy as np

from . import (
    ExplainabilityResult,
    ExplainerType,
    FeatureContribution,
    ModelExplainer,
    ModelType,
)

logger = logging.getLogger(__name__)

# Try to import SHAP
try:
    import shap

    SHAP_AVAILABLE = True
except ImportError:
    shap = None  # type: ignore
    SHAP_AVAILABLE = False


class SHAPExplainer(ModelExplainer):
    """
    SHAP-based model explainer.

    Supports multiple explainer types:
    - TreeExplainer: For tree-based models (XGBoost, LightGBM, RandomForest)
    - KernelExplainer: Model-agnostic (slower but works with any model)
    - DeepExplainer: For deep learning models (TensorFlow/PyTorch)
    - LinearExplainer: For linear models

    Usage:
        explainer = SHAPExplainer(model, feature_names=['age', 'income'])
        result = explainer.explain_prediction(sample_data)
        importance = explainer.feature_importance(background_data)
    """

    def __init__(
        self,
        model: Any,
        feature_names: Optional[list[str]] = None,
        model_type: Optional[ModelType] = None,
        background_data: Optional[Any] = None,
    ):
        """
        Initialize SHAP explainer.

        Args:
            model: The model to explain
            feature_names: Names of input features
            model_type: Type of model (auto-detected if not provided)
            background_data: Background data for KernelExplainer
        """
        super().__init__(model, feature_names)
        self.model_type = model_type or self._detect_model_type()
        self.background_data = background_data
        self._shap_explainer: Optional[Any] = None

    @property
    def explainer_type(self) -> ExplainerType:
        """Return SHAP as the explainer type."""
        return ExplainerType.SHAP

    def is_available(self) -> bool:
        """Check if SHAP is available."""
        return SHAP_AVAILABLE

    def _detect_model_type(self) -> ModelType:
        """Auto-detect model type from the model object."""
        model_class = type(self.model).__name__.lower()
        module = (
            type(self.model).__module__.lower()
            if hasattr(type(self.model), "__module__")
            else ""
        )

        # Tree-based models
        tree_indicators = [
            "randomforest",
            "xgb",
            "lightgbm",
            "lgbm",
            "catboost",
            "gradientboosting",
            "decisiontree",
            "extratrees",
        ]
        if any(t in model_class or t in module for t in tree_indicators):
            return ModelType.TREE

        # Linear models
        linear_indicators = ["linear", "logistic", "ridge", "lasso", "elasticnet"]
        if any(l in model_class for l in linear_indicators):
            return ModelType.LINEAR

        # Deep learning models
        deep_indicators = ["keras", "tensorflow", "torch", "nn", "neural", "sequential"]
        if any(d in model_class or d in module for d in deep_indicators):
            return ModelType.DEEP

        # Default to kernel (model-agnostic)
        return ModelType.KERNEL

    def _get_shap_explainer(self, data: Optional[Any] = None) -> Any:
        """Get or create the appropriate SHAP explainer."""
        if not SHAP_AVAILABLE:
            raise RuntimeError("SHAP library is not installed")

        if self._shap_explainer is not None:
            return self._shap_explainer

        background = data if data is not None else self.background_data

        try:
            if self.model_type == ModelType.TREE:
                self._shap_explainer = shap.TreeExplainer(self.model)
            elif self.model_type == ModelType.LINEAR:
                if background is not None:
                    self._shap_explainer = shap.LinearExplainer(self.model, background)
                else:
                    # Fall back to Kernel if no background data
                    raise ValueError("LinearExplainer requires background data")
            elif self.model_type == ModelType.DEEP:
                if background is not None:
                    self._shap_explainer = shap.DeepExplainer(self.model, background)
                else:
                    raise ValueError("DeepExplainer requires background data")
            else:  # KERNEL (model-agnostic)
                if background is None:
                    raise ValueError("KernelExplainer requires background data")

                # Get prediction function
                if hasattr(self.model, "predict_proba"):
                    predict_fn = self.model.predict_proba
                elif hasattr(self.model, "predict"):
                    predict_fn = self.model.predict
                elif callable(self.model):
                    predict_fn = self.model
                else:
                    raise ValueError(
                        "Model must have predict/predict_proba or be callable"
                    )

                self._shap_explainer = shap.KernelExplainer(predict_fn, background)

        except Exception as e:
            logger.warning(f"Failed to create {self.model_type.value} explainer: {e}")
            # Try KernelExplainer as fallback
            if self.model_type != ModelType.KERNEL and background is not None:
                logger.info("Falling back to KernelExplainer")
                predict_fn = getattr(
                    self.model,
                    "predict_proba",
                    getattr(self.model, "predict", self.model),
                )
                self._shap_explainer = shap.KernelExplainer(predict_fn, background)
            else:
                raise

        return self._shap_explainer

    def explain_prediction(
        self,
        data: Any,
        check_additivity: bool = True,
        **kwargs,
    ) -> ExplainabilityResult:
        """
        Explain a single prediction or batch of predictions.

        Args:
            data: Input data to explain (1D or 2D array)
            check_additivity: Whether to check SHAP additivity
            **kwargs: Additional arguments passed to SHAP

        Returns:
            ExplainabilityResult with SHAP values and feature contributions
        """
        if not SHAP_AVAILABLE:
            return ExplainabilityResult.error_result(
                "SHAP library is not installed. Install with: pip install shap",
                ExplainerType.SHAP,
            )

        try:
            # Ensure data is 2D
            data_array = np.atleast_2d(data)

            # Get explainer
            explainer = self._get_shap_explainer(self.background_data)

            # Calculate SHAP values
            if self.model_type == ModelType.TREE:
                shap_values = explainer.shap_values(
                    data_array, check_additivity=check_additivity
                )
            else:
                shap_values = explainer.shap_values(data_array, **kwargs)

            # Handle multi-class output
            if isinstance(shap_values, list):
                # Use the positive class for binary classification
                shap_values = (
                    shap_values[1] if len(shap_values) == 2 else shap_values[0]
                )

            # Get base value
            if hasattr(explainer, "expected_value"):
                base_value = explainer.expected_value
                if isinstance(base_value, (list, np.ndarray)):
                    base_value = float(
                        base_value[1] if len(base_value) == 2 else base_value[0]
                    )
                else:
                    base_value = float(base_value)
            else:
                base_value = None

            # Build feature contributions
            contributions = []
            shap_row = shap_values[0] if len(shap_values.shape) > 1 else shap_values
            data_row = data_array[0]

            for i, shap_val in enumerate(shap_row):
                contributions.append(
                    FeatureContribution(
                        feature_name=self._get_feature_name(i),
                        contribution=float(shap_val),
                        base_value=base_value,
                        feature_value=float(data_row[i]) if i < len(data_row) else None,
                    )
                )

            # Get prediction
            prediction = None
            if hasattr(self.model, "predict"):
                try:
                    prediction = self.model.predict(data_array)[0]
                    if hasattr(prediction, "item"):
                        prediction = prediction.item()
                except Exception:
                    pass

            # Calculate feature importance from absolute values
            importance = {}
            for fc in contributions:
                importance[fc.feature_name] = abs(fc.contribution)

            return ExplainabilityResult(
                explainer_type=ExplainerType.SHAP,
                model_type=self.model_type,
                prediction=prediction,
                base_value=base_value,
                feature_contributions=contributions,
                feature_importance=importance,
                raw_explanation=shap_values,
                metadata={
                    "num_features": len(contributions),
                    "explainer_class": type(explainer).__name__,
                },
                success=True,
            )

        except Exception as e:
            logger.error(f"SHAP explanation failed: {e}")
            return ExplainabilityResult.error_result(str(e), ExplainerType.SHAP)

    def feature_importance(
        self,
        data: Any,
        method: str = "mean_abs",
        **kwargs,
    ) -> dict[str, float]:
        """
        Calculate global feature importance using SHAP values.

        Args:
            data: Dataset to compute importance over
            method: Aggregation method ('mean_abs', 'mean', 'max')
            **kwargs: Additional arguments

        Returns:
            Dictionary mapping feature names to importance scores
        """
        if not SHAP_AVAILABLE:
            logger.warning("SHAP not available, returning empty importance")
            return {}

        try:
            data_array = np.atleast_2d(data)
            explainer = self._get_shap_explainer(self.background_data)
            shap_values = explainer.shap_values(data_array, **kwargs)

            # Handle multi-class
            if isinstance(shap_values, list):
                shap_values = (
                    shap_values[1] if len(shap_values) == 2 else shap_values[0]
                )

            # Aggregate across samples
            if method == "mean_abs":
                importance_values = np.abs(shap_values).mean(axis=0)
            elif method == "mean":
                importance_values = shap_values.mean(axis=0)
            elif method == "max":
                importance_values = np.abs(shap_values).max(axis=0)
            else:
                importance_values = np.abs(shap_values).mean(axis=0)

            # Build importance dict
            importance = {}
            for i, val in enumerate(importance_values):
                importance[self._get_feature_name(i)] = float(val)

            return importance

        except Exception as e:
            logger.error(f"Failed to compute feature importance: {e}")
            return {}

    def summary_plot_data(
        self,
        data: Any,
        max_display: int = 20,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Get data for a SHAP summary plot (without actually plotting).

        Args:
            data: Dataset to explain
            max_display: Maximum features to include
            **kwargs: Additional arguments

        Returns:
            Dictionary with data needed to create a summary plot
        """
        if not SHAP_AVAILABLE:
            return {"error": "SHAP not available"}

        try:
            data_array = np.atleast_2d(data)
            explainer = self._get_shap_explainer(self.background_data)
            shap_values = explainer.shap_values(data_array, **kwargs)

            if isinstance(shap_values, list):
                shap_values = (
                    shap_values[1] if len(shap_values) == 2 else shap_values[0]
                )

            # Get feature importance for ordering
            importance = np.abs(shap_values).mean(axis=0)
            feature_order = np.argsort(importance)[::-1][:max_display]

            # Build plot data
            plot_data = {
                "feature_names": [self._get_feature_name(i) for i in feature_order],
                "shap_values": shap_values[:, feature_order].tolist(),
                "feature_values": data_array[:, feature_order].tolist(),
                "base_value": (
                    float(explainer.expected_value)
                    if hasattr(explainer, "expected_value")
                    and not isinstance(explainer.expected_value, (list, np.ndarray))
                    else None
                ),
                "importance_order": feature_order.tolist(),
            }

            return plot_data

        except Exception as e:
            logger.error(f"Failed to generate summary plot data: {e}")
            return {"error": str(e)}

    def waterfall_plot_data(self, data: Any, **kwargs) -> dict[str, Any]:
        """
        Get data for a SHAP waterfall plot for a single prediction.

        Args:
            data: Single sample to explain
            **kwargs: Additional arguments

        Returns:
            Dictionary with waterfall plot data
        """
        result = self.explain_prediction(data, **kwargs)

        if not result.success:
            return {"error": result.error}

        # Sort by absolute contribution
        sorted_contributions = sorted(
            result.feature_contributions,
            key=lambda x: abs(x.contribution),
            reverse=True,
        )

        return {
            "base_value": result.base_value,
            "prediction": result.prediction,
            "features": [
                {
                    "name": fc.feature_name,
                    "contribution": fc.contribution,
                    "value": fc.feature_value,
                }
                for fc in sorted_contributions
            ],
        }


# Convenience function
def explain_with_shap(
    model: Any,
    data: Any,
    feature_names: Optional[list[str]] = None,
    background_data: Optional[Any] = None,
    **kwargs,
) -> ExplainabilityResult:
    """
    Convenience function to explain a prediction with SHAP.

    Args:
        model: Model to explain
        data: Data to explain
        feature_names: Names of features
        background_data: Background data for kernel explainer
        **kwargs: Additional arguments

    Returns:
        ExplainabilityResult
    """
    explainer = SHAPExplainer(
        model, feature_names=feature_names, background_data=background_data
    )
    return explainer.explain_prediction(data, **kwargs)
