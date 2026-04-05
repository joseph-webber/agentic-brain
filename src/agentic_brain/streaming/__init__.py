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

"""Streaming response support for the Agentic Brain API."""

from .stream_handler import (
    StreamingResponse,
    StreamProvider,
    StreamToken,
    iter_chunked_lines,
    iter_sse_payloads,
    iter_text_chunks,
)

__all__ = [
    "StreamingResponse",
    "StreamProvider",
    "StreamToken",
    "iter_chunked_lines",
    "iter_sse_payloads",
    "iter_text_chunks",
]
