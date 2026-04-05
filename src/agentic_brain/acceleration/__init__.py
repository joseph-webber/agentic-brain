# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""Hardware acceleration helpers."""

from .mlx_backend import MLXBackend, MLXBackendInfo, get_best_backend

__all__ = ["MLXBackend", "MLXBackendInfo", "get_best_backend"]
