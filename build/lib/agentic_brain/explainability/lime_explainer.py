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
LIME (Local Interpretable Model-agnostic Explanations) integration.

LIME is an optional dependency. Code gracefully degrades if not installed.
"""

import logging
from typing import Any, Callable, Optional

import numpy as np

from . import (
    ExplainabilityResult,
    ExplainerType,
    FeatureContribution,
    ModelExplainer,
    ModelType,
)

logger = logging.getLogger(__name__)

# Try to import LIME
try:
    import lime
    import lime.lime_tabular
    import lime.lime_text

    try:
        import lime.lime_image

        LIME_IMAGE_AVAILABLE = True
    except ImportError:
        LIME_IMAGE_AVAILABLE = False

    LIME_AVAILABLE = True
except ImportError:
    lime = None  # type: ignore
    LIME_AVAILABLE = False
    LIME_IMAGE_AVAILABLE = False


class LIMEExplainer(ModelExplainer):
    """
    LIME-based model explainer.

    Supports:
    - Tabular data (LimeTabularExplainer)
    - Text data (LimeTextExplainer)
    - Image data (LimeImageExplainer)

    Usage:
        explainer = LIMEExplainer(model, training_data, feature_names=['age', 'income'])
        result = explainer.explain_instance(sample)
        html = explainer.get_explanation_html(sample)
    """

    def __init__(
        self,
        model: Any,
        training_data: Optional[Any] = None,
        feature_names: Optional[list[str]] = None,
        class_names: Optional[list[str]] = None,
        categorical_features: Optional[list[int]] = None,
        mode: str = "classification",
        data_type: ModelType = ModelType.TABULAR,
        kernel_width: Optional[float] = None,
    ):
        """
        Initialize LIME explainer.

        Args:
            model: Model to explain (must have predict or predict_proba)
            training_data: Training data for tabular explainer
            feature_names: Names of input features
            class_names: Names of output classes
            categorical_features: Indices of categorical features
            mode: 'classification' or 'regression'
            data_type: Type of data (TABULAR, TEXT, or IMAGE)
            kernel_width: Width of exponential kernel (default: sqrt(num_features) * 0.75)
        """
        super().__init__(model, feature_names)
        self.training_data = training_data
        self.class_names = class_names
        self.categorical_features = categorical_features or []
        self.mode = mode
        self.data_type = data_type
        self.kernel_width = kernel_width
        self._lime_explainer: Optional[Any] = None

    @property
    def explainer_type(self) -> ExplainerType:
        """Return LIME as the explainer type."""
        return ExplainerType.LIME

    def is_available(self) -> bool:
        """Check if LIME is available."""
        return LIME_AVAILABLE

    def _get_predict_fn(self) -> Callable:
        """Get the appropriate prediction function."""
        if hasattr(self.model, "predict_proba"):
            return self.model.predict_proba
        elif hasattr(self.model, "predict"):
            # Wrap predict for LIME compatibility
            def predict_wrapper(x):
                predictions = self.model.predict(x)
                # Convert to probability-like format for LIME
                if len(predictions.shape) == 1:
                    # Binary classification: convert to 2-column format
                    return np.column_stack([1 - predictions, predictions])
                return predictions

            return predict_wrapper
        elif callable(self.model):
            return self.model
        else:
            raise ValueError("Model must have predict_proba, predict, or be callable")

    def _get_lime_explainer(self) -> Any:
        """Get or create the appropriate LIME explainer."""
        if not LIME_AVAILABLE:
            raise RuntimeError("LIME library is not installed")

        if self._lime_explainer is not None:
            return self._lime_explainer

        if self.data_type == ModelType.TABULAR:
            if self.training_data is None:
                raise ValueError("Tabular explainer requires training_data")

            training_array = np.atleast_2d(self.training_data)

            # Auto-generate feature names if not provided
            if self.feature_names is None:
                self.feature_names = [
                    f"feature_{i}" for i in range(training_array.shape[1])
                ]

            self._lime_explainer = lime.lime_tabular.LimeTabularExplainer(
                training_array,
                feature_names=self.feature_names,
                class_names=self.class_names,
                categorical_features=self.categorical_features,
                mode=self.mode,
                kernel_width=self.kernel_width,
            )

        elif self.data_type == ModelType.TEXT:
            self._lime_explainer = lime.lime_text.LimeTextExplainer(
                class_names=self.class_names,
            )

        elif self.data_type == ModelType.IMAGE:
            if not LIME_IMAGE_AVAILABLE:
                raise RuntimeError("lime.lime_image not available")
            self._lime_explainer = lime.lime_image.LimeImageExplainer()

        else:
            raise ValueError(f"Unsupported data type: {self.data_type}")

        return self._lime_explainer

    def explain_prediction(
        self,
        data: Any,
        num_features: int = 10,
        num_samples: int = 5000,
        **kwargs,
    ) -> ExplainabilityResult:
        """
        Explain a prediction using LIME.

        Args:
            data: Input data to explain
            num_features: Number of features to include in explanation
            num_samples: Number of samples for LIME perturbation
            **kwargs: Additional arguments

        Returns:
            ExplainabilityResult with LIME explanation
        """
        return self.explain_instance(data, num_features, num_samples, **kwargs)

    def explain_instance(
        self,
        data: Any,
        num_features: int = 10,
        num_samples: int = 5000,
        labels: Optional[tuple[int, ...]] = None,
        **kwargs,
    ) -> ExplainabilityResult:
        """
        Explain a single instance using LIME.

        Args:
            data: Input instance to explain
            num_features: Number of features in explanation
            num_samples: Number of perturbation samples
            labels: Class labels to explain (default: top class)
            **kwargs: Additional arguments

        Returns:
            ExplainabilityResult
        """
        if not LIME_AVAILABLE:
            return ExplainabilityResult.error_result(
                "LIME library is not installed. Install with: pip install lime",
                ExplainerType.LIME,
            )

        try:
            explainer = self._get_lime_explainer()
            predict_fn = self._get_predict_fn()

            if self.data_type == ModelType.TABULAR:
                return self._explain_tabular(
                    explainer,
                    predict_fn,
                    data,
                    num_features,
                    num_samples,
                    labels,
                    **kwargs,
                )
            elif self.data_type == ModelType.TEXT:
                return self._explain_text(
                    explainer,
                    predict_fn,
                    data,
                    num_features,
                    num_samples,
                    labels,
                    **kwargs,
                )
            elif self.data_type == ModelType.IMAGE:
                return self._explain_image(
                    explainer, predict_fn, data, num_features, num_samples, **kwargs
                )
            else:
                return ExplainabilityResult.error_result(
                    f"Unsupported data type: {self.data_type}", ExplainerType.LIME
                )

        except Exception as e:
            logger.error(f"LIME explanation failed: {e}")
            return ExplainabilityResult.error_result(str(e), ExplainerType.LIME)

    def _explain_tabular(
        self,
        explainer: Any,
        predict_fn: Callable,
        data: Any,
        num_features: int,
        num_samples: int,
        labels: Optional[tuple[int, ...]],
        **kwargs,
    ) -> ExplainabilityResult:
        """Explain tabular data."""
        data_array = np.atleast_1d(data).flatten()

        explanation = explainer.explain_instance(
            data_array,
            predict_fn,
            num_features=num_features,
            num_samples=num_samples,
            labels=labels,
            **kwargs,
        )

        # Get the explained label
        if labels:
            label = labels[0]
        else:
            label = explanation.top_labels[0] if explanation.top_labels else 0

        # Extract feature contributions
        contributions = []
        feature_importance = {}

        for feature_name, contribution in explanation.as_list(label=label):
            contributions.append(
                FeatureContribution(
                    feature_name=feature_name,
                    contribution=float(contribution),
                )
            )
            feature_importance[feature_name] = abs(float(contribution))

        # Get prediction
        prediction = None
        try:
            pred_proba = predict_fn(data_array.reshape(1, -1))
            prediction = float(pred_proba[0][label])
        except Exception:
            pass

        return ExplainabilityResult(
            explainer_type=ExplainerType.LIME,
            model_type=self.data_type,
            prediction=prediction,
            feature_contributions=contributions,
            feature_importance=feature_importance,
            raw_explanation=explanation,
            metadata={
                "num_features": num_features,
                "num_samples": num_samples,
                "explained_label": label,
                "intercept": (
                    float(explanation.intercept[label])
                    if hasattr(explanation, "intercept")
                    else None
                ),
                "local_pred": (
                    float(explanation.local_pred[0])
                    if hasattr(explanation, "local_pred")
                    else None
                ),
                "score": (
                    float(explanation.score) if hasattr(explanation, "score") else None
                ),
            },
            success=True,
        )

    def _explain_text(
        self,
        explainer: Any,
        predict_fn: Callable,
        data: str,
        num_features: int,
        num_samples: int,
        labels: Optional[tuple[int, ...]],
        **kwargs,
    ) -> ExplainabilityResult:
        """Explain text data."""
        explanation = explainer.explain_instance(
            data,
            predict_fn,
            num_features=num_features,
            num_samples=num_samples,
            labels=labels,
            **kwargs,
        )

        label = (
            labels[0]
            if labels
            else (explanation.top_labels[0] if explanation.top_labels else 0)
        )

        contributions = []
        feature_importance = {}

        for word, contribution in explanation.as_list(label=label):
            contributions.append(
                FeatureContribution(
                    feature_name=word,
                    contribution=float(contribution),
                )
            )
            feature_importance[word] = abs(float(contribution))

        return ExplainabilityResult(
            explainer_type=ExplainerType.LIME,
            model_type=ModelType.TEXT,
            feature_contributions=contributions,
            feature_importance=feature_importance,
            raw_explanation=explanation,
            metadata={
                "num_features": num_features,
                "explained_label": label,
                "text_length": len(data),
            },
            success=True,
        )

    def _explain_image(
        self,
        explainer: Any,
        predict_fn: Callable,
        data: Any,
        num_features: int,
        num_samples: int,
        **kwargs,
    ) -> ExplainabilityResult:
        """Explain image data."""
        if not LIME_IMAGE_AVAILABLE:
            return ExplainabilityResult.error_result(
                "LIME image explainer not available", ExplainerType.LIME
            )

        # Image explanation returns segments, not features
        explanation = explainer.explain_instance(
            data,
            predict_fn,
            top_labels=kwargs.get("top_labels", 5),
            hide_color=kwargs.get("hide_color", 0),
            num_samples=num_samples,
        )

        # Get top label
        top_label = explanation.top_labels[0] if explanation.top_labels else 0

        # Get image and mask for visualization
        temp, mask = explanation.get_image_and_mask(
            top_label,
            positive_only=kwargs.get("positive_only", True),
            num_features=num_features,
            hide_rest=kwargs.get("hide_rest", False),
        )

        return ExplainabilityResult(
            explainer_type=ExplainerType.LIME,
            model_type=ModelType.IMAGE,
            raw_explanation=explanation,
            metadata={
                "top_label": top_label,
                "segments_shape": mask.shape,
                "num_samples": num_samples,
            },
            success=True,
        )

    def get_explanation_html(
        self,
        data: Any,
        num_features: int = 10,
        num_samples: int = 5000,
        **kwargs,
    ) -> str:
        """
        Get HTML representation of the explanation.

        Args:
            data: Instance to explain
            num_features: Number of features
            num_samples: Number of samples
            **kwargs: Additional arguments

        Returns:
            HTML string with interactive explanation
        """
        if not LIME_AVAILABLE:
            return "<p>LIME library is not installed</p>"

        try:
            result = self.explain_instance(data, num_features, num_samples, **kwargs)

            if not result.success:
                return f"<p>Error: {result.error}</p>"

            if result.raw_explanation and hasattr(result.raw_explanation, "as_html"):
                return result.raw_explanation.as_html()

            # Fallback: generate simple HTML
            html = ["<div class='lime-explanation'>"]
            html.append("<h3>LIME Explanation</h3>")

            if result.prediction is not None:
                html.append(
                    f"<p><strong>Prediction:</strong> {result.prediction:.4f}</p>"
                )

            html.append("<table>")
            html.append("<tr><th>Feature</th><th>Contribution</th></tr>")

            for fc in result.get_top_features(num_features):
                color = "green" if fc.contribution > 0 else "red"
                html.append(
                    f"<tr><td>{fc.feature_name}</td>"
                    f"<td style='color:{color}'>{fc.contribution:+.4f}</td></tr>"
                )

            html.append("</table>")
            html.append("</div>")

            return "\n".join(html)

        except Exception as e:
            return f"<p>Error generating explanation: {e}</p>"

    def feature_importance(
        self,
        data: Any,
        num_samples: int = 100,
        **kwargs,
    ) -> dict[str, float]:
        """
        Calculate feature importance by averaging over multiple samples.

        Args:
            data: Dataset (multiple samples)
            num_samples: Samples per explanation
            **kwargs: Additional arguments

        Returns:
            Dictionary of feature importances
        """
        if not LIME_AVAILABLE:
            return {}

        try:
            data_array = np.atleast_2d(data)
            importance_sum: dict[str, float] = {}
            count = 0

            # Limit to reasonable number of samples for efficiency
            max_samples = min(len(data_array), 50)

            for i in range(max_samples):
                result = self.explain_instance(
                    data_array[i], num_samples=num_samples, **kwargs
                )
                if result.success:
                    for name, imp in result.feature_importance.items():
                        importance_sum[name] = importance_sum.get(name, 0) + imp
                    count += 1

            if count > 0:
                return {k: v / count for k, v in importance_sum.items()}

            return {}

        except Exception as e:
            logger.error(f"Failed to compute feature importance: {e}")
            return {}


# Convenience function
def explain_with_lime(
    model: Any,
    data: Any,
    training_data: Any,
    feature_names: Optional[list[str]] = None,
    mode: str = "classification",
    **kwargs,
) -> ExplainabilityResult:
    """
    Convenience function to explain a prediction with LIME.

    Args:
        model: Model to explain
        data: Instance to explain
        training_data: Training data for the explainer
        feature_names: Names of features
        mode: 'classification' or 'regression'
        **kwargs: Additional arguments

    Returns:
        ExplainabilityResult
    """
    explainer = LIMEExplainer(
        model,
        training_data=training_data,
        feature_names=feature_names,
        mode=mode,
    )
    return explainer.explain_instance(data, **kwargs)
