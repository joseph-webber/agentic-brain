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

"""Tests for Firebase Cloud Functions, RTDB, and Storage helpers."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import agentic_brain.storage.firebase_rtdb as firebase_rtdb_module
import agentic_brain.storage.firebase_storage as firebase_storage_module
from agentic_brain.cloud.firebase_functions import FirebaseFunctionsManager
from agentic_brain.storage.firebase_rtdb import FirebaseRTDBStore
from agentic_brain.storage.firebase_storage import FirebaseStorageManager


class TestFirebaseFunctionsManager:
    def test_build_deploy_command(self, tmp_path: Path):
        functions_dir = tmp_path / "functions"
        functions_dir.mkdir()
        (functions_dir / "firebase.json").write_text("{}", encoding="utf-8")
        manager = FirebaseFunctionsManager("demo-project", str(functions_dir))
        definition = manager.pubsub_function("ingestMessages", topic="agentic-sync")
        command = manager.build_deploy_command(definition)
        assert "firebase" in command[0]
        assert "--project" in command
        assert definition.selector() in command

    def test_write_manifest(self, tmp_path: Path):
        functions_dir = tmp_path / "functions"
        functions_dir.mkdir()
        manager = FirebaseFunctionsManager("demo-project", str(functions_dir))
        manifest = manager.write_manifest(
            [
                manager.http_function("chatGateway"),
                manager.scheduled_function("cleanup", schedule="every 5 minutes"),
            ]
        )
        assert manifest.exists()
        assert "chatGateway" in manifest.read_text(encoding="utf-8")


class TestFirebaseRTDBStore:
    def test_security_rules_template(self):
        rules = FirebaseRTDBStore.security_rules_template()
        assert (
            rules["rules"]["presence"]["$uid"][".write"]
            == "auth != null && auth.uid === $uid"
        )

    def test_presence_serialization(self, tmp_path: Path):
        firebase_rtdb_module.FIREBASE_RTDB_AVAILABLE = True
        store = FirebaseRTDBStore(
            database_url="https://demo.firebaseio.com",
            cache_path=str(tmp_path / "rtdb-queue.json"),
        )
        with patch.object(store, "connect", return_value=False):
            result = store.set_state("state/session-1", {"typing": True}, sync=False)
        assert result is False
        assert Path(store.cache_path).exists()


class TestFirebaseStorageManager:
    def test_signed_url_generation(self):
        firebase_storage_module.FIREBASE_STORAGE_AVAILABLE = True
        manager = FirebaseStorageManager(bucket_name="demo.appspot.com")
        mock_blob = MagicMock()
        mock_blob.generate_signed_url.return_value = "https://example.com/signed"
        with patch.object(manager, "_blob", return_value=mock_blob):
            url = manager.get_signed_url("images/test.png")
        assert url == "https://example.com/signed"

    def test_process_image_uses_processor(self):
        firebase_storage_module.FIREBASE_STORAGE_AVAILABLE = True
        manager = FirebaseStorageManager(bucket_name="demo.appspot.com")
        input_blob = MagicMock()
        input_blob.download_as_bytes.return_value = b"raw-image"
        with (
            patch.object(manager, "_blob", return_value=input_blob),
            patch.object(
                manager, "upload_bytes", return_value=MagicMock(path="processed.png")
            ) as upload_bytes,
        ):
            result = manager.process_image(
                "images/source.png",
                "images/processed.png",
                lambda data: data + b"-processed",
            )
        upload_bytes.assert_called_once()
        assert result.path == "processed.png"
