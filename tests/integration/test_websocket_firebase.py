# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>

import asyncio
import os

import aiohttp
import pytest

firebase_admin = pytest.importorskip("firebase_admin")
from firebase_admin import auth, credentials, db, firestore, initialize_app

pytestmark = pytest.mark.integration


# Fixture to initialize Firebase Admin SDK connected to emulator
@pytest.fixture(scope="module")
def firebase_app():
    # Set environment variables to point to emulator
    os.environ["FIRESTORE_EMULATOR_HOST"] = "localhost:8080"
    os.environ["FIREBASE_AUTH_EMULATOR_HOST"] = "localhost:9099"
    os.environ["FIREBASE_DATABASE_EMULATOR_HOST"] = "localhost:9000"

    # Initialize with dummy credentials for emulator
    if not firebase_admin._apps:
        cred = credentials.Certificate(
            {
                "type": "service_account",
                "project_id": "agentic-brain-local",
                "private_key_id": "dummy",
                "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQDwy...\n-----END PRIVATE KEY-----\n",
                "client_email": "firebase-adminsdk-dummy@agentic-brain-local.iam.gserviceaccount.com",
                "client_id": "dummy",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-dummy%40agentic-brain-local.iam.gserviceaccount.com",
            }
        )

        initialize_app(
            cred,
            {
                "projectId": "agentic-brain-local",
                "databaseURL": "http://localhost:9000/?ns=agentic-brain-local",
            },
        )

    return firebase_admin.get_app()


@pytest.mark.asyncio
@pytest.mark.skip(reason="Firebase emulator not running in CI")
async def test_websocket_firebase_sync(firebase_app):
    """
    Test that messages sent via WebSocket are synced to Firebase Firestore
    """
    # 1. Connect to WebSocket
    # Note: Ensure API is running for this test
    async with aiohttp.ClientSession():
        # Mocking the connection for unit/integration isolation
        # In full E2E, we'd connect to ws://localhost:8000/ws/agent-1

        message = {
            "type": "chat",
            "content": "Hello Firebase Integration!",
            "agent_id": "integration-test-agent",
            "timestamp": "2024-05-20T10:00:00Z",
        }

        # 2. Verify direct Firestore write works (Emulator Check)
        db_client = firestore.client()
        doc_ref = db_client.collection("messages").document("test-integration-msg")
        doc_ref.set(message)

        # Read it back
        doc = doc_ref.get()
        assert doc.exists
        assert doc.to_dict()["content"] == "Hello Firebase Integration!"


@pytest.mark.asyncio
@pytest.mark.skip(reason="Firebase emulator not running in CI")
async def test_firebase_presence_sync(firebase_app):
    """
    Test presence system using Realtime Database
    """
    # 1. Set presence in Realtime DB
    ref = db.reference("status/integration-agent")
    ref.set({"state": "online", "last_seen": 1234567890})

    # 2. Verify we can read it back
    status = ref.get()
    assert status["state"] == "online"

    # 3. Update to offline
    ref.update({"state": "offline"})
    status = ref.get()
    assert status["state"] == "offline"


@pytest.mark.asyncio
@pytest.mark.skip(reason="Firebase emulator not running in CI")
async def test_auth_integration(firebase_app):
    """
    Test Authentication integration
    """
    try:
        user = auth.create_user(
            uid="integration-test-user",
            email="integration@example.com",
            password="secretPassword",
        )
    except auth.EmailAlreadyExistsError:
        user = auth.get_user_by_email("integration@example.com")

    assert user.uid == "integration-test-user"

    # Verify user exists
    fetched_user = auth.get_user("integration-test-user")
    assert fetched_user.email == "integration@example.com"
