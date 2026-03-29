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

"""Fine-tuning utilities for LLM adaptation.

This module provides tools for preparing datasets, configuring LoRA/QLoRA,
and managing training jobs. It does NOT perform actual training - that
requires external libraries (peft, transformers, etc.) which are optional.

Example:
    >>> from agentic_brain.finetuning import DatasetBuilder, lora_default, TrainingJob
    >>>
    >>> # Build a dataset
    >>> builder = DatasetBuilder()
    >>> builder.from_qa_pairs([
    ...     {"question": "What is AI?", "answer": "Artificial Intelligence..."}
    ... ])
    >>> builder.to_jsonl("dataset.jsonl")
    >>>
    >>> # Configure LoRA
    >>> lora_config = lora_default().for_architecture("llama")
    >>>
    >>> # Create a training job
    >>> job = TrainingJob(
    ...     name="my-finetune",
    ...     model_name="meta-llama/Llama-2-7b",
    ...     lora_config=lora_config,
    ... )
"""

from .dataset import (
    Conversation,
    ConversationTurn,
    DatasetBuilder,
    DatasetFormat,
    Document,
    QAPair,
    ValidationResult,
)
from .lora import (
    DEFAULT_TARGET_MODULES,
    LoRAConfig,
    LoRAMergeConfig,
    QuantizationType,
    TaskType,
    lora_aggressive,
    lora_default,
    lora_minimal,
    qlora_4bit,
    qlora_8bit,
)
from .trainer import (
    Checkpoint,
    JobStatus,
    OptimizerType,
    SchedulerType,
    TrainingConfig,
    TrainingJob,
    TrainingMetrics,
    estimate_memory,
    estimate_time,
    training_default,
    training_fast,
    training_thorough,
    validate_hardware,
)

__all__ = [
    # Dataset
    "DatasetBuilder",
    "DatasetFormat",
    "Conversation",
    "ConversationTurn",
    "QAPair",
    "Document",
    "ValidationResult",
    # LoRA
    "LoRAConfig",
    "LoRAMergeConfig",
    "QuantizationType",
    "TaskType",
    "DEFAULT_TARGET_MODULES",
    "lora_default",
    "lora_aggressive",
    "lora_minimal",
    "qlora_4bit",
    "qlora_8bit",
    # Trainer
    "TrainingConfig",
    "TrainingJob",
    "TrainingMetrics",
    "Checkpoint",
    "JobStatus",
    "OptimizerType",
    "SchedulerType",
    "estimate_memory",
    "estimate_time",
    "validate_hardware",
    "training_default",
    "training_fast",
    "training_thorough",
]
