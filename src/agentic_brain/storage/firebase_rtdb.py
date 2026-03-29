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

"""Firebase Realtime Database helpers for state sync and presence."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

try:
    import firebase_admin
    from firebase_admin import credentials, db

    FIREBASE_RTDB_AVAILABLE = True
except ImportError:
    FIREBASE_RTDB_AVAILABLE = False
    firebase_admin = None  # type: ignore[assignment]
    credentials = None  # type: ignore[assignment]
    db = None  # type: ignore[assignment]


@dataclass(slots=True)
class PresenceInfo:
    """Presence information stored in Realtime Database."""

    user_id: str
    status: str = "offline"
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "status": self.status,
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }


class FirebaseRTDBStore:
    """Realtime Database wrapper with offline queueing."""

    def __init__(
        self,
        database_url: str,
        credentials_path: Optional[str] = None,
        app_name: str = "agentic-brain-rtdb",
        cache_path: Optional[str] = None,
    ):
        if not FIREBASE_RTDB_AVAILABLE:
            raise ImportError(
                "firebase-admin not available. Install with: pip install firebase-admin"
            )
        self.database_url = database_url
        self.credentials_path = credentials_path
        self.app_name = app_name
        self.cache_path = Path(
            cache_path or (Path.home() / ".agentic_brain" / "firebase_rtdb_queue.json")
        )
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._app: Any = None
        self._connected = False

    def connect(self) -> bool:
        if self._connected and self._app is not None:
            return True
        try:
            try:
                self._app = firebase_admin.get_app(self.app_name)
            except ValueError:
                options = {"databaseURL": self.database_url}
                if self.credentials_path:
                    cred = credentials.Certificate(self.credentials_path)
                    self._app = firebase_admin.initialize_app(
                        cred, options=options, name=self.app_name
                    )
                else:
                    self._app = firebase_admin.initialize_app(
                        options=options, name=self.app_name
                    )
            self._connected = True
            self.sync_pending_operations()
            return True
        except Exception as exc:
            logger.error("Failed to connect to Firebase RTDB: %s", exc)
            return False

    def _queue_operation(self, operation: dict[str, Any]) -> None:
        existing = []
        if self.cache_path.exists():
            try:
                existing = json.loads(self.cache_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                existing = []
        existing.append(operation)
        self.cache_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    def _flush_queue(self) -> list[dict[str, Any]]:
        if not self.cache_path.exists():
            return []
        try:
            queued = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            queued = []
        self.cache_path.write_text("[]", encoding="utf-8")
        return queued

    def _reference(self, path: str) -> Any:
        return db.reference(path, app=self._app)

    def set_state(self, path: str, value: dict[str, Any], sync: bool = True) -> bool:
        if sync and self.connect():
            self._reference(path).set(value)
            return True
        self._queue_operation({"type": "set", "path": path, "value": value})
        return False

    def get_state(self, path: str, default: Optional[Any] = None) -> Any:
        if not self.connect():
            return default
        value = self._reference(path).get()
        return default if value is None else value

    def delete_state(self, path: str) -> bool:
        if self.connect():
            self._reference(path).delete()
            return True
        self._queue_operation({"type": "delete", "path": path})
        return False

    def batch_update(self, updates: dict[str, Any]) -> bool:
        if self.connect():
            self._reference("/").update(updates)
            return True
        self._queue_operation({"type": "update", "value": updates})
        return False

    def sync_pending_operations(self) -> int:
        if not self._connected:
            return 0
        replayed = 0
        for operation in self._flush_queue():
            op_type = operation.get("type")
            if op_type == "set":
                self._reference(operation["path"]).set(operation["value"])
            elif op_type == "delete":
                self._reference(operation["path"]).delete()
            elif op_type == "update":
                self._reference("/").update(operation["value"])
            replayed += 1
        return replayed

    def set_presence(
        self,
        user_id: str,
        status: str = "online",
        metadata: Optional[dict[str, Any]] = None,
    ) -> PresenceInfo:
        presence = PresenceInfo(user_id=user_id, status=status, metadata=metadata or {})
        self.set_state(f"presence/{user_id}", presence.to_dict())
        return presence

    def mark_offline(self, user_id: str) -> PresenceInfo:
        return self.set_presence(user_id, status="offline")

    def get_presence(self, user_id: str) -> Optional[PresenceInfo]:
        value = self.get_state(f"presence/{user_id}")
        if not value:
            return None
        updated_at = value.get("updated_at")
        return PresenceInfo(
            user_id=value.get("user_id", user_id),
            status=value.get("status", "offline"),
            updated_at=(
                datetime.fromisoformat(updated_at) if updated_at else datetime.now(UTC)
            ),
            metadata=value.get("metadata", {}),
        )

    def is_online(self, user_id: str, max_age_seconds: int = 120) -> bool:
        presence = self.get_presence(user_id)
        if not presence or presence.status != "online":
            return False
        return presence.updated_at >= datetime.now(UTC) - timedelta(
            seconds=max_age_seconds
        )

    @staticmethod
    def security_rules_template(read_authenticated_only: bool = True) -> dict[str, Any]:
        auth_check = "auth != null" if read_authenticated_only else True
        return {
            "rules": {
                ".read": auth_check,
                ".write": "auth != null",
                "presence": {
                    "$uid": {
                        ".read": auth_check,
                        ".write": "auth != null && auth.uid === $uid",
                    }
                },
                "state": {
                    "$session": {
                        ".read": auth_check,
                        ".write": "auth != null",
                    }
                },
            }
        }
