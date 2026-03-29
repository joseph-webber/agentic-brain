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

"""Training utilities for fine-tuning LLMs.

Provides configuration and job management - NO actual training.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from .lora import LoRAConfig


class JobStatus(Enum):
    """Status of a training job."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OptimizerType(Enum):
    """Supported optimizer types."""

    ADAMW = "adamw"
    ADAM = "adam"
    SGD = "sgd"
    ADAFACTOR = "adafactor"
    ADAMW_8BIT = "adamw_8bit"
    PAGED_ADAMW = "paged_adamw"
    PAGED_ADAMW_8BIT = "paged_adamw_8bit"


class SchedulerType(Enum):
    """Supported learning rate scheduler types."""

    LINEAR = "linear"
    COSINE = "cosine"
    COSINE_WITH_RESTARTS = "cosine_with_restarts"
    POLYNOMIAL = "polynomial"
    CONSTANT = "constant"
    CONSTANT_WITH_WARMUP = "constant_with_warmup"


@dataclass
class TrainingConfig:
    """Configuration for fine-tuning training.

    This is configuration only - no actual training is performed.
    """

    # Basic training params
    epochs: int = 3
    batch_size: int = 4
    gradient_accumulation_steps: int = 4
    learning_rate: float = 2e-4
    weight_decay: float = 0.01
    max_grad_norm: float = 1.0

    # Learning rate schedule
    warmup_ratio: float = 0.03
    warmup_steps: int | None = None
    lr_scheduler_type: SchedulerType = SchedulerType.COSINE

    # Optimizer
    optimizer: OptimizerType = OptimizerType.PAGED_ADAMW_8BIT
    adam_beta1: float = 0.9
    adam_beta2: float = 0.999
    adam_epsilon: float = 1e-8

    # Data
    max_seq_length: int = 2048
    dataset_text_field: str = "text"
    packing: bool = False

    # Checkpointing
    save_strategy: str = "steps"
    save_steps: int = 100
    save_total_limit: int = 3
    checkpoint_dir: str | None = None

    # Logging
    logging_steps: int = 10
    logging_dir: str | None = None
    report_to: list[str] = field(default_factory=lambda: ["tensorboard"])

    # Evaluation
    eval_strategy: str = "steps"
    eval_steps: int = 100

    # Hardware
    fp16: bool = False
    bf16: bool = True
    gradient_checkpointing: bool = True
    dataloader_num_workers: int = 4

    # Misc
    seed: int = 42
    push_to_hub: bool = False
    hub_model_id: str | None = None

    def validate(self) -> tuple[bool, list[str]]:
        """Validate the configuration.

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors: list[str] = []

        if self.epochs < 1:
            errors.append("epochs must be at least 1")
        if self.batch_size < 1:
            errors.append("batch_size must be at least 1")
        if self.gradient_accumulation_steps < 1:
            errors.append("gradient_accumulation_steps must be at least 1")
        if self.learning_rate <= 0:
            errors.append("learning_rate must be positive")
        if self.learning_rate > 0.1:
            errors.append("learning_rate > 0.1 is unusually high")
        if self.weight_decay < 0:
            errors.append("weight_decay must be non-negative")
        if self.max_grad_norm <= 0:
            errors.append("max_grad_norm must be positive")
        if self.warmup_ratio < 0 or self.warmup_ratio > 1:
            errors.append("warmup_ratio must be in [0, 1]")
        if self.max_seq_length < 32:
            errors.append("max_seq_length must be at least 32")
        if self.fp16 and self.bf16:
            errors.append("Cannot enable both fp16 and bf16")

        return len(errors) == 0, errors

    @property
    def effective_batch_size(self) -> int:
        """Calculate effective batch size including gradient accumulation."""
        return self.batch_size * self.gradient_accumulation_steps

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "epochs": self.epochs,
            "batch_size": self.batch_size,
            "gradient_accumulation_steps": self.gradient_accumulation_steps,
            "learning_rate": self.learning_rate,
            "weight_decay": self.weight_decay,
            "max_grad_norm": self.max_grad_norm,
            "warmup_ratio": self.warmup_ratio,
            "warmup_steps": self.warmup_steps,
            "lr_scheduler_type": self.lr_scheduler_type.value,
            "optimizer": self.optimizer.value,
            "adam_beta1": self.adam_beta1,
            "adam_beta2": self.adam_beta2,
            "adam_epsilon": self.adam_epsilon,
            "max_seq_length": self.max_seq_length,
            "dataset_text_field": self.dataset_text_field,
            "packing": self.packing,
            "save_strategy": self.save_strategy,
            "save_steps": self.save_steps,
            "save_total_limit": self.save_total_limit,
            "checkpoint_dir": self.checkpoint_dir,
            "logging_steps": self.logging_steps,
            "logging_dir": self.logging_dir,
            "report_to": self.report_to,
            "eval_strategy": self.eval_strategy,
            "eval_steps": self.eval_steps,
            "fp16": self.fp16,
            "bf16": self.bf16,
            "gradient_checkpointing": self.gradient_checkpointing,
            "dataloader_num_workers": self.dataloader_num_workers,
            "seed": self.seed,
            "push_to_hub": self.push_to_hub,
            "hub_model_id": self.hub_model_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TrainingConfig:
        """Create from dictionary."""
        data = dict(data)  # Make copy
        if "lr_scheduler_type" in data and isinstance(data["lr_scheduler_type"], str):
            data["lr_scheduler_type"] = SchedulerType(data["lr_scheduler_type"])
        if "optimizer" in data and isinstance(data["optimizer"], str):
            data["optimizer"] = OptimizerType(data["optimizer"])
        return cls(**data)

    def to_hf_training_args(self) -> Any:
        """Convert to Hugging Face TrainingArguments.

        Returns:
            transformers.TrainingArguments object

        Raises:
            ImportError: If transformers not installed
        """
        try:
            from transformers import TrainingArguments
        except ImportError:
            raise ImportError(
                "transformers is required for to_hf_training_args(). "
                "Install with: pip install transformers"
            )

        output_dir = self.checkpoint_dir or "./output"

        return TrainingArguments(
            output_dir=output_dir,
            num_train_epochs=self.epochs,
            per_device_train_batch_size=self.batch_size,
            gradient_accumulation_steps=self.gradient_accumulation_steps,
            learning_rate=self.learning_rate,
            weight_decay=self.weight_decay,
            max_grad_norm=self.max_grad_norm,
            warmup_ratio=self.warmup_ratio,
            warmup_steps=self.warmup_steps or 0,
            lr_scheduler_type=self.lr_scheduler_type.value,
            save_strategy=self.save_strategy,
            save_steps=self.save_steps,
            save_total_limit=self.save_total_limit,
            logging_steps=self.logging_steps,
            logging_dir=self.logging_dir,
            report_to=self.report_to,
            evaluation_strategy=self.eval_strategy,
            eval_steps=self.eval_steps,
            fp16=self.fp16,
            bf16=self.bf16,
            gradient_checkpointing=self.gradient_checkpointing,
            dataloader_num_workers=self.dataloader_num_workers,
            seed=self.seed,
            push_to_hub=self.push_to_hub,
            hub_model_id=self.hub_model_id,
        )


@dataclass
class Checkpoint:
    """A training checkpoint."""

    step: int
    epoch: float
    loss: float
    learning_rate: float
    path: str
    timestamp: datetime = field(default_factory=datetime.now)
    metrics: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "step": self.step,
            "epoch": self.epoch,
            "loss": self.loss,
            "learning_rate": self.learning_rate,
            "path": self.path,
            "timestamp": self.timestamp.isoformat(),
            "metrics": self.metrics,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Checkpoint:
        """Create from dictionary."""
        data = dict(data)
        if "timestamp" in data and isinstance(data["timestamp"], str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)


@dataclass
class TrainingMetrics:
    """Metrics from a training run."""

    train_loss: float = 0.0
    eval_loss: float | None = None
    train_runtime: float = 0.0
    train_samples_per_second: float = 0.0
    train_steps_per_second: float = 0.0
    total_steps: int = 0
    completed_steps: int = 0
    current_epoch: float = 0.0
    best_metric: float | None = None
    best_step: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "train_loss": self.train_loss,
            "eval_loss": self.eval_loss,
            "train_runtime": self.train_runtime,
            "train_samples_per_second": self.train_samples_per_second,
            "train_steps_per_second": self.train_steps_per_second,
            "total_steps": self.total_steps,
            "completed_steps": self.completed_steps,
            "current_epoch": self.current_epoch,
            "best_metric": self.best_metric,
            "best_step": self.best_step,
        }

    @property
    def progress_percentage(self) -> float:
        """Calculate training progress as percentage."""
        if self.total_steps == 0:
            return 0.0
        return (self.completed_steps / self.total_steps) * 100


@dataclass
class TrainingJob:
    """A training job with progress tracking.

    This manages job metadata and progress - NO actual training.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = "training_job"
    status: JobStatus = JobStatus.PENDING
    model_name: str = ""
    dataset_name: str = ""
    training_config: TrainingConfig = field(default_factory=TrainingConfig)
    lora_config: LoRAConfig | None = None
    metrics: TrainingMetrics = field(default_factory=TrainingMetrics)
    checkpoints: list[Checkpoint] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def start(self) -> None:
        """Mark job as started."""
        self.status = JobStatus.RUNNING
        self.started_at = datetime.now()

    def complete(self) -> None:
        """Mark job as completed."""
        self.status = JobStatus.COMPLETED
        self.completed_at = datetime.now()

    def fail(self, error: str) -> None:
        """Mark job as failed."""
        self.status = JobStatus.FAILED
        self.error_message = error
        self.completed_at = datetime.now()

    def cancel(self) -> None:
        """Mark job as cancelled."""
        self.status = JobStatus.CANCELLED
        self.completed_at = datetime.now()

    def pause(self) -> None:
        """Mark job as paused."""
        self.status = JobStatus.PAUSED

    def resume(self) -> None:
        """Resume a paused job."""
        if self.status == JobStatus.PAUSED:
            self.status = JobStatus.RUNNING

    def add_checkpoint(self, checkpoint: Checkpoint) -> None:
        """Add a checkpoint to the job."""
        self.checkpoints.append(checkpoint)

        # Update best metric if applicable
        if (
            self.metrics.best_metric is None
            or checkpoint.loss < self.metrics.best_metric
        ):
            self.metrics.best_metric = checkpoint.loss
            self.metrics.best_step = checkpoint.step

    def update_progress(
        self,
        step: int,
        loss: float,
        epoch: float,
        learning_rate: float,
    ) -> None:
        """Update training progress."""
        self.metrics.completed_steps = step
        self.metrics.train_loss = loss
        self.metrics.current_epoch = epoch

    @property
    def duration_seconds(self) -> float:
        """Calculate job duration in seconds."""
        if self.started_at is None:
            return 0.0
        end = self.completed_at or datetime.now()
        return (end - self.started_at).total_seconds()

    @property
    def is_running(self) -> bool:
        """Check if job is currently running."""
        return self.status == JobStatus.RUNNING

    @property
    def is_complete(self) -> bool:
        """Check if job has finished (success or failure)."""
        return self.status in (
            JobStatus.COMPLETED,
            JobStatus.FAILED,
            JobStatus.CANCELLED,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "model_name": self.model_name,
            "dataset_name": self.dataset_name,
            "training_config": self.training_config.to_dict(),
            "lora_config": self.lora_config.to_dict() if self.lora_config else None,
            "metrics": self.metrics.to_dict(),
            "checkpoints": [c.to_dict() for c in self.checkpoints],
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
            "error_message": self.error_message,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TrainingJob:
        """Create from dictionary."""
        data = dict(data)

        # Convert nested objects
        if "training_config" in data:
            data["training_config"] = TrainingConfig.from_dict(data["training_config"])
        if "lora_config" in data and data["lora_config"] is not None:
            data["lora_config"] = LoRAConfig.from_dict(data["lora_config"])
        if "metrics" in data:
            data["metrics"] = TrainingMetrics(**data["metrics"])
        if "checkpoints" in data:
            data["checkpoints"] = [Checkpoint.from_dict(c) for c in data["checkpoints"]]
        if "status" in data:
            data["status"] = JobStatus(data["status"])
        if "created_at" in data and isinstance(data["created_at"], str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if "started_at" in data and data["started_at"]:
            data["started_at"] = datetime.fromisoformat(data["started_at"])
        if "completed_at" in data and data["completed_at"]:
            data["completed_at"] = datetime.fromisoformat(data["completed_at"])

        return cls(**data)

    def save(self, path: str | Path) -> None:
        """Save job state to file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: str | Path) -> TrainingJob:
        """Load job state from file."""
        with Path(path).open("r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)


def estimate_memory(
    model_params_billions: float,
    batch_size: int = 4,
    seq_length: int = 2048,
    gradient_checkpointing: bool = True,
    fp16: bool = False,
    bf16: bool = True,
    lora_config: LoRAConfig | None = None,
) -> dict[str, Any]:
    """Estimate GPU memory requirements for training.

    Args:
        model_params_billions: Model size in billions of parameters
        batch_size: Per-device batch size
        seq_length: Maximum sequence length
        gradient_checkpointing: Whether using gradient checkpointing
        fp16: Using FP16 training
        bf16: Using BF16 training
        lora_config: LoRA configuration if using LoRA

    Returns:
        Dictionary with memory estimates
    """
    # Base memory for model weights
    bytes_per_param = 2 if (fp16 or bf16) else 4
    model_memory_gb = (model_params_billions * 1e9 * bytes_per_param) / (1024**3)

    # Optimizer states (AdamW uses 2 states per param)
    if lora_config:
        # Only LoRA params need optimizer states
        trainable_ratio = lora_config.trainable_params_ratio
        optimizer_memory_gb = model_memory_gb * trainable_ratio * 2
    else:
        optimizer_memory_gb = model_memory_gb * 2

    # Gradients
    if lora_config:
        gradients_memory_gb = model_memory_gb * lora_config.trainable_params_ratio
    else:
        gradients_memory_gb = model_memory_gb

    # Activations (rough estimate)
    # Activations scale with batch_size * seq_length
    base_activation = 0.5  # GB per billion params for bs=1, seq=512
    activation_scale = (batch_size / 1) * (seq_length / 512)
    activations_memory_gb = model_params_billions * base_activation * activation_scale

    # Gradient checkpointing reduces activation memory by ~5x
    if gradient_checkpointing:
        activations_memory_gb /= 5

    # QLoRA reduces model memory
    if lora_config and lora_config.use_qlora:
        if lora_config.quantization_type.value in ("int4", "nf4", "fp4"):
            model_memory_gb /= 4
        elif lora_config.quantization_type.value == "int8":
            model_memory_gb /= 2

    total_memory_gb = (
        model_memory_gb
        + optimizer_memory_gb
        + gradients_memory_gb
        + activations_memory_gb
    )

    # Add 10% overhead for CUDA kernels, etc.
    total_with_overhead = total_memory_gb * 1.1

    return {
        "model_memory_gb": round(model_memory_gb, 2),
        "optimizer_memory_gb": round(optimizer_memory_gb, 2),
        "gradients_memory_gb": round(gradients_memory_gb, 2),
        "activations_memory_gb": round(activations_memory_gb, 2),
        "total_memory_gb": round(total_memory_gb, 2),
        "total_with_overhead_gb": round(total_with_overhead, 2),
        "recommended_gpu": _recommend_gpu(total_with_overhead),
    }


def _recommend_gpu(memory_gb: float) -> str:
    """Recommend a GPU based on memory requirements."""
    if memory_gb <= 8:
        return "RTX 3060 (12GB) or better"
    elif memory_gb <= 12:
        return "RTX 3080 (12GB) / RTX 4070 (12GB) or better"
    elif memory_gb <= 16:
        return "RTX 4080 (16GB) / A4000 (16GB) or better"
    elif memory_gb <= 24:
        return "RTX 3090 (24GB) / RTX 4090 (24GB) / A5000 (24GB) or better"
    elif memory_gb <= 40:
        return "A100 (40GB) or better"
    elif memory_gb <= 48:
        return "RTX 6000 Ada (48GB) / A6000 (48GB) or better"
    elif memory_gb <= 80:
        return "A100 (80GB) / H100 (80GB)"
    else:
        return f"Multi-GPU setup required ({memory_gb:.0f}GB total)"


def estimate_time(
    num_samples: int,
    epochs: int = 3,
    batch_size: int = 4,
    gradient_accumulation_steps: int = 4,
    samples_per_second: float = 5.0,
) -> dict[str, Any]:
    """Estimate training time.

    Args:
        num_samples: Number of training samples
        epochs: Number of training epochs
        batch_size: Per-device batch size
        gradient_accumulation_steps: Gradient accumulation steps
        samples_per_second: Estimated throughput (varies by hardware)

    Returns:
        Dictionary with time estimates
    """
    effective_batch_size = batch_size * gradient_accumulation_steps
    steps_per_epoch = num_samples // effective_batch_size
    total_steps = steps_per_epoch * epochs

    seconds_per_step = effective_batch_size / samples_per_second
    total_seconds = total_steps * seconds_per_step

    hours = total_seconds / 3600
    minutes = (total_seconds % 3600) / 60

    return {
        "total_steps": total_steps,
        "steps_per_epoch": steps_per_epoch,
        "estimated_seconds": round(total_seconds, 1),
        "estimated_minutes": round(total_seconds / 60, 1),
        "estimated_hours": round(hours, 2),
        "formatted": f"{int(hours)}h {int(minutes)}m",
    }


def validate_hardware(
    required_memory_gb: float,
    required_compute_capability: float = 7.0,
) -> dict[str, Any]:
    """Validate that hardware meets requirements.

    Args:
        required_memory_gb: Required GPU memory in GB
        required_compute_capability: Minimum CUDA compute capability

    Returns:
        Dictionary with validation results
    """
    result: dict[str, Any] = {
        "cuda_available": False,
        "mps_available": False,
        "gpu_count": 0,
        "gpus": [],
        "meets_requirements": False,
        "warnings": [],
    }

    # Check for CUDA
    try:
        import torch

        if torch.cuda.is_available():
            result["cuda_available"] = True
            result["gpu_count"] = torch.cuda.device_count()

            for i in range(result["gpu_count"]):
                props = torch.cuda.get_device_properties(i)
                gpu_info = {
                    "name": props.name,
                    "memory_gb": round(props.total_memory / (1024**3), 2),
                    "compute_capability": f"{props.major}.{props.minor}",
                    "meets_memory": props.total_memory / (1024**3)
                    >= required_memory_gb,
                    "meets_compute": props.major + props.minor / 10
                    >= required_compute_capability,
                }
                result["gpus"].append(gpu_info)

            # Check if any GPU meets requirements
            result["meets_requirements"] = any(
                g["meets_memory"] and g["meets_compute"] for g in result["gpus"]
            )

        # Check for MPS (Apple Silicon)
        if torch.backends.mps.is_available():
            result["mps_available"] = True
            result["gpus"].append(
                {
                    "name": "Apple Silicon (MPS)",
                    "memory_gb": "shared",
                    "compute_capability": "N/A",
                    "meets_memory": True,  # MPS uses unified memory
                    "meets_compute": True,
                }
            )
            result["meets_requirements"] = True
            result["warnings"].append(
                "MPS detected - some features may have limited support"
            )

    except ImportError:
        result["warnings"].append("PyTorch not installed - cannot detect GPU hardware")

    if not result["cuda_available"] and not result["mps_available"]:
        result["warnings"].append("No GPU detected - training will be very slow")

    return result


# Preset configurations


def training_default() -> TrainingConfig:
    """Default training configuration for most use cases."""
    return TrainingConfig(
        epochs=3,
        batch_size=4,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        warmup_ratio=0.03,
        bf16=True,
        gradient_checkpointing=True,
    )


def training_fast() -> TrainingConfig:
    """Fast training configuration for quick experiments."""
    return TrainingConfig(
        epochs=1,
        batch_size=8,
        gradient_accumulation_steps=2,
        learning_rate=3e-4,
        warmup_ratio=0.01,
        bf16=True,
        gradient_checkpointing=False,
        save_steps=500,
        logging_steps=50,
    )


def training_thorough() -> TrainingConfig:
    """Thorough training configuration for best results."""
    return TrainingConfig(
        epochs=5,
        batch_size=2,
        gradient_accumulation_steps=8,
        learning_rate=1e-4,
        warmup_ratio=0.05,
        weight_decay=0.05,
        bf16=True,
        gradient_checkpointing=True,
        save_steps=50,
        eval_steps=50,
        logging_steps=5,
    )
