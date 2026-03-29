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

"""CI tests for hardware acceleration detection."""

from __future__ import annotations

import builtins
import platform
from unittest.mock import patch

import pytest

from agentic_brain.rag.embeddings import detect_hardware


def has_module(module_name: str) -> bool:
    """Return True when a module can be imported."""
    try:
        __import__(module_name)
        return True
    except ImportError:
        return False


def test_mlx_detection():
    """Test MLX is detected on Apple Silicon."""
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        pytest.skip("Not Apple Silicon")

    if not has_module("mlx.core"):
        pytest.skip("MLX not installed")

    best_device, info = detect_hardware()

    assert info["apple_silicon"] is True
    assert info["mlx"] is True
    assert best_device == "mlx"


def test_cuda_detection():
    """Test CUDA detection."""
    try:
        import torch
    except ImportError:
        pytest.skip("torch not installed")

    if not torch.cuda.is_available():
        pytest.skip("CUDA not available")

    best_device, info = detect_hardware()

    assert info["cuda"] is True
    assert info["cuda_version"] == torch.version.cuda
    assert best_device == "cuda"


def test_rocm_detection():
    """Test ROCm detection."""
    try:
        import torch
    except ImportError:
        pytest.skip("torch not installed")

    hip_version = getattr(torch.version, "hip", None)
    if not hip_version:
        pytest.skip("ROCm not available")

    best_device, info = detect_hardware()

    assert info["rocm"] is True
    assert info.get("rocm_version") == hip_version
    assert best_device == "cuda"


def test_cpu_fallback():
    """Test CPU fallback works."""

    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "mlx" or name.startswith("mlx."):
            raise ImportError("mlx unavailable")
        if name == "torch" or name.startswith("torch."):
            raise ImportError("torch unavailable")
        return original_import(name, globals, locals, fromlist, level)

    with patch("builtins.__import__", side_effect=fake_import):
        best_device, info = detect_hardware()

    assert best_device == "cpu"
    assert info["cuda"] is False
    assert info["mlx"] is False
    assert info["mps"] is False
    assert info["rocm"] is False
