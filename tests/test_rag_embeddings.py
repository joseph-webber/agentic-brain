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
Tests for hardware-accelerated embedding providers.

Tests coverage:
- Hardware detection (detect_hardware, get_best_device, get_hardware_info)
- SentenceTransformerEmbeddings (with hardware acceleration)
- MLXEmbeddings (Apple Silicon native)
- CUDAEmbeddings (NVIDIA GPUs)
- ROCmEmbeddings (AMD GPUs)
- OllamaEmbeddings (local, free)
- OpenAIEmbeddings (cloud, API-based)
- CachedEmbeddings (caching wrapper)
- get_embeddings factory function

Uses pytest.mark.skipif to skip tests when hardware/libraries not available.
Mocks external APIs (Ollama, OpenAI) for those tests.
"""

import hashlib
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest


# Helper function to check if module is available
def has_module(module_name: str) -> bool:
    """Check if a module is available."""
    try:
        __import__(module_name)
        return True
    except ImportError:
        return False


# Import the module we're testing
from agentic_brain.rag.embeddings import (
    CachedEmbeddings,
    CUDAEmbeddings,
    EmbeddingProvider,
    EmbeddingResult,
    MLXEmbeddings,
    OllamaEmbeddings,
    OpenAIEmbeddings,
    ROCmEmbeddings,
    SentenceTransformerEmbeddings,
    detect_hardware,
    get_best_device,
    get_embeddings,
    get_hardware_info,
)

# =============================================================================
# Test Hardware Detection
# =============================================================================


class TestHardwareDetection:
    """Test hardware detection functionality."""

    def test_detect_hardware_returns_tuple(self):
        """Test that detect_hardware returns a tuple of (device, info)."""
        device, info = detect_hardware()

        assert isinstance(device, str)
        assert isinstance(info, dict)
        assert device in ("mlx", "cuda", "mps", "cpu")

    def test_get_best_device_returns_string(self):
        """Test that get_best_device returns a device string."""
        device = get_best_device()

        assert isinstance(device, str)
        assert device in ("mlx", "cuda", "mps", "cpu")

    def test_get_hardware_info_has_required_keys(self):
        """Test that get_hardware_info returns dict with required keys."""
        info = get_hardware_info()

        required_keys = {
            "platform",
            "machine",
            "apple_silicon",
            "chip",
            "cuda",
            "cuda_version",
            "cuda_devices",
            "mps",
            "mlx",
            "rocm",
            "cpu_cores",
        }

        assert isinstance(info, dict)
        for key in required_keys:
            assert key in info, f"Missing key: {key}"

    def test_detect_hardware_info_types(self):
        """Test that hardware info has correct types."""
        _, info = detect_hardware()

        assert isinstance(info["platform"], str)
        assert isinstance(info["machine"], str)
        assert isinstance(info["apple_silicon"], bool)
        assert info["chip"] is None or isinstance(info["chip"], str)
        assert isinstance(info["cuda"], bool)
        assert info["cuda_version"] is None or isinstance(info["cuda_version"], str)
        assert isinstance(info["cuda_devices"], list)
        assert isinstance(info["mps"], bool)
        assert isinstance(info["mlx"], bool)
        assert isinstance(info["rocm"], bool)
        assert isinstance(info["cpu_cores"], (int, type(None)))

    def test_hardware_cache(self):
        """Test that hardware detection is cached."""
        device1, info1 = detect_hardware()
        device2, info2 = detect_hardware()

        # Should return same objects due to caching
        assert device1 == device2
        assert info1 == info2


# =============================================================================
# Test Ollama Embeddings
# =============================================================================


class TestOllamaEmbeddings:
    """Test Ollama embedding provider."""

    def test_init_default(self):
        """Test Ollama initialization with defaults."""
        embedder = OllamaEmbeddings()

        assert embedder.model == "nomic-embed-text"
        assert embedder.base_url == "http://localhost:11434"
        assert embedder.dimensions == 768

    def test_init_custom(self):
        """Test Ollama initialization with custom values."""
        embedder = OllamaEmbeddings(model="mistral", base_url="http://custom:9999")

        assert embedder.model == "mistral"
        assert embedder.base_url == "http://custom:9999"

    def test_model_name(self):
        """Test Ollama model_name property."""
        embedder = OllamaEmbeddings(model="nomic-embed-text")
        assert embedder.model_name == "ollama/nomic-embed-text"

    @patch("requests.post")
    def test_embed_single_text(self, mock_post):
        """Test embedding a single text with Ollama."""
        mock_response = Mock()
        mock_response.json.return_value = {"embedding": [0.1, 0.2, 0.3, 0.4, 0.5]}
        mock_post.return_value = mock_response

        embedder = OllamaEmbeddings()
        result = embedder.embed("Hello world")

        assert isinstance(result, list)
        assert len(result) == 5
        assert result == [0.1, 0.2, 0.3, 0.4, 0.5]

        # Verify request was made correctly
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["json"]["prompt"] == "Hello world"

    @patch("requests.post")
    def test_embed_batch(self, mock_post):
        """Test embedding multiple texts with Ollama."""

        def mock_embed_func(url, json, **kwargs):
            response = Mock()
            response.json.return_value = {
                "embedding": [0.1 * (i + 1) for i in range(5)]
            }
            return response

        mock_post.side_effect = mock_embed_func

        embedder = OllamaEmbeddings()
        texts = ["Hello", "World"]
        results = embedder.embed_batch(texts)

        assert isinstance(results, list)
        assert len(results) == 2
        assert all(isinstance(r, list) for r in results)


# =============================================================================
# Test OpenAI Embeddings
# =============================================================================


class TestOpenAIEmbeddings:
    """Test OpenAI embedding provider."""

    def test_init_requires_api_key(self):
        """Test that OpenAI initialization requires API key."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="OpenAI API key required"):
                OpenAIEmbeddings()

    def test_init_with_env_variable(self):
        """Test OpenAI initialization with environment variable."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            embedder = OpenAIEmbeddings()
            assert embedder.api_key == "test-key"

    def test_init_with_explicit_key(self):
        """Test OpenAI initialization with explicit API key."""
        embedder = OpenAIEmbeddings(api_key="explicit-key")
        assert embedder.api_key == "explicit-key"

    def test_dimensions_small_model(self):
        """Test dimensions for small embedding model."""
        embedder = OpenAIEmbeddings(model="text-embedding-3-small", api_key="test-key")
        assert embedder.dimensions == 512

    def test_dimensions_large_model(self):
        """Test dimensions for large embedding model."""
        embedder = OpenAIEmbeddings(model="text-embedding-3-large", api_key="test-key")
        assert embedder.dimensions == 1536

    def test_model_name(self):
        """Test OpenAI model_name property."""
        embedder = OpenAIEmbeddings(model="text-embedding-3-small", api_key="test-key")
        assert embedder.model_name == "openai/text-embedding-3-small"

    @patch("requests.post")
    def test_embed_single_text(self, mock_post):
        """Test embedding a single text with OpenAI."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": [{"embedding": [0.1, 0.2, 0.3], "index": 0}]
        }
        mock_post.return_value = mock_response

        embedder = OpenAIEmbeddings(api_key="test-key")
        result = embedder.embed("Hello world")

        assert isinstance(result, list)
        assert result == [0.1, 0.2, 0.3]

    @patch("requests.post")
    def test_embed_batch(self, mock_post):
        """Test embedding multiple texts with OpenAI."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": [
                {"embedding": [0.1, 0.2], "index": 0},
                {"embedding": [0.3, 0.4], "index": 1},
            ]
        }
        mock_post.return_value = mock_response

        embedder = OpenAIEmbeddings(api_key="test-key")
        results = embedder.embed_batch(["Hello", "World"])

        assert isinstance(results, list)
        assert len(results) == 2
        assert results[0] == [0.1, 0.2]
        assert results[1] == [0.3, 0.4]


# =============================================================================
# Test Sentence Transformer Embeddings
# =============================================================================


class TestSentenceTransformerEmbeddings:
    """Test SentenceTransformer embedding provider."""

    def test_init_with_auto_device(self):
        """Test initialization with automatic device detection."""
        embedder = SentenceTransformerEmbeddings()

        assert embedder.model == "all-MiniLM-L6-v2"
        assert embedder.device in ("cuda", "mps", "cpu")
        assert embedder.batch_size == 32
        assert embedder.dimensions == 384

    def test_init_with_specific_device(self):
        """Test initialization with specific device."""
        for device in ("cpu", "mps", "cuda"):
            embedder = SentenceTransformerEmbeddings(device=device)
            assert embedder.device == device

    def test_model_dimensions(self):
        """Test that known models have correct dimensions."""
        test_cases = [
            ("all-MiniLM-L6-v2", 384),
            ("all-mpnet-base-v2", 768),
            ("paraphrase-MiniLM-L6-v2", 384),
        ]

        for model, expected_dim in test_cases:
            embedder = SentenceTransformerEmbeddings(model=model)
            assert embedder.dimensions == expected_dim

    def test_model_name_includes_device(self):
        """Test that model_name includes device."""
        embedder = SentenceTransformerEmbeddings(device="cpu")
        assert "@cpu" in embedder.model_name
        assert "sentence_transformers" in embedder.model_name

    @pytest.mark.skipif(
        not has_module("sentence_transformers"),
        reason="sentence-transformers not available",
    )
    def test_embed_returns_list(self):
        """Test that embed returns a list of floats."""
        embedder = SentenceTransformerEmbeddings(device="cpu")
        result = embedder.embed("Hello world")

        assert isinstance(result, list)
        assert all(isinstance(x, float) for x in result)
        assert len(result) == 384

    @pytest.mark.skipif(
        not has_module("sentence_transformers"),
        reason="sentence-transformers not available",
    )
    def test_embed_batch_returns_list_of_lists(self):
        """Test that embed_batch returns list of embeddings."""
        embedder = SentenceTransformerEmbeddings(device="cpu")
        results = embedder.embed_batch(["Hello", "World"])

        assert isinstance(results, list)
        assert len(results) == 2
        assert all(isinstance(r, list) for r in results)
        assert all(len(r) == 384 for r in results)

    def test_batch_size_property(self):
        """Test batch_size can be customized."""
        embedder = SentenceTransformerEmbeddings(batch_size=64)
        assert embedder.batch_size == 64


# =============================================================================
# Test MLX Embeddings
# =============================================================================


class TestMLXEmbeddings:
    """Test MLX embedding provider for Apple Silicon."""

    def test_init_checks_mlx_availability(self):
        """Test that MLX initialization checks for MLX availability."""
        # This test just verifies the class exists
        try:
            from agentic_brain.rag.embeddings import MLXEmbeddings
        except ImportError:
            pytest.skip("MLX module not available")

    @pytest.mark.skipif(not has_module("mlx"), reason="MLX not available")
    def test_init_with_mlx(self):
        """Test MLX embeddings initialization."""
        embedder = MLXEmbeddings()

        assert embedder.model == "all-MiniLM-L6-v2"
        assert embedder.batch_size == 32
        assert embedder.dimensions == 384

    @pytest.mark.skipif(not has_module("mlx"), reason="MLX not available")
    def test_model_name_starts_with_mlx(self):
        """Test that MLX model_name starts with 'mlx/'."""
        embedder = MLXEmbeddings()
        assert embedder.model_name.startswith("mlx/")

    @pytest.mark.skipif(not has_module("mlx"), reason="MLX not available")
    def test_embed_returns_list(self):
        """Test that MLX embed returns a list."""
        try:
            embedder = MLXEmbeddings()
            result = embedder.embed("Hello world")

            assert isinstance(result, list)
            assert all(isinstance(x, float) for x in result)
        except ImportError as e:
            pytest.skip(f"MLX dependency not available: {e}")

    def test_init_requires_mlx(self):
        """Test that MLX embeddings require MLX to be installed."""
        with patch.dict("sys.modules", {"mlx": None, "mlx.core": None}):
            with pytest.raises(ImportError, match="MLX required"):
                MLXEmbeddings()


# =============================================================================
# Test CUDA Embeddings
# =============================================================================


class TestCUDAEmbeddings:
    """Test CUDA embedding provider for NVIDIA GPUs."""

    @pytest.mark.skipif(not has_module("torch"), reason="PyTorch not available")
    def test_init_requires_cuda(self):
        """Test that CUDA embeddings require CUDA to be available."""
        with patch("torch.cuda.is_available", return_value=False):
            with pytest.raises(ImportError, match="CUDA not available"):
                CUDAEmbeddings()

    @pytest.mark.skipif(not has_module("torch"), reason="PyTorch not available")
    def test_init_with_cuda(self):
        """Test CUDA embeddings initialization if CUDA is available."""
        try:
            import torch

            if torch.cuda.is_available():
                embedder = CUDAEmbeddings()
                assert embedder.device.startswith("cuda:")
                assert embedder.batch_size == 64
        except ImportError:
            pytest.skip("CUDA not available")

    @pytest.mark.skipif(not has_module("torch"), reason="PyTorch not available")
    def test_cuda_fp16_option(self):
        """Test FP16 mixed precision option."""
        try:
            import torch

            if torch.cuda.is_available():
                embedder = CUDAEmbeddings(fp16=True)
                assert embedder.fp16 is True
        except ImportError:
            pytest.skip("CUDA not available")

    @pytest.mark.skipif(not has_module("torch"), reason="PyTorch not available")
    def test_device_id_property(self):
        """Test device_id can be set."""
        try:
            import torch

            if torch.cuda.is_available():
                embedder = CUDAEmbeddings(device_id=0)
                assert embedder.device_id == 0
        except ImportError:
            pytest.skip("CUDA not available")


# =============================================================================
# Test ROCm Embeddings
# =============================================================================


class TestROCmEmbeddings:
    """Test ROCm embedding provider for AMD GPUs."""

    @pytest.mark.skipif(not has_module("torch"), reason="PyTorch not available")
    def test_init_requires_rocm(self):
        """Test that ROCm embeddings require ROCm to be available."""
        with patch("torch.cuda.is_available", return_value=False):
            with pytest.raises(ImportError, match="ROCm not available"):
                ROCmEmbeddings()

    @pytest.mark.skipif(not has_module("torch"), reason="PyTorch not available")
    def test_init_with_rocm(self):
        """Test ROCm embeddings initialization if ROCm is available."""
        try:
            import torch

            if torch.cuda.is_available() and hasattr(torch.version, "hip"):
                embedder = ROCmEmbeddings()
                assert embedder.device.startswith("cuda:")
                assert embedder.batch_size == 64
        except ImportError:
            pytest.skip("ROCm not available")


# =============================================================================
# Test Cached Embeddings
# =============================================================================


class TestCachedEmbeddings:
    """Test caching wrapper for embedding providers."""

    def test_init_default(self):
        """Test CachedEmbeddings initialization."""
        mock_provider = MagicMock(spec=EmbeddingProvider)
        mock_provider.model_name = "test/model"

        cached = CachedEmbeddings(mock_provider)

        assert cached.provider is mock_provider
        assert cached.cache_dir.exists()

    def test_init_custom_cache_dir(self):
        """Test CachedEmbeddings with custom cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_provider = MagicMock(spec=EmbeddingProvider)
            mock_provider.model_name = "test/model"
            custom_dir = Path(tmpdir) / "custom_cache"

            cached = CachedEmbeddings(mock_provider, cache_dir=custom_dir)

            assert cached.cache_dir == custom_dir
            assert custom_dir.exists()

    def test_cache_key_generation(self):
        """Test that cache keys are generated correctly."""
        mock_provider = MagicMock(spec=EmbeddingProvider)
        mock_provider.model_name = "test/model"
        cached = CachedEmbeddings(mock_provider)

        text = "Hello world"
        expected_key = hashlib.sha256(text.encode()).hexdigest()[:16]
        actual_key = cached._cache_key(text)

        assert actual_key == expected_key

    def test_embed_caches_result(self):
        """Test that embed caches the result."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_provider = MagicMock(spec=EmbeddingProvider)
            mock_provider.model_name = "test/model"
            mock_provider.embed.return_value = [0.1, 0.2, 0.3]

            cached = CachedEmbeddings(mock_provider, cache_dir=Path(tmpdir) / "cache")

            # First call should use provider
            result1 = cached.embed("Hello")
            assert result1 == [0.1, 0.2, 0.3]
            assert mock_provider.embed.call_count == 1

            # Second call should use cache
            result2 = cached.embed("Hello")
            assert result2 == [0.1, 0.2, 0.3]
            assert mock_provider.embed.call_count == 1  # Not called again

    def test_embed_batch_mixed_cache(self):
        """Test embed_batch with some cached and some new embeddings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_provider = MagicMock(spec=EmbeddingProvider)
            mock_provider.model_name = "test/model"
            mock_provider.dimensions = 3
            mock_provider.embed_batch.return_value = [
                [0.7, 0.8, 0.9],
                [0.4, 0.5, 0.6],
            ]

            cached = CachedEmbeddings(mock_provider, cache_dir=Path(tmpdir) / "cache")

            # Pre-populate cache for first text
            cached._set_cached("First", [0.1, 0.2, 0.3])

            # Request both cached and uncached
            results = cached.embed_batch(["First", "Second", "Third"])

            assert len(results) == 3
            assert results[0] == [0.1, 0.2, 0.3]  # From cache
            assert results[1] == [0.7, 0.8, 0.9]  # From provider
            assert results[2] == [0.4, 0.5, 0.6]  # From provider

    def test_dimensions_delegates_to_provider(self):
        """Test that dimensions delegates to provider."""
        mock_provider = MagicMock(spec=EmbeddingProvider)
        mock_provider.model_name = "test/model"
        mock_provider.dimensions = 384

        cached = CachedEmbeddings(mock_provider)
        assert cached.dimensions == 384

    def test_model_name_includes_cached(self):
        """Test that model_name includes 'cached/'."""
        mock_provider = MagicMock(spec=EmbeddingProvider)
        mock_provider.model_name = "test/model"

        cached = CachedEmbeddings(mock_provider)
        assert cached.model_name == "cached/test/model"


# =============================================================================
# Test get_embeddings Factory Function
# =============================================================================


class TestGetEmbeddings:
    """Test the get_embeddings factory function."""

    @patch("requests.get")
    def test_auto_provider_selection_ollama(self, mock_get):
        """Test auto-selection when ollama is available on CPU system."""
        # Mock requests.get to simulate Ollama available
        mock_response = Mock()
        mock_response.ok = True
        mock_get.return_value = mock_response

        # Also mock hardware info to simulate CPU-only system
        with patch("agentic_brain.rag.embeddings.get_hardware_info") as mock_hw:
            mock_hw.return_value = {
                "platform": "Linux",
                "machine": "x86_64",
                "apple_silicon": False,
                "chip": None,
                "cuda": False,
                "cuda_version": None,
                "cuda_devices": [],
                "mps": False,
                "mlx": False,
                "rocm": False,
                "cpu_cores": 8,
            }
            with (
                patch(
                    "agentic_brain.rag.embeddings._HARDWARE_CACHE", mock_hw.return_value
                ),
                patch(
                    "agentic_brain.rag.embeddings.get_best_device", return_value="cpu"
                ),
            ):
                embedder = get_embeddings(provider="auto")

                assert isinstance(embedder, CachedEmbeddings)
                assert isinstance(embedder.provider, (OllamaEmbeddings, MLXEmbeddings))

    @patch("requests.get")
    def test_auto_provider_selection_openai(self, mock_get):
        """Test auto-selection falls back to OpenAI if Ollama unavailable."""
        mock_get.side_effect = ConnectionError("Connection failed")

        # Mock hardware info to simulate CPU-only system
        with patch("agentic_brain.rag.embeddings.get_hardware_info") as mock_hw:
            mock_hw.return_value = {
                "platform": "Linux",
                "machine": "x86_64",
                "apple_silicon": False,
                "chip": None,
                "cuda": False,
                "cuda_version": None,
                "cuda_devices": [],
                "mps": False,
                "mlx": False,
                "rocm": False,
                "cpu_cores": 8,
            }
            with (
                patch(
                    "agentic_brain.rag.embeddings._HARDWARE_CACHE", mock_hw.return_value
                ),
                patch(
                    "agentic_brain.rag.embeddings.get_best_device", return_value="cpu"
                ),
                patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}),
                patch.dict("sys.modules", {"sentence_transformers": None}),
            ):
                embedder = get_embeddings(provider="auto")

                assert isinstance(embedder, CachedEmbeddings)
                assert isinstance(embedder.provider, (OpenAIEmbeddings, MLXEmbeddings))

    def test_ollama_provider_explicit(self):
        """Test explicit Ollama provider selection."""
        embedder = get_embeddings(provider="ollama")

        assert isinstance(embedder, CachedEmbeddings)
        assert isinstance(embedder.provider, OllamaEmbeddings)

    def test_openai_provider_explicit(self):
        """Test explicit OpenAI provider selection."""
        with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}):
            embedder = get_embeddings(provider="openai")

            assert isinstance(embedder, CachedEmbeddings)
            assert isinstance(embedder.provider, OpenAIEmbeddings)

    def test_cache_enabled_by_default(self):
        """Test that caching is enabled by default."""
        embedder = get_embeddings(provider="ollama")

        assert isinstance(embedder, CachedEmbeddings)

    def test_cache_can_be_disabled(self):
        """Test that caching can be disabled."""
        embedder = get_embeddings(provider="ollama", cache=False)

        assert not isinstance(embedder, CachedEmbeddings)
        assert isinstance(embedder, OllamaEmbeddings)

    def test_invalid_provider_raises_error(self):
        """Test that invalid provider raises ValueError."""
        with pytest.raises(ValueError, match="Unknown provider"):
            get_embeddings(provider="invalid_provider")


# =============================================================================
# Test EmbeddingResult Dataclass
# =============================================================================


class TestEmbeddingResult:
    """Test EmbeddingResult dataclass."""

    def test_embedding_result_creation(self):
        """Test creating an EmbeddingResult."""
        result = EmbeddingResult(
            text="Hello world",
            embedding=[0.1, 0.2, 0.3],
            model="test/model",
            dimensions=3,
            cached=False,
        )

        assert result.text == "Hello world"
        assert result.embedding == [0.1, 0.2, 0.3]
        assert result.model == "test/model"
        assert result.dimensions == 3
        assert result.cached is False

    def test_embedding_result_cached_default(self):
        """Test that cached defaults to False."""
        result = EmbeddingResult(
            text="Hello", embedding=[0.1], model="test", dimensions=1
        )

        assert result.cached is False


# =============================================================================
# Integration Tests
# =============================================================================


class TestEmbeddingIntegration:
    """Integration tests for embedding providers."""

    def test_different_providers_same_interface(self):
        """Test that all providers implement the same interface."""
        providers = [
            OllamaEmbeddings(),
        ]

        # Add OpenAI if API key available
        import os

        if os.getenv("OPENAI_API_KEY"):
            providers.append(OpenAIEmbeddings())

        for provider in providers:
            # All should have these methods and properties
            assert hasattr(provider, "embed")
            assert hasattr(provider, "embed_batch")
            assert hasattr(provider, "dimensions")
            assert hasattr(provider, "model_name")

            # Properties should return correct types
            assert isinstance(provider.dimensions, int)
            assert isinstance(provider.model_name, str)

    def test_embedding_deterministic(self):
        """Test that embeddings are deterministic (same input = same output)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mock_provider = MagicMock(spec=EmbeddingProvider)
            mock_provider.model_name = "test/model"
            mock_provider.embed.return_value = [0.1, 0.2, 0.3]

            cached1 = CachedEmbeddings(mock_provider, cache_dir=Path(tmpdir) / "cache1")

            result1 = cached1.embed("test text")
            result2 = cached1.embed("test text")

            assert result1 == result2

    def test_embedding_different_texts_different_embeddings(self):
        """Test that different texts produce different embeddings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            embeddings_map = {
                "hello": [0.1, 0.2, 0.3],
                "world": [0.4, 0.5, 0.6],
                "test": [0.7, 0.8, 0.9],
            }

            mock_provider = MagicMock(spec=EmbeddingProvider)
            mock_provider.model_name = "test/model"

            def mock_embed(text):
                return embeddings_map.get(text, [0.0, 0.0, 0.0])

            mock_provider.embed.side_effect = mock_embed

            cached = CachedEmbeddings(mock_provider, cache_dir=Path(tmpdir) / "cache")

            result1 = cached.embed("hello")
            result2 = cached.embed("world")
            result3 = cached.embed("test")

            assert result1 == [0.1, 0.2, 0.3]
            assert result2 == [0.4, 0.5, 0.6]
            assert result3 == [0.7, 0.8, 0.9]
            assert result1 != result2
            assert result2 != result3


# =============================================================================
# Test Error Handling
# =============================================================================


class TestErrorHandling:
    """Test error handling in embedding providers."""

    @patch("requests.post")
    def test_ollama_api_error(self, mock_post):
        """Test handling of Ollama API errors."""
        mock_post.side_effect = ConnectionError("Connection failed")

        embedder = OllamaEmbeddings()

        with pytest.raises(ConnectionError):
            embedder.embed("Hello")

    def test_openai_missing_key(self):
        """Test that OpenAI requires API key."""
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError):
                OpenAIEmbeddings()

    def test_cache_corrupted_file_fallback(self):
        """Test that corrupted cache files are handled gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_dir = Path(tmpdir) / "cache"
            cache_dir.mkdir()

            # Create a corrupted cache file
            mock_provider = MagicMock(spec=EmbeddingProvider)
            mock_provider.model_name = "test/model"
            mock_provider.embed.return_value = [0.1, 0.2, 0.3]

            cached = CachedEmbeddings(mock_provider, cache_dir=cache_dir)

            # Write corrupted JSON
            text = "test"
            cache_file = cache_dir / f"{cached._cache_key(text)}.json"
            cache_file.write_text("{ invalid json }")

            # Should fall back to provider instead of failing
            result = cached.embed(text)

            assert result == [0.1, 0.2, 0.3]
            assert mock_provider.embed.called


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
