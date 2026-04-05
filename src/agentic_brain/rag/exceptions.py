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

"""RAG-specific exception types.

These wrap lower-level exceptions (I/O, network, model loading) with consistent
error categories so callers can handle failures predictably.
"""

from __future__ import annotations

from typing import Any, Optional


class _BaseRAGError(Exception):
    """Base class for RAG errors."""

    def __init__(self, message: str, *, context: Optional[dict[str, Any]] = None):
        super().__init__(message)
        self.context: dict[str, Any] = context or {}


class ChunkingError(_BaseRAGError):
    """Raised when text chunking fails (empty input, encoding issues, oversize)."""


class EmbeddingError(_BaseRAGError):
    """Raised when embedding generation fails (API failures, rate limits, load errors)."""


class RetrievalError(_BaseRAGError):
    """Raised when retrieval fails (connection errors, timeouts, query failures)."""


class LoaderError(_BaseRAGError):
    """Raised when document loading fails (missing/permission/corrupt file)."""


__all__ = [
    "ChunkingError",
    "EmbeddingError",
    "RetrievalError",
    "LoaderError",
]
