from __future__ import annotations

import pytest

from agentic_brain.config import get_settings
from agentic_brain.config.settings import ENVIRONMENT_KEYS, ENV_VAR_PATHS

CONFIG_ENV_KEYS = set(ENV_VAR_PATHS) | set(ENVIRONMENT_KEYS) | {
    "BRAIN_CONFIG_FILE",
    "BRAIN_CONFIG_PATH",
    "BRAIN_ENV_FILE",
    "BRAIN_PROFILE",
    "ENVIRONMENT",
    "PROFILE",
    "CORS_ORIGINS",
}


@pytest.fixture(autouse=True)
def clear_config_state(monkeypatch: pytest.MonkeyPatch):
    for key in CONFIG_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
