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

"""LoRA configuration utilities for fine-tuning.

Provides configuration presets for LoRA and QLoRA fine-tuning.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class QuantizationType(Enum):
    """Quantization types for QLoRA."""

    NONE = "none"
    INT8 = "int8"
    INT4 = "int4"
    NF4 = "nf4"  # Normal Float 4-bit
    FP4 = "fp4"  # Float 4-bit


class TaskType(Enum):
    """Task types for LoRA configuration."""

    CAUSAL_LM = "CAUSAL_LM"
    SEQ_2_SEQ_LM = "SEQ_2_SEQ_LM"
    TOKEN_CLS = "TOKEN_CLS"
    SEQ_CLS = "SEQ_CLS"
    QUESTION_ANS = "QUESTION_ANS"


# Default target modules for common architectures
DEFAULT_TARGET_MODULES: dict[str, list[str]] = {
    "llama": [
        "q_proj",
        "k_proj",
        "v_proj",
        "o_proj",
        "gate_proj",
        "up_proj",
        "down_proj",
    ],
    "mistral": [
        "q_proj",
        "k_proj",
        "v_proj",
        "o_proj",
        "gate_proj",
        "up_proj",
        "down_proj",
    ],
    "gpt2": ["c_attn", "c_proj", "c_fc"],
    "gpt_neox": ["query_key_value", "dense", "dense_h_to_4h", "dense_4h_to_h"],
    "falcon": ["query_key_value", "dense", "dense_h_to_4h", "dense_4h_to_h"],
    "bloom": ["query_key_value", "dense", "dense_h_to_4h", "dense_4h_to_h"],
    "opt": ["q_proj", "k_proj", "v_proj", "out_proj", "fc1", "fc2"],
    "phi": ["q_proj", "k_proj", "v_proj", "dense", "fc1", "fc2"],
    "qwen": ["c_attn", "c_proj", "w1", "w2"],
    "gemma": [
        "q_proj",
        "k_proj",
        "v_proj",
        "o_proj",
        "gate_proj",
        "up_proj",
        "down_proj",
    ],
}


@dataclass
class LoRAConfig:
    """Configuration for LoRA (Low-Rank Adaptation) fine-tuning.

    Attributes:
        r: Rank of the low-rank matrices (typically 8-64)
        lora_alpha: Scaling factor (typically 16-32)
        lora_dropout: Dropout probability for LoRA layers
        target_modules: List of module names to apply LoRA to
        bias: Bias training mode ("none", "all", "lora_only")
        task_type: Type of task for the model
        modules_to_save: Additional modules to train fully
        fan_in_fan_out: Set for Conv1D layers (GPT-2 style)
        inference_mode: Whether in inference mode
    """

    r: int = 8
    lora_alpha: int = 16
    lora_dropout: float = 0.05
    target_modules: list[str] | None = None
    bias: str = "none"
    task_type: TaskType = TaskType.CAUSAL_LM
    modules_to_save: list[str] | None = None
    fan_in_fan_out: bool = False
    inference_mode: bool = False

    # QLoRA-specific settings
    use_qlora: bool = False
    quantization_type: QuantizationType = QuantizationType.NONE
    double_quantization: bool = False
    compute_dtype: str = "float16"

    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.r < 1:
            raise ValueError("Rank (r) must be at least 1")
        if self.lora_alpha < 1:
            raise ValueError("Alpha must be at least 1")
        if not 0 <= self.lora_dropout < 1:
            raise ValueError("Dropout must be in [0, 1)")
        if self.bias not in ("none", "all", "lora_only"):
            raise ValueError("Bias must be 'none', 'all', or 'lora_only'")

    def validate(self) -> tuple[bool, list[str]]:
        """Validate the configuration.

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors: list[str] = []

        if self.r < 1:
            errors.append("Rank (r) must be at least 1")
        if self.r > 256:
            errors.append("Rank (r) > 256 is unusually high, may cause OOM")

        if self.lora_alpha < 1:
            errors.append("Alpha must be at least 1")
        if self.lora_alpha < self.r:
            errors.append(
                f"Alpha ({self.lora_alpha}) < r ({self.r}) may reduce effectiveness"
            )

        if not 0 <= self.lora_dropout < 1:
            errors.append("Dropout must be in [0, 1)")
        if self.lora_dropout > 0.3:
            errors.append("Dropout > 0.3 may hurt training stability")

        if self.target_modules is not None and len(self.target_modules) == 0:
            errors.append("target_modules cannot be empty list")

        if self.use_qlora and self.quantization_type == QuantizationType.NONE:
            errors.append("QLoRA enabled but quantization_type is NONE")

        return len(errors) == 0, errors

    @property
    def scaling_factor(self) -> float:
        """Calculate the LoRA scaling factor (alpha/r)."""
        return self.lora_alpha / self.r

    @property
    def trainable_params_ratio(self) -> float:
        """Estimate ratio of trainable to total parameters.

        This is a rough estimate assuming typical transformer architecture.
        Actual ratio depends on model architecture and target modules.
        """
        # Typical: ~0.1% to 1% of params are trainable with LoRA
        # Higher r = more trainable params
        base_ratio = 0.001  # 0.1% for r=8
        return base_ratio * (self.r / 8)

    def for_architecture(self, architecture: str) -> LoRAConfig:
        """Return a copy configured for a specific architecture.

        Args:
            architecture: Model architecture name (llama, mistral, gpt2, etc.)

        Returns:
            New LoRAConfig with appropriate target_modules
        """
        arch_lower = architecture.lower()
        target_modules = DEFAULT_TARGET_MODULES.get(arch_lower)

        if target_modules is None:
            # Try to find partial match
            for key, modules in DEFAULT_TARGET_MODULES.items():
                if key in arch_lower or arch_lower in key:
                    target_modules = modules
                    break

        if target_modules is None:
            # Default to common attention modules
            target_modules = ["q_proj", "k_proj", "v_proj", "o_proj"]

        return LoRAConfig(
            r=self.r,
            lora_alpha=self.lora_alpha,
            lora_dropout=self.lora_dropout,
            target_modules=target_modules,
            bias=self.bias,
            task_type=self.task_type,
            modules_to_save=self.modules_to_save,
            fan_in_fan_out=self.fan_in_fan_out,
            inference_mode=self.inference_mode,
            use_qlora=self.use_qlora,
            quantization_type=self.quantization_type,
            double_quantization=self.double_quantization,
            compute_dtype=self.compute_dtype,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "r": self.r,
            "lora_alpha": self.lora_alpha,
            "lora_dropout": self.lora_dropout,
            "target_modules": self.target_modules,
            "bias": self.bias,
            "task_type": self.task_type.value,
            "modules_to_save": self.modules_to_save,
            "fan_in_fan_out": self.fan_in_fan_out,
            "inference_mode": self.inference_mode,
            "use_qlora": self.use_qlora,
            "quantization_type": self.quantization_type.value,
            "double_quantization": self.double_quantization,
            "compute_dtype": self.compute_dtype,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LoRAConfig:
        """Create from dictionary."""
        # Handle enum conversions
        if "task_type" in data and isinstance(data["task_type"], str):
            data = dict(data)  # Make copy to avoid modifying original
            data["task_type"] = TaskType(data["task_type"])
        if "quantization_type" in data and isinstance(data["quantization_type"], str):
            data = dict(data)
            data["quantization_type"] = QuantizationType(data["quantization_type"])
        return cls(**data)

    def to_peft_config(self) -> Any:
        """Convert to PEFT LoraConfig object.

        Returns:
            peft.LoraConfig object

        Raises:
            ImportError: If peft is not installed
        """
        try:
            from peft import LoraConfig as PeftLoraConfig
            from peft import TaskType as PeftTaskType
        except ImportError:
            raise ImportError(
                "peft is required for to_peft_config(). "
                "Install with: pip install peft"
            )

        # Map our task type to PEFT's
        task_type_map = {
            TaskType.CAUSAL_LM: PeftTaskType.CAUSAL_LM,
            TaskType.SEQ_2_SEQ_LM: PeftTaskType.SEQ_2_SEQ_LM,
            TaskType.TOKEN_CLS: PeftTaskType.TOKEN_CLS,
            TaskType.SEQ_CLS: PeftTaskType.SEQ_CLS,
            TaskType.QUESTION_ANS: PeftTaskType.QUESTION_ANS,
        }

        return PeftLoraConfig(
            r=self.r,
            lora_alpha=self.lora_alpha,
            lora_dropout=self.lora_dropout,
            target_modules=self.target_modules,
            bias=self.bias,
            task_type=task_type_map.get(self.task_type, PeftTaskType.CAUSAL_LM),
            modules_to_save=self.modules_to_save,
            fan_in_fan_out=self.fan_in_fan_out,
            inference_mode=self.inference_mode,
        )

    def to_bnb_config(self) -> Any:
        """Convert to BitsAndBytes quantization config for QLoRA.

        Returns:
            transformers.BitsAndBytesConfig object

        Raises:
            ImportError: If transformers is not installed
            ValueError: If not configured for QLoRA
        """
        if not self.use_qlora:
            raise ValueError("QLoRA not enabled in this config")

        try:
            import torch
            from transformers import BitsAndBytesConfig
        except ImportError:
            raise ImportError(
                "transformers and torch are required for QLoRA config. "
                "Install with: pip install transformers torch bitsandbytes"
            )

        # Map compute dtype
        dtype_map = {
            "float16": torch.float16,
            "bfloat16": torch.bfloat16,
            "float32": torch.float32,
        }
        compute_dtype = dtype_map.get(self.compute_dtype, torch.float16)

        if self.quantization_type in (
            QuantizationType.INT4,
            QuantizationType.NF4,
            QuantizationType.FP4,
        ):
            return BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type=(
                    self.quantization_type.value
                    if self.quantization_type != QuantizationType.INT4
                    else "nf4"
                ),
                bnb_4bit_use_double_quant=self.double_quantization,
                bnb_4bit_compute_dtype=compute_dtype,
            )
        elif self.quantization_type == QuantizationType.INT8:
            return BitsAndBytesConfig(
                load_in_8bit=True,
            )
        else:
            raise ValueError(f"Unsupported quantization type: {self.quantization_type}")

    def estimate_memory_savings(self, model_params_billions: float) -> dict[str, float]:
        """Estimate memory savings from using this LoRA config.

        Args:
            model_params_billions: Model size in billions of parameters

        Returns:
            Dictionary with memory estimates in GB
        """
        # Full fine-tuning memory (rough estimate: 4 bytes per param for fp32)
        full_memory_gb = model_params_billions * 4

        # LoRA memory is ~r/d of full, where d is hidden dimension
        # Rough approximation: r=8 on typical models uses ~0.1% of params
        lora_ratio = self.trainable_params_ratio
        lora_memory_gb = full_memory_gb * lora_ratio

        # QLoRA further reduces by ~4x for 4-bit
        if self.use_qlora and self.quantization_type in (
            QuantizationType.INT4,
            QuantizationType.NF4,
            QuantizationType.FP4,
        ):
            lora_memory_gb *= 0.25

        return {
            "full_finetuning_gb": full_memory_gb,
            "lora_finetuning_gb": lora_memory_gb,
            "memory_savings_gb": full_memory_gb - lora_memory_gb,
            "savings_percentage": (1 - lora_ratio) * 100,
        }


# Preset configurations


def lora_default() -> LoRAConfig:
    """Default LoRA configuration.

    Good balance of performance and efficiency.
    r=8, alpha=16, dropout=0.05
    """
    return LoRAConfig(
        r=8,
        lora_alpha=16,
        lora_dropout=0.05,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
    )


def lora_aggressive() -> LoRAConfig:
    """Aggressive LoRA configuration for maximum adaptation.

    Higher rank and alpha for better performance at cost of memory.
    r=64, alpha=128, targets more modules.
    """
    return LoRAConfig(
        r=64,
        lora_alpha=128,
        lora_dropout=0.1,
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
        bias="none",
        task_type=TaskType.CAUSAL_LM,
    )


def lora_minimal() -> LoRAConfig:
    """Minimal LoRA configuration for resource-constrained environments.

    Low rank, attention only.
    r=4, alpha=8, attention modules only.
    """
    return LoRAConfig(
        r=4,
        lora_alpha=8,
        lora_dropout=0.0,
        target_modules=["q_proj", "v_proj"],
        bias="none",
        task_type=TaskType.CAUSAL_LM,
    )


def qlora_4bit() -> LoRAConfig:
    """QLoRA configuration with 4-bit quantization.

    Optimal for running on consumer GPUs with limited VRAM.
    Uses NF4 quantization with double quantization.
    """
    return LoRAConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
        bias="none",
        task_type=TaskType.CAUSAL_LM,
        use_qlora=True,
        quantization_type=QuantizationType.NF4,
        double_quantization=True,
        compute_dtype="bfloat16",
    )


def qlora_8bit() -> LoRAConfig:
    """QLoRA configuration with 8-bit quantization.

    Good balance between memory savings and precision.
    """
    return LoRAConfig(
        r=8,
        lora_alpha=16,
        lora_dropout=0.05,
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
        ],
        bias="none",
        task_type=TaskType.CAUSAL_LM,
        use_qlora=True,
        quantization_type=QuantizationType.INT8,
        double_quantization=False,
        compute_dtype="float16",
    )


@dataclass
class LoRAMergeConfig:
    """Configuration for merging LoRA adapters."""

    base_model_path: str
    adapter_paths: list[str] = field(default_factory=list)
    merge_weights: list[float] | None = None
    output_path: str | None = None
    output_dtype: str = "float16"

    def validate(self) -> tuple[bool, list[str]]:
        """Validate merge configuration."""
        errors: list[str] = []

        if not self.base_model_path:
            errors.append("base_model_path is required")

        if not self.adapter_paths:
            errors.append("At least one adapter_path is required")

        if self.merge_weights is not None:
            if len(self.merge_weights) != len(self.adapter_paths):
                errors.append(
                    f"merge_weights length ({len(self.merge_weights)}) must match "
                    f"adapter_paths length ({len(self.adapter_paths)})"
                )
            if any(w < 0 for w in self.merge_weights):
                errors.append("merge_weights must be non-negative")

        return len(errors) == 0, errors

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "base_model_path": self.base_model_path,
            "adapter_paths": self.adapter_paths,
            "merge_weights": self.merge_weights,
            "output_path": self.output_path,
            "output_dtype": self.output_dtype,
        }
