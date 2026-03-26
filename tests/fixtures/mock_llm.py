# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
#
# Centralised fixtures for mocking outbound LLM calls during tests.
# This prevents CI environments from attempting real network requests.

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any
from unittest.mock import MagicMock

import pytest
import requests


@pytest.fixture(autouse=True)
def mock_llm_requests(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """
    Automatically intercept outbound LLM HTTP calls when running in CI.

    The fixture stubs both Ollama (local) and OpenAI-style endpoints so that
    unit tests remain deterministic and do not depend on real network access.
    """

    original_post = requests.post

    def _mock_post(url: str, *args: Any, **kwargs: Any) -> MagicMock:
        # Ollama local endpoint
        if "/api/generate" in url:
            mock_resp = MagicMock()
            mock_resp.status_code = 200

            if kwargs.get("stream"):
                mock_resp.iter_lines.return_value = [
                    b'{"response": "Mocked response part 1", "done": false}',
                    b'{"response": " part 2", "done": true}',
                ]
            else:
                mock_resp.json.return_value = {"response": "Mocked LLM response"}
            return mock_resp

        # OpenAI / compatible endpoints
        if "api.openai.com" in url:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "choices": [{"message": {"content": "Mocked OpenAI response"}}]
            }
            return mock_resp

        # Google Gemini endpoints
        if "generativelanguage.googleapis.com" in url:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"text": "Mocked Gemini response"},
                            ]
                        }
                    }
                ]
            }
            return mock_resp

        return original_post(url, *args, **kwargs)

    if os.getenv("CI") or os.getenv("MOCK_LLM"):
        monkeypatch.setattr(requests, "post", _mock_post)

    yield

    if os.getenv("CI") or os.getenv("MOCK_LLM"):
        monkeypatch.setattr(requests, "post", original_post)
