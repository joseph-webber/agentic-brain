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

"""WordPress integration package.

This package replaces the previous single-module ``commerce/wordpress.py``
implementation while keeping backwards-compatible import paths.

The legacy test suite patches ``agentic_brain.commerce.wordpress.asyncio.sleep``.
To keep that stable, the package imports :mod:`asyncio` at the top level.
"""

from __future__ import annotations

import asyncio as asyncio  # re-export for backwards-compatible patch paths

from .client import (
    WordPressAPIError,
    WordPressClient,
    WordPressConfig,
    WPAuth,
    WPCategory,
    WPComment,
    WPMedia,
    WPPage,
    WPPost,
    WPRenderedText,
    WPTag,
    WPUser,
)
from .multisite import WordPressMultisiteClient, WordPressSite

__all__ = [
    "asyncio",
    "WPAuth",
    "WPCategory",
    "WPComment",
    "WPMedia",
    "WPPage",
    "WPPost",
    "WPRenderedText",
    "WPTag",
    "WPUser",
    "WordPressAPIError",
    "WordPressClient",
    "WordPressConfig",
    "WordPressMultisiteClient",
    "WordPressSite",
]
