# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

from __future__ import annotations

import builtins
import math

import numpy as np
import pytest

from agentic_brain.acceleration import mlx_backend


@pytest.fixture(autouse=True)
def reset_backend_cache():
    mlx_backend.get_best_backend.cache_clear()
    yield
    mlx_backend.get_best_backend.cache_clear()


class FakeMX:
    float32 = np.float32

    def array(self, data, dtype=None):
        return np.array(data, dtype=dtype)

    def sqrt(self, value):
        return np.sqrt(value)

    def sum(self, value, axis=None, keepdims=False):
        return np.sum(value, axis=axis, keepdims=keepdims)

    def matmul(self, left, right):
        return np.matmul(left, right)

    def eval(self, *values):
        return values


class FakeMLXLM:
    def __init__(self):
        self.load_calls: list[str] = []
        self.generate_calls: list[dict[str, object]] = []

    def load(self, model_name):
        self.load_calls.append(model_name)
        return {"model_name": model_name}, {"tokenizer": model_name}

    def generate(self, model, tokenizer, **kwargs):
        self.generate_calls.append({"model": model, "tokenizer": tokenizer, **kwargs})
        return f"mlx:{kwargs['prompt']}"


def make_backend(
    *,
    apple_silicon: bool = True,
    mlx_available: bool = True,
    mlx_lm_available: bool = False,
    model: str = "all-MiniLM-L6-v2",
) -> mlx_backend.MLXBackend:
    fake_mx = FakeMX() if mlx_available else None
    fake_lm = FakeMLXLM() if mlx_lm_available else None

    original_try_import_mlx = mlx_backend._try_import_mlx
    original_try_import_lm = mlx_backend._try_import_mlx_lm
    original_is_apple = mlx_backend._is_apple_silicon

    mlx_backend._try_import_mlx = lambda: fake_mx  # type: ignore[assignment]
    mlx_backend._try_import_mlx_lm = lambda: fake_lm  # type: ignore[assignment]
    mlx_backend._is_apple_silicon = lambda: apple_silicon  # type: ignore[assignment]
    try:
        backend = mlx_backend.MLXBackend(embedding_model=model)
        if fake_lm is not None:
            backend._mlx_lm = fake_lm
        return backend
    finally:
        mlx_backend._try_import_mlx = original_try_import_mlx  # type: ignore[assignment]
        mlx_backend._try_import_mlx_lm = original_try_import_lm  # type: ignore[assignment]
        mlx_backend._is_apple_silicon = original_is_apple  # type: ignore[assignment]


def test_detects_apple_silicon_true(monkeypatch):
    monkeypatch.setattr(mlx_backend.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(mlx_backend.platform, "machine", lambda: "arm64")
    assert mlx_backend._is_apple_silicon() is True


def test_detects_apple_silicon_false_on_intel(monkeypatch):
    monkeypatch.setattr(mlx_backend.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(mlx_backend.platform, "machine", lambda: "x86_64")
    assert mlx_backend._is_apple_silicon() is False


def test_detects_apple_silicon_false_on_linux(monkeypatch):
    monkeypatch.setattr(mlx_backend.platform, "system", lambda: "Linux")
    monkeypatch.setattr(mlx_backend.platform, "machine", lambda: "arm64")
    assert mlx_backend._is_apple_silicon() is False


def test_try_import_mlx_none_when_missing(monkeypatch):
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "mlx" or name.startswith("mlx."):
            raise ImportError("mlx missing")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert mlx_backend._try_import_mlx() is None


def test_get_best_backend_returns_backend_instance(monkeypatch):
    monkeypatch.setattr(mlx_backend, "_try_import_mlx", lambda: FakeMX())
    monkeypatch.setattr(mlx_backend, "_try_import_mlx_lm", lambda: FakeMLXLM())
    monkeypatch.setattr(mlx_backend, "_is_apple_silicon", lambda: True)
    backend = mlx_backend.get_best_backend()
    assert isinstance(backend, mlx_backend.MLXBackend)


def test_get_best_backend_is_cached(monkeypatch):
    monkeypatch.setattr(mlx_backend, "_try_import_mlx", lambda: FakeMX())
    monkeypatch.setattr(mlx_backend, "_try_import_mlx_lm", lambda: None)
    monkeypatch.setattr(mlx_backend, "_is_apple_silicon", lambda: True)
    first = mlx_backend.get_best_backend()
    second = mlx_backend.get_best_backend()
    assert first is second


def test_get_best_backend_cache_clear_uses_new_environment(monkeypatch):
    monkeypatch.setattr(mlx_backend, "_try_import_mlx", lambda: FakeMX())
    monkeypatch.setattr(mlx_backend, "_try_import_mlx_lm", lambda: None)
    monkeypatch.setattr(mlx_backend, "_is_apple_silicon", lambda: True)
    first = mlx_backend.get_best_backend()
    mlx_backend.get_best_backend.cache_clear()
    monkeypatch.setattr(mlx_backend, "_try_import_mlx", lambda: None)
    monkeypatch.setattr(mlx_backend, "_is_apple_silicon", lambda: False)
    second = mlx_backend.get_best_backend()
    assert first.backend_name == "mlx"
    assert second.backend_name == "cpu"


def test_backend_name_mlx_when_available():
    backend = make_backend()
    assert backend.backend_name == "mlx"


def test_backend_name_cpu_when_mlx_missing():
    backend = make_backend(apple_silicon=True, mlx_available=False)
    assert backend.backend_name == "cpu"


def test_available_property_tracks_backend_name():
    assert make_backend().available is True
    assert make_backend(mlx_available=False).available is False


def test_model_name_prefix_is_mlx_for_hardware_backend():
    backend = make_backend()
    assert backend.model_name.startswith("mlx/")


def test_model_name_prefix_is_cpu_for_fallback_backend():
    backend = make_backend(mlx_available=False)
    assert backend.model_name.startswith("cpu/")


def test_dimensions_default_model():
    backend = make_backend()
    assert backend.dimensions == 384


def test_dimensions_nomic_model():
    backend = make_backend(model="nomic-embed-text")
    assert backend.dimensions == 768


def test_dimensions_mpnet_model():
    backend = make_backend(model="all-mpnet-base-v2")
    assert backend.dimensions == 768


def test_embeddings_provider_property_returns_self():
    backend = make_backend()
    assert backend.embeddings_provider is backend


def test_describe_contains_reason():
    backend = make_backend()
    description = backend.describe()
    assert description["backend"] == "mlx"
    assert "reason" in description


def test_info_snapshot_contains_keys():
    backend = make_backend()
    info = backend.info
    for key in ("apple_silicon", "mlx_available", "best_backend", "reason"):
        assert hasattr(info, key)


def test_embed_single_text_cpu_fallback():
    backend = make_backend(mlx_available=False)
    vec = backend.embed("hello world")
    assert len(vec) == backend.dimensions
    assert math.isclose(sum(v * v for v in vec), 1.0, rel_tol=1e-5)


def test_embed_single_text_cpu_is_deterministic():
    backend = make_backend(mlx_available=False)
    assert backend.embed("same text") == backend.embed("same text")


def test_embed_batch_cpu_handles_empty_input():
    backend = make_backend(mlx_available=False)
    assert backend.embed_batch([]) == []


def test_embed_batch_cpu_returns_vectors():
    backend = make_backend(mlx_available=False)
    vectors = backend.embed_batch(["one", "two"])
    assert len(vectors) == 2
    assert all(len(vec) == backend.dimensions for vec in vectors)


def test_embed_single_text_mlx_uses_mx_arrays():
    backend = make_backend()
    vec = backend.embed("hello world")
    assert len(vec) == backend.dimensions
    assert all(isinstance(value, float) for value in vec)


def test_embed_batch_mlx_returns_normalized_vectors():
    backend = make_backend()
    vectors = backend.embed_batch(["alpha beta", "gamma delta"])
    assert len(vectors) == 2
    assert all(len(vec) == backend.dimensions for vec in vectors)


def test_similarity_cpu_matches_identity():
    backend = make_backend(mlx_available=False)
    vec = backend.embed("identity")
    assert math.isclose(backend.similarity(vec, vec), 1.0, rel_tol=1e-5)


def test_similarity_cpu_returns_zero_for_zero_vector():
    backend = make_backend(mlx_available=False)
    assert backend.similarity([0.0, 0.0], [1.0, 0.0]) == 0.0


def test_similarity_mlx_works_with_arrays():
    backend = make_backend()
    vec = backend.embed("mlx similarity")
    assert backend.similarity(vec, vec) > 0.99


def test_similarity_search_cpu_with_text_corpus():
    backend = make_backend(mlx_available=False)
    results = backend.similarity_search("apple silicon", ["apple silicon", "cloud"])
    assert results[0][0] == 0
    assert results[0][1] >= results[1][1]


def test_similarity_search_cpu_with_vector_corpus():
    backend = make_backend(mlx_available=False)
    query = backend.embed("apple silicon")
    corpus = [backend.embed("apple silicon"), backend.embed("cloud")]
    results = backend.similarity_search(query, corpus)
    assert results[0][0] == 0


def test_similarity_search_mlx_sorts_descending():
    backend = make_backend()
    results = backend.similarity_search("same thing", ["same thing", "different thing"])
    assert results[0][0] == 0
    assert results[0][1] >= results[1][1]


def test_similarity_search_respects_top_k():
    backend = make_backend()
    results = backend.similarity_search("query", ["a", "b", "c"], top_k=2)
    assert len(results) == 2


def test_infer_cpu_tokenizes_prompt():
    backend = make_backend(mlx_available=False)
    output = backend.infer("Hello, MLX world!")
    assert output == "hello mlx world"


def test_infer_cpu_handles_empty_prompt():
    backend = make_backend(mlx_available=False)
    assert backend.infer("") == ""


def test_infer_batch_cpu_processes_each_prompt():
    backend = make_backend(mlx_available=False)
    outputs = backend.infer_batch(["one two", "three four"])
    assert outputs == ["one two", "three four"]


def test_infer_mlx_uses_generate(monkeypatch):
    fake_mx = FakeMX()
    fake_lm = FakeMLXLM()
    monkeypatch.setattr(mlx_backend, "_try_import_mlx", lambda: fake_mx)
    monkeypatch.setattr(mlx_backend, "_try_import_mlx_lm", lambda: fake_lm)
    monkeypatch.setattr(mlx_backend, "_is_apple_silicon", lambda: True)
    backend = mlx_backend.MLXBackend()
    output = backend.infer("Generate this", max_tokens=16)
    assert output == "mlx:Generate this"
    assert fake_lm.load_calls
    assert fake_lm.generate_calls


def test_infer_mlx_falls_back_when_generate_fails(monkeypatch):
    class FailingMLXLM(FakeMLXLM):
        def generate(self, model, tokenizer, **kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr(mlx_backend, "_try_import_mlx", lambda: FakeMX())
    monkeypatch.setattr(mlx_backend, "_try_import_mlx_lm", lambda: FailingMLXLM())
    monkeypatch.setattr(mlx_backend, "_is_apple_silicon", lambda: True)
    backend = mlx_backend.MLXBackend()
    monkeypatch.setattr(
        mlx_backend.MLXBackend,
        "_cpu_infer",
        lambda self, prompt, max_tokens=128: "cpu-fallback",
    )
    assert backend.infer("Generate this") == "cpu-fallback"


def test_fallback_to_cpu_disabled_raises_for_embed():
    backend = make_backend(mlx_available=False)
    backend.fallback_to_cpu = False
    with pytest.raises(RuntimeError):
        backend.embed("no cpu fallback")


def test_fallback_to_cpu_disabled_raises_for_batch_embed():
    backend = make_backend(mlx_available=False)
    backend.fallback_to_cpu = False
    with pytest.raises(RuntimeError):
        backend.embed_batch(["no cpu fallback"])


def test_fallback_to_cpu_disabled_raises_for_infer():
    backend = make_backend(mlx_available=False)
    backend.fallback_to_cpu = False
    with pytest.raises(RuntimeError):
        backend.infer("no cpu fallback")


def test_unicode_embedding_is_deterministic():
    backend = make_backend(mlx_available=False)
    assert backend.embed("café déjà vu") == backend.embed("café déjà vu")


def test_batch_size_is_preserved():
    backend = make_backend(apple_silicon=False, mlx_available=False)
    backend.batch_size = 64
    assert backend.batch_size == 64


def test_environment_snapshot_is_reasonable():
    backend = make_backend()
    info = backend.info
    assert info.environment["mlx"] in {"true", "false"}
    assert info.environment["mlx_lm"] in {"true", "false"}


def test_get_best_backend_description_matches_backend():
    backend = make_backend()
    description = backend.describe()
    assert description["dimensions"] == backend.dimensions


def test_backend_reason_mentions_cpu_when_unavailable():
    backend = make_backend(apple_silicon=False, mlx_available=False)
    assert "CPU" in backend.info.reason.upper()
