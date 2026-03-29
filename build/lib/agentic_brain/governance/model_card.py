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
Model Card Template
===================

Pydantic model for AI Model Cards following Google's Model Card format.
Provides standardized documentation for AI/ML models including intended use,
limitations, training data, and ethical considerations.

Reference: https://modelcards.withgoogle.com/

Example:
    >>> from agentic_brain.governance import ModelCard
    >>> card = ModelCard(
    ...     model_name="customer-support-bot",
    ...     version="1.0.0",
    ...     description="AI assistant for customer support queries",
    ...     intended_use=["Customer support chat", "FAQ answering"],
    ...     limitations=["Not suitable for medical advice"],
    ... )
    >>> print(card.to_markdown())
"""

from __future__ import annotations

from datetime import UTC, datetime, timezone
from enum import Enum, StrEnum
from typing import Any

from pydantic import BaseModel, Field


class RiskLevel(StrEnum):
    """Risk level classification for model deployment."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EvaluationMetric(BaseModel):
    """A single evaluation metric with its value and context."""

    name: str = Field(
        ..., description="Name of the metric (e.g., 'accuracy', 'f1_score')"
    )
    value: float = Field(..., description="Metric value")
    threshold: float | None = Field(None, description="Minimum acceptable threshold")
    dataset: str | None = Field(None, description="Dataset used for evaluation")
    date_measured: str | None = Field(None, description="When the metric was measured")


class TrainingDataInfo(BaseModel):
    """Information about training data used for the model."""

    description: str = Field(..., description="Description of the training data")
    source: str | None = Field(None, description="Source of the data")
    size: str | None = Field(
        None, description="Size of the dataset (e.g., '1M records')"
    )
    date_collected: str | None = Field(None, description="When data was collected")
    preprocessing: list[str] | None = Field(
        default_factory=list, description="Preprocessing steps applied"
    )
    known_biases: list[str] | None = Field(
        default_factory=list, description="Known biases in the data"
    )


class EthicalConsideration(BaseModel):
    """An ethical consideration for the model."""

    category: str = Field(
        ..., description="Category (e.g., 'fairness', 'privacy', 'safety')"
    )
    description: str = Field(..., description="Description of the consideration")
    mitigation: str | None = Field(
        None, description="Steps taken to mitigate the concern"
    )
    risk_level: RiskLevel = Field(
        default=RiskLevel.LOW, description="Associated risk level"
    )


class ModelCard(BaseModel):
    """
    Model Card for AI/ML model documentation.

    Follows Google's Model Card format for standardized AI model documentation.
    Captures essential information about model purpose, limitations, and ethics.

    Attributes:
        model_name: Unique identifier for the model
        version: Semantic version string
        description: Brief description of what the model does
        intended_use: List of intended use cases
        limitations: Known limitations and failure modes
        training_data: Information about training data
        evaluation_metrics: Performance metrics
        ethical_considerations: Ethical aspects and mitigations
    """

    # Core identification
    model_name: str = Field(..., description="Unique name/identifier for the model")
    version: str = Field(..., description="Model version (semver format)")
    description: str = Field(
        ..., description="Brief description of the model's purpose"
    )

    # Ownership and dates
    owner: str | None = Field(
        None, description="Team or individual responsible for the model"
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="When the model card was created",
    )
    updated_at: str | None = Field(None, description="Last update timestamp")

    # Use cases
    intended_use: list[str] = Field(
        default_factory=list, description="Intended use cases"
    )
    out_of_scope_use: list[str] = Field(
        default_factory=list, description="Use cases explicitly not supported"
    )

    # Technical details
    model_type: str | None = Field(
        None, description="Type of model (e.g., 'transformer', 'decision_tree')"
    )
    architecture: str | None = Field(None, description="Model architecture details")
    input_format: str | None = Field(None, description="Expected input format")
    output_format: str | None = Field(None, description="Output format produced")

    # Limitations and risks
    limitations: list[str] = Field(
        default_factory=list, description="Known limitations"
    )
    risks: list[str] = Field(
        default_factory=list, description="Potential risks of deployment"
    )

    # Data and evaluation
    training_data: TrainingDataInfo | None = Field(
        None, description="Training data information"
    )
    evaluation_metrics: list[EvaluationMetric] = Field(
        default_factory=list, description="Evaluation metrics"
    )

    # Ethics
    ethical_considerations: list[EthicalConsideration] = Field(
        default_factory=list, description="Ethical considerations and mitigations"
    )

    # Additional metadata
    tags: list[str] = Field(default_factory=list, description="Tags for categorization")
    references: list[str] = Field(
        default_factory=list, description="Related papers or documentation"
    )
    custom_fields: dict[str, Any] = Field(
        default_factory=dict, description="Additional custom fields"
    )

    def to_markdown(self) -> str:
        """
        Export the model card as a Markdown document.

        Returns:
            Formatted Markdown string
        """
        lines = [
            f"# Model Card: {self.model_name}",
            "",
            f"**Version:** {self.version}",
            f"**Created:** {self.created_at}",
        ]

        if self.owner:
            lines.append(f"**Owner:** {self.owner}")
        if self.updated_at:
            lines.append(f"**Updated:** {self.updated_at}")

        lines.extend(["", "## Description", "", self.description, ""])

        if self.model_type or self.architecture:
            lines.extend(["## Technical Details", ""])
            if self.model_type:
                lines.append(f"- **Type:** {self.model_type}")
            if self.architecture:
                lines.append(f"- **Architecture:** {self.architecture}")
            if self.input_format:
                lines.append(f"- **Input Format:** {self.input_format}")
            if self.output_format:
                lines.append(f"- **Output Format:** {self.output_format}")
            lines.append("")

        if self.intended_use:
            lines.extend(["## Intended Use", ""])
            for use in self.intended_use:
                lines.append(f"- {use}")
            lines.append("")

        if self.out_of_scope_use:
            lines.extend(["## Out of Scope Use", ""])
            for use in self.out_of_scope_use:
                lines.append(f"- ⚠️ {use}")
            lines.append("")

        if self.limitations:
            lines.extend(["## Limitations", ""])
            for limitation in self.limitations:
                lines.append(f"- {limitation}")
            lines.append("")

        if self.risks:
            lines.extend(["## Risks", ""])
            for risk in self.risks:
                lines.append(f"- ⚠️ {risk}")
            lines.append("")

        if self.training_data:
            lines.extend(["## Training Data", ""])
            lines.append(self.training_data.description)
            if self.training_data.source:
                lines.append(f"- **Source:** {self.training_data.source}")
            if self.training_data.size:
                lines.append(f"- **Size:** {self.training_data.size}")
            if self.training_data.date_collected:
                lines.append(f"- **Collected:** {self.training_data.date_collected}")
            if self.training_data.preprocessing:
                lines.append("- **Preprocessing:**")
                for step in self.training_data.preprocessing:
                    lines.append(f"  - {step}")
            if self.training_data.known_biases:
                lines.append("- **Known Biases:**")
                for bias in self.training_data.known_biases:
                    lines.append(f"  - ⚠️ {bias}")
            lines.append("")

        if self.evaluation_metrics:
            lines.extend(
                [
                    "## Evaluation Metrics",
                    "",
                    "| Metric | Value | Threshold | Dataset |",
                    "|--------|-------|-----------|---------|",
                ]
            )
            for metric in self.evaluation_metrics:
                threshold = f"{metric.threshold}" if metric.threshold else "N/A"
                dataset = metric.dataset or "N/A"
                lines.append(
                    f"| {metric.name} | {metric.value} | {threshold} | {dataset} |"
                )
            lines.append("")

        if self.ethical_considerations:
            lines.extend(["## Ethical Considerations", ""])
            for consideration in self.ethical_considerations:
                risk_emoji = {
                    "low": "🟢",
                    "medium": "🟡",
                    "high": "🟠",
                    "critical": "🔴",
                }.get(consideration.risk_level.value, "⚪")
                lines.append(f"### {risk_emoji} {consideration.category.title()}")
                lines.append("")
                lines.append(consideration.description)
                if consideration.mitigation:
                    lines.append("")
                    lines.append(f"**Mitigation:** {consideration.mitigation}")
                lines.append("")

        if self.tags:
            lines.extend(["## Tags", ""])
            lines.append(", ".join(f"`{tag}`" for tag in self.tags))
            lines.append("")

        if self.references:
            lines.extend(["## References", ""])
            for ref in self.references:
                lines.append(f"- {ref}")
            lines.append("")

        return "\n".join(lines)

    def to_json(self, indent: int = 2) -> str:
        """
        Export the model card as a JSON string.

        Args:
            indent: JSON indentation level

        Returns:
            JSON-formatted string
        """
        return self.model_dump_json(indent=indent)

    @classmethod
    def from_yaml(cls, yaml_content: str) -> ModelCard:
        """
        Create a ModelCard from YAML content.

        Args:
            yaml_content: YAML string to parse

        Returns:
            ModelCard instance

        Raises:
            ImportError: If PyYAML is not installed
            ValueError: If YAML content is invalid
        """
        try:
            import yaml
        except ImportError:
            raise ImportError(
                "PyYAML is required for YAML support. Install with: pip install pyyaml"
            )

        try:
            data = yaml.safe_load(yaml_content)
            if not isinstance(data, dict):
                raise ValueError("YAML content must be a dictionary")
            return cls(**data)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML content: {e}")

    def to_yaml(self) -> str:
        """
        Export the model card as YAML.

        Returns:
            YAML-formatted string

        Raises:
            ImportError: If PyYAML is not installed
        """
        try:
            import yaml
        except ImportError:
            raise ImportError(
                "PyYAML is required for YAML support. Install with: pip install pyyaml"
            )

        return yaml.dump(self.model_dump(), default_flow_style=False, sort_keys=False)

    def validate_completeness(self) -> dict[str, Any]:
        """
        Check if the model card has all recommended fields filled.

        Returns:
            Dict with completeness score and missing fields
        """
        required_fields = ["model_name", "version", "description"]
        recommended_fields = [
            "owner",
            "intended_use",
            "limitations",
            "training_data",
            "evaluation_metrics",
            "ethical_considerations",
        ]

        missing_required = []
        missing_recommended = []

        for field in required_fields:
            value = getattr(self, field)
            if not value:
                missing_required.append(field)

        for field in recommended_fields:
            value = getattr(self, field)
            if not value or (isinstance(value, list) and len(value) == 0):
                missing_recommended.append(field)

        total_fields = len(required_fields) + len(recommended_fields)
        filled_fields = total_fields - len(missing_required) - len(missing_recommended)
        completeness = round((filled_fields / total_fields) * 100, 1)

        return {
            "completeness_percent": completeness,
            "is_valid": len(missing_required) == 0,
            "missing_required": missing_required,
            "missing_recommended": missing_recommended,
        }
