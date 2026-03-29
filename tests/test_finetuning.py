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

"""Tests for fine-tuning utilities."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from agentic_brain.finetuning import (
    Checkpoint,
    Conversation,
    ConversationTurn,
    DatasetBuilder,
    DatasetFormat,
    Document,
    JobStatus,
    LoRAConfig,
    LoRAMergeConfig,
    QAPair,
    QuantizationType,
    SchedulerType,
    TaskType,
    TrainingConfig,
    TrainingJob,
    TrainingMetrics,
    estimate_memory,
    estimate_time,
    lora_aggressive,
    lora_default,
    lora_minimal,
    qlora_4bit,
    qlora_8bit,
    training_default,
    training_fast,
    training_thorough,
)

# =============================================================================
# Dataset Tests
# =============================================================================


class TestConversationTurn:
    """Tests for ConversationTurn."""

    def test_create_turn(self):
        """Test creating a conversation turn."""
        turn = ConversationTurn(role="user", content="Hello")
        assert turn.role == "user"
        assert turn.content == "Hello"
        assert turn.metadata == {}

    def test_turn_with_metadata(self):
        """Test turn with metadata."""
        turn = ConversationTurn(
            role="assistant",
            content="Hi there!",
            metadata={"confidence": 0.95},
        )
        assert turn.metadata["confidence"] == 0.95

    def test_to_dict(self):
        """Test converting turn to dict."""
        turn = ConversationTurn(role="system", content="Be helpful")
        d = turn.to_dict()
        assert d["role"] == "system"
        assert d["content"] == "Be helpful"

    def test_from_dict(self):
        """Test creating turn from dict."""
        data = {"role": "user", "content": "Question?"}
        turn = ConversationTurn.from_dict(data)
        assert turn.role == "user"
        assert turn.content == "Question?"


class TestConversation:
    """Tests for Conversation."""

    def test_create_conversation(self):
        """Test creating a conversation."""
        turns = [
            ConversationTurn(role="user", content="Hi"),
            ConversationTurn(role="assistant", content="Hello!"),
        ]
        conv = Conversation(turns=turns)
        assert len(conv.turns) == 2
        assert conv.id is not None
        assert conv.id.startswith("conv_")

    def test_conversation_with_id(self):
        """Test conversation with custom ID."""
        conv = Conversation(
            turns=[ConversationTurn(role="user", content="Test")],
            id="custom_id",
        )
        assert conv.id == "custom_id"

    def test_to_alpaca(self):
        """Test converting to Alpaca format."""
        conv = Conversation(
            turns=[
                ConversationTurn(role="system", content="Be helpful"),
                ConversationTurn(role="user", content="What is 2+2?"),
                ConversationTurn(role="assistant", content="4"),
            ]
        )
        alpaca = conv.to_alpaca()
        assert alpaca["instruction"] == "Be helpful"
        assert alpaca["input"] == "What is 2+2?"
        assert alpaca["output"] == "4"

    def test_to_sharegpt(self):
        """Test converting to ShareGPT format."""
        conv = Conversation(
            turns=[
                ConversationTurn(role="user", content="Hello"),
                ConversationTurn(role="assistant", content="Hi!"),
            ]
        )
        sharegpt = conv.to_sharegpt()
        assert "conversations" in sharegpt
        assert sharegpt["conversations"][0]["from"] == "human"
        assert sharegpt["conversations"][1]["from"] == "gpt"

    def test_to_openai(self):
        """Test converting to OpenAI format."""
        conv = Conversation(
            turns=[
                ConversationTurn(role="system", content="Assistant"),
                ConversationTurn(role="user", content="Hi"),
            ]
        )
        openai = conv.to_openai()
        assert "messages" in openai
        assert len(openai["messages"]) == 2

    def test_token_estimate(self):
        """Test token count estimation."""
        conv = Conversation(
            turns=[
                ConversationTurn(role="user", content="Hello world"),  # 11 chars
            ]
        )
        # Rough estimate: 4 chars per token
        assert conv.total_tokens_estimate() == 2


class TestQAPair:
    """Tests for QAPair."""

    def test_create_qa_pair(self):
        """Test creating Q&A pair."""
        qa = QAPair(question="What is AI?", answer="Artificial Intelligence")
        assert qa.question == "What is AI?"
        assert qa.answer == "Artificial Intelligence"
        assert qa.id.startswith("qa_")

    def test_qa_with_context(self):
        """Test Q&A pair with context."""
        qa = QAPair(
            question="What is ML?",
            answer="Machine Learning",
            context="Computer Science context",
        )
        assert qa.context == "Computer Science context"

    def test_to_conversation(self):
        """Test converting Q&A to conversation."""
        qa = QAPair(
            question="Question?",
            answer="Answer!",
            context="Context here",
        )
        conv = qa.to_conversation()
        assert len(conv.turns) == 3
        assert conv.turns[0].role == "system"
        assert conv.turns[1].role == "user"
        assert conv.turns[2].role == "assistant"


class TestDocument:
    """Tests for Document."""

    def test_create_document(self):
        """Test creating a document."""
        doc = Document(content="This is content", title="Doc Title")
        assert doc.content == "This is content"
        assert doc.title == "Doc Title"
        assert doc.id.startswith("doc_")

    def test_to_qa_pairs_default(self):
        """Test converting document to default Q&A pairs."""
        doc = Document(content="AI is cool", title="AI Guide")
        qa_pairs = doc.to_qa_pairs()
        assert len(qa_pairs) == 2  # Default generates 2 questions

    def test_to_qa_pairs_custom(self):
        """Test converting document with custom questions."""
        doc = Document(content="Python is great")
        questions = ["What is Python?", "Why use Python?"]
        qa_pairs = doc.to_qa_pairs(questions)
        assert len(qa_pairs) == 2
        assert qa_pairs[0].question == "What is Python?"


class TestDatasetBuilder:
    """Tests for DatasetBuilder."""

    def test_empty_builder(self):
        """Test empty builder."""
        builder = DatasetBuilder()
        assert builder.size == 0

    def test_from_conversations(self):
        """Test adding conversations."""
        builder = DatasetBuilder()
        builder.from_conversations(
            [
                {
                    "messages": [
                        {"role": "user", "content": "Hi"},
                        {"role": "assistant", "content": "Hello"},
                    ]
                }
            ]
        )
        assert builder.size == 1

    def test_from_qa_pairs(self):
        """Test adding Q&A pairs."""
        builder = DatasetBuilder()
        builder.from_qa_pairs(
            [
                {"question": "Q1", "answer": "A1"},
                {"question": "Q2", "answer": "A2"},
            ]
        )
        assert builder.size == 2

    def test_from_documents(self):
        """Test adding documents."""
        builder = DatasetBuilder()
        builder.from_documents([{"content": "Doc content", "title": "Doc 1"}])
        assert builder.size == 2  # Default generates 2 Q&A pairs per doc

    def test_dedupe(self):
        """Test deduplication."""
        builder = DatasetBuilder()
        # Add same Q&A twice - but note they get unique IDs first time
        builder.from_qa_pairs([{"question": "Q1", "answer": "A1"}])
        # The _add_conversation prevents duplicates during initial add
        # so we need to reset and manually add duplicates
        builder._seen_hashes.clear()
        builder.from_qa_pairs([{"question": "Q1", "answer": "A1"}])
        removed = builder.dedupe()
        assert removed == 1
        assert builder.size == 1

    def test_filter_by_quality_min_turns(self):
        """Test filtering by minimum turns."""
        builder = DatasetBuilder()
        builder.from_qa_pairs([{"question": "Q", "answer": "A"}])  # 2 turns
        removed = builder.filter_by_quality(min_turns=3)
        assert removed == 1
        assert builder.size == 0

    def test_filter_by_quality_require_assistant(self):
        """Test filtering by requiring assistant."""
        builder = DatasetBuilder()
        # Manually create conversation without assistant
        conv = Conversation(
            turns=[
                ConversationTurn(role="user", content="Hi"),
                ConversationTurn(role="user", content="Hello?"),
            ]
        )
        builder._conversations.append(conv)
        removed = builder.filter_by_quality(require_assistant=True)
        assert removed == 1

    def test_filter_by_content_exclude(self):
        """Test filtering by excluding patterns."""
        builder = DatasetBuilder()
        builder.from_qa_pairs(
            [
                {"question": "Secret code: 123", "answer": "OK"},
                {"question": "Normal question", "answer": "Normal answer"},
            ]
        )
        removed = builder.filter_by_content(exclude_patterns=[r"Secret"])
        assert removed == 1
        assert builder.size == 1

    def test_validate_empty(self):
        """Test validating empty dataset."""
        builder = DatasetBuilder()
        result = builder.validate()
        assert not result.is_valid
        assert "empty" in result.errors[0].lower()

    def test_validate_valid(self):
        """Test validating valid dataset."""
        builder = DatasetBuilder()
        builder.from_qa_pairs([{"question": "Q", "answer": "A"}])
        result = builder.validate()
        assert result.is_valid
        assert result.stats["total_conversations"] == 1

    def test_split(self):
        """Test splitting dataset."""
        builder = DatasetBuilder()
        for i in range(10):
            builder.from_qa_pairs([{"question": f"Q{i}", "answer": f"A{i}"}])
        train, val, test = builder.split(
            train_ratio=0.8, val_ratio=0.1, test_ratio=0.1, shuffle=False
        )
        assert train.size == 8
        assert val.size == 1
        assert test.size == 1

    def test_split_invalid_ratios(self):
        """Test split with invalid ratios."""
        builder = DatasetBuilder()
        with pytest.raises(ValueError, match="sum to 1.0"):
            builder.split(train_ratio=0.5, val_ratio=0.5, test_ratio=0.5)

    def test_iterate_formats(self):
        """Test iterating in different formats."""
        builder = DatasetBuilder()
        builder.from_qa_pairs([{"question": "Q", "answer": "A"}])

        # OpenAI format
        records = list(builder.iterate(DatasetFormat.OPENAI_JSONL))
        assert "messages" in records[0]

        # Alpaca format
        records = list(builder.iterate(DatasetFormat.ALPACA))
        assert "instruction" in records[0]

        # ShareGPT format
        records = list(builder.iterate(DatasetFormat.SHAREGPT))
        assert "conversations" in records[0]

    def test_to_jsonl(self):
        """Test exporting to JSONL."""
        builder = DatasetBuilder()
        builder.from_qa_pairs([{"question": "Q", "answer": "A"}])

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "dataset.jsonl"
            count = builder.to_jsonl(path)
            assert count == 1
            assert path.exists()

            # Verify content
            with path.open() as f:
                data = json.loads(f.readline())
                assert "messages" in data

    def test_to_list(self):
        """Test exporting to list."""
        builder = DatasetBuilder()
        builder.from_qa_pairs([{"question": "Q", "answer": "A"}])
        records = builder.to_list()
        assert len(records) == 1
        assert isinstance(records[0], dict)


# =============================================================================
# LoRA Tests
# =============================================================================


class TestLoRAConfig:
    """Tests for LoRAConfig."""

    def test_default_config(self):
        """Test default LoRA config."""
        config = LoRAConfig()
        assert config.r == 8
        assert config.lora_alpha == 16
        assert config.lora_dropout == 0.05

    def test_invalid_rank(self):
        """Test invalid rank raises error."""
        with pytest.raises(ValueError, match="Rank"):
            LoRAConfig(r=0)

    def test_invalid_alpha(self):
        """Test invalid alpha raises error."""
        with pytest.raises(ValueError, match="Alpha"):
            LoRAConfig(lora_alpha=0)

    def test_invalid_dropout(self):
        """Test invalid dropout raises error."""
        with pytest.raises(ValueError, match="Dropout"):
            LoRAConfig(lora_dropout=1.5)

    def test_invalid_bias(self):
        """Test invalid bias raises error."""
        with pytest.raises(ValueError, match="Bias"):
            LoRAConfig(bias="invalid")

    def test_scaling_factor(self):
        """Test scaling factor calculation."""
        config = LoRAConfig(r=8, lora_alpha=16)
        assert config.scaling_factor == 2.0

    def test_validate_alpha_less_than_r(self):
        """Test validation when alpha < r (still valid but noted)."""
        config = LoRAConfig(r=8, lora_alpha=4)  # alpha < r
        is_valid, errors = config.validate()
        # alpha < r is noted in errors list but doesn't make config invalid
        assert any("Alpha" in e and "effectiveness" in e for e in errors)

    def test_validate_high_rank(self):
        """Test validation rejects very high rank."""
        config = LoRAConfig(r=300, lora_alpha=300)
        is_valid, errors = config.validate()
        assert not is_valid
        assert any("256" in e for e in errors)

    def test_for_architecture_llama(self):
        """Test getting config for Llama architecture."""
        config = lora_default().for_architecture("llama")
        assert "q_proj" in config.target_modules
        assert "k_proj" in config.target_modules

    def test_for_architecture_gpt2(self):
        """Test getting config for GPT-2 architecture."""
        config = lora_default().for_architecture("gpt2")
        assert "c_attn" in config.target_modules

    def test_for_architecture_unknown(self):
        """Test getting config for unknown architecture."""
        config = lora_default().for_architecture("unknown_model")
        # Should fall back to common attention modules
        assert config.target_modules is not None

    def test_to_dict(self):
        """Test converting to dict."""
        config = LoRAConfig(r=16, lora_alpha=32)
        d = config.to_dict()
        assert d["r"] == 16
        assert d["lora_alpha"] == 32
        assert d["task_type"] == "CAUSAL_LM"

    def test_from_dict(self):
        """Test creating from dict."""
        data = {"r": 16, "lora_alpha": 32, "task_type": "CAUSAL_LM"}
        config = LoRAConfig.from_dict(data)
        assert config.r == 16
        assert config.task_type == TaskType.CAUSAL_LM

    def test_estimate_memory_savings(self):
        """Test memory savings estimation."""
        config = lora_default()
        savings = config.estimate_memory_savings(7.0)  # 7B model
        assert savings["full_finetuning_gb"] == 28.0
        assert savings["lora_finetuning_gb"] < savings["full_finetuning_gb"]
        assert savings["savings_percentage"] > 99.0

    def test_qlora_validation(self):
        """Test QLoRA validation."""
        config = LoRAConfig(use_qlora=True, quantization_type=QuantizationType.NONE)
        is_valid, errors = config.validate()
        assert not is_valid
        assert any("QLoRA" in e for e in errors)


class TestLoRAPresets:
    """Tests for LoRA preset configurations."""

    def test_lora_default(self):
        """Test default preset."""
        config = lora_default()
        assert config.r == 8
        assert config.lora_alpha == 16

    def test_lora_aggressive(self):
        """Test aggressive preset."""
        config = lora_aggressive()
        assert config.r == 64
        assert config.lora_alpha == 128
        assert config.target_modules is not None

    def test_lora_minimal(self):
        """Test minimal preset."""
        config = lora_minimal()
        assert config.r == 4
        assert config.lora_dropout == 0.0
        assert len(config.target_modules) == 2

    def test_qlora_4bit(self):
        """Test QLoRA 4-bit preset."""
        config = qlora_4bit()
        assert config.use_qlora is True
        assert config.quantization_type == QuantizationType.NF4
        assert config.double_quantization is True

    def test_qlora_8bit(self):
        """Test QLoRA 8-bit preset."""
        config = qlora_8bit()
        assert config.use_qlora is True
        assert config.quantization_type == QuantizationType.INT8


class TestLoRAMergeConfig:
    """Tests for LoRAMergeConfig."""

    def test_create_merge_config(self):
        """Test creating merge config."""
        config = LoRAMergeConfig(
            base_model_path="base/model",
            adapter_paths=["adapter1", "adapter2"],
        )
        assert len(config.adapter_paths) == 2

    def test_validate_missing_base(self):
        """Test validation with missing base model."""
        config = LoRAMergeConfig(base_model_path="", adapter_paths=["adapter"])
        is_valid, errors = config.validate()
        assert not is_valid
        assert any("base_model_path" in e for e in errors)

    def test_validate_weight_mismatch(self):
        """Test validation with weight count mismatch."""
        config = LoRAMergeConfig(
            base_model_path="base",
            adapter_paths=["a1", "a2"],
            merge_weights=[1.0],  # Only 1 weight for 2 adapters
        )
        is_valid, errors = config.validate()
        assert not is_valid


# =============================================================================
# Trainer Tests
# =============================================================================


class TestTrainingConfig:
    """Tests for TrainingConfig."""

    def test_default_config(self):
        """Test default training config."""
        config = TrainingConfig()
        assert config.epochs == 3
        assert config.batch_size == 4
        assert config.bf16 is True

    def test_effective_batch_size(self):
        """Test effective batch size calculation."""
        config = TrainingConfig(batch_size=4, gradient_accumulation_steps=4)
        assert config.effective_batch_size == 16

    def test_validate_invalid_epochs(self):
        """Test validation rejects invalid epochs."""
        config = TrainingConfig(epochs=0)
        is_valid, errors = config.validate()
        assert not is_valid
        assert any("epochs" in e for e in errors)

    def test_validate_invalid_lr(self):
        """Test validation rejects invalid learning rate."""
        config = TrainingConfig(learning_rate=-0.1)
        is_valid, errors = config.validate()
        assert not is_valid

    def test_validate_fp16_bf16_conflict(self):
        """Test validation rejects both fp16 and bf16."""
        config = TrainingConfig(fp16=True, bf16=True)
        is_valid, errors = config.validate()
        assert not is_valid
        assert any("fp16" in e.lower() and "bf16" in e.lower() for e in errors)

    def test_to_dict(self):
        """Test converting to dict."""
        config = TrainingConfig(epochs=5)
        d = config.to_dict()
        assert d["epochs"] == 5
        assert d["lr_scheduler_type"] == "cosine"

    def test_from_dict(self):
        """Test creating from dict."""
        data = {"epochs": 10, "lr_scheduler_type": "linear"}
        config = TrainingConfig.from_dict(data)
        assert config.epochs == 10
        assert config.lr_scheduler_type == SchedulerType.LINEAR


class TestTrainingPresets:
    """Tests for training presets."""

    def test_training_default(self):
        """Test default training preset."""
        config = training_default()
        assert config.epochs == 3
        assert config.gradient_checkpointing is True

    def test_training_fast(self):
        """Test fast training preset."""
        config = training_fast()
        assert config.epochs == 1
        assert config.gradient_checkpointing is False

    def test_training_thorough(self):
        """Test thorough training preset."""
        config = training_thorough()
        assert config.epochs == 5
        assert config.save_steps == 50


class TestCheckpoint:
    """Tests for Checkpoint."""

    def test_create_checkpoint(self):
        """Test creating a checkpoint."""
        ckpt = Checkpoint(
            step=100,
            epoch=1.5,
            loss=0.5,
            learning_rate=1e-4,
            path="/path/to/ckpt",
        )
        assert ckpt.step == 100
        assert ckpt.loss == 0.5

    def test_to_dict(self):
        """Test converting to dict."""
        ckpt = Checkpoint(
            step=50,
            epoch=0.5,
            loss=1.0,
            learning_rate=2e-4,
            path="/ckpt",
        )
        d = ckpt.to_dict()
        assert d["step"] == 50
        assert "timestamp" in d


class TestTrainingMetrics:
    """Tests for TrainingMetrics."""

    def test_default_metrics(self):
        """Test default metrics."""
        metrics = TrainingMetrics()
        assert metrics.train_loss == 0.0
        assert metrics.completed_steps == 0

    def test_progress_percentage(self):
        """Test progress percentage calculation."""
        metrics = TrainingMetrics(total_steps=100, completed_steps=25)
        assert metrics.progress_percentage == 25.0

    def test_progress_zero_steps(self):
        """Test progress with zero total steps."""
        metrics = TrainingMetrics(total_steps=0)
        assert metrics.progress_percentage == 0.0


class TestTrainingJob:
    """Tests for TrainingJob."""

    def test_create_job(self):
        """Test creating a job."""
        job = TrainingJob(name="test_job")
        assert job.name == "test_job"
        assert job.status == JobStatus.PENDING
        assert job.id is not None

    def test_job_lifecycle(self):
        """Test job state transitions."""
        job = TrainingJob()

        # Start
        job.start()
        assert job.status == JobStatus.RUNNING
        assert job.started_at is not None
        assert job.is_running is True

        # Pause/resume
        job.pause()
        assert job.status == JobStatus.PAUSED
        job.resume()
        assert job.status == JobStatus.RUNNING

        # Complete
        job.complete()
        assert job.status == JobStatus.COMPLETED
        assert job.completed_at is not None
        assert job.is_complete is True

    def test_job_failure(self):
        """Test job failure."""
        job = TrainingJob()
        job.start()
        job.fail("Out of memory")
        assert job.status == JobStatus.FAILED
        assert job.error_message == "Out of memory"

    def test_job_cancel(self):
        """Test job cancellation."""
        job = TrainingJob()
        job.start()
        job.cancel()
        assert job.status == JobStatus.CANCELLED

    def test_add_checkpoint(self):
        """Test adding checkpoints."""
        job = TrainingJob()
        ckpt = Checkpoint(
            step=100,
            epoch=1.0,
            loss=0.5,
            learning_rate=1e-4,
            path="/ckpt",
        )
        job.add_checkpoint(ckpt)
        assert len(job.checkpoints) == 1
        assert job.metrics.best_metric == 0.5
        assert job.metrics.best_step == 100

    def test_update_progress(self):
        """Test updating progress."""
        job = TrainingJob()
        job.update_progress(step=50, loss=0.8, epoch=0.5, learning_rate=1e-4)
        assert job.metrics.completed_steps == 50
        assert job.metrics.train_loss == 0.8

    def test_to_dict_from_dict(self):
        """Test serialization roundtrip."""
        job = TrainingJob(
            name="test",
            model_name="llama-7b",
            lora_config=lora_default(),
        )
        job.start()
        job.update_progress(step=10, loss=1.0, epoch=0.1, learning_rate=1e-4)

        d = job.to_dict()
        restored = TrainingJob.from_dict(d)

        assert restored.name == "test"
        assert restored.model_name == "llama-7b"
        assert restored.lora_config is not None
        assert restored.metrics.completed_steps == 10

    def test_save_load(self):
        """Test saving and loading job."""
        job = TrainingJob(name="persist_test")
        job.start()

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "job.json"
            job.save(path)
            loaded = TrainingJob.load(path)
            assert loaded.name == "persist_test"
            assert loaded.status == JobStatus.RUNNING


class TestEstimateMemory:
    """Tests for memory estimation."""

    def test_estimate_7b_model(self):
        """Test memory estimate for 7B model."""
        result = estimate_memory(7.0)
        assert "model_memory_gb" in result
        assert "total_with_overhead_gb" in result
        assert "recommended_gpu" in result

    def test_estimate_with_lora(self):
        """Test memory estimate with LoRA."""
        lora = lora_default()
        result_full = estimate_memory(7.0)
        result_lora = estimate_memory(7.0, lora_config=lora)
        assert result_lora["optimizer_memory_gb"] < result_full["optimizer_memory_gb"]

    def test_estimate_with_qlora(self):
        """Test memory estimate with QLoRA."""
        qlora = qlora_4bit()
        result = estimate_memory(7.0, lora_config=qlora)
        # QLoRA should reduce model memory
        assert result["model_memory_gb"] < 7.0


class TestEstimateTime:
    """Tests for time estimation."""

    def test_estimate_basic(self):
        """Test basic time estimate."""
        result = estimate_time(num_samples=1000)
        assert "total_steps" in result
        assert "estimated_hours" in result
        assert "formatted" in result

    def test_estimate_params_affect_result(self):
        """Test that parameters affect estimate."""
        result_1epoch = estimate_time(num_samples=1000, epochs=1)
        result_3epoch = estimate_time(num_samples=1000, epochs=3)
        assert result_3epoch["total_steps"] == 3 * result_1epoch["total_steps"]
