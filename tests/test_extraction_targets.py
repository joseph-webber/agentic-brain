# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
#
# Licensed under the Apache License, Version 2.0 ("License");
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

from __future__ import annotations

import os
from datetime import UTC, timezone

from agentic_brain.agi.causal_reasoning import CausalReasoner, get_reasoner
from agentic_brain.bots.recovery import RecoveryManager
from agentic_brain.bots.secrets import AgentSecrets
from agentic_brain.bots.session import AgentSession, generate_session_id
from agentic_brain.utils.clock import AgentClock


def test_recovery_manager_uses_configurable_checkpoint_root(tmp_path):
    manager = RecoveryManager("agent/demo", checkpoint_root=tmp_path)
    assert manager.agent_id == "agent/demo"
    assert manager.bot_id == "agent/demo"
    assert manager.checkpoint_dir == tmp_path / "agent_demo"


def test_generate_session_id_is_readable_and_unique():
    identifiers = {generate_session_id() for _ in range(32)}
    assert len(identifiers) == 32
    assert all(identifier.startswith("session_") for identifier in identifiers)


def test_agent_session_serialization_round_trip():
    session = AgentSession(agent_id="worker")
    session.start()
    session.end()

    payload = session.to_dict()
    restored = AgentSession.from_dict(payload)

    assert restored.agent_id == "worker"
    assert restored.session_id == session.session_id
    assert restored.started_at is not None
    assert restored.started_at.tzinfo == UTC


def test_agent_secrets_supports_configurable_prefix_and_env_file(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("API_TOKEN=file-token\n")

    store = AgentSecrets(
        service_name="tests",
        env_prefix="CUSTOM",
        env_file_path=env_file,
        keyring_enabled=False,
    )

    os.environ["CUSTOM_API_TOKEN"] = "env-token"
    try:
        assert store.get("API_TOKEN") == "env-token"
        assert store.exists("API_TOKEN")
        assert "API_TOKEN" in store.list_keys()
    finally:
        del os.environ["CUSTOM_API_TOKEN"]


def test_agent_clock_provides_utc_first_timestamp_utilities():
    clock = AgentClock()
    stamped = clock.stamp({})

    assert clock.validate(stamped["timestamp"])
    assert clock.fix("2026-03-29T10:00:00+00:00").endswith("Z")
    assert clock.age_minutes(None) == float("inf")
    assert clock.age_human(stamped["timestamp"]) in {"just now", "0 minutes ago"}


def test_causal_reasoner_is_importable_and_operational():
    reasoner = CausalReasoner()
    reasoner.initialize()
    reasoner.learn_causal_relationship(
        "network down", "service unavailable", mechanism="dependency chain"
    )

    causes = reasoner.infer_causes("service unavailable")

    assert causes
    assert causes[0][0] == "network down"
    assert get_reasoner().get_link_count() >= 1
