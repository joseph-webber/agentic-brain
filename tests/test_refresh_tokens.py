# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""Tests for JWT refresh token service."""

import time
from datetime import UTC, datetime, timedelta, timezone

import pytest

from agentic_brain.auth.refresh_tokens import (
    InMemoryRefreshTokenStore,
    RefreshTokenData,
    RefreshTokenResult,
    RefreshTokenService,
)


class TestRefreshTokenData:
    """Tests for RefreshTokenData model."""

    def test_create(self):
        """Test creating refresh token data."""
        data = RefreshTokenData(
            token_hash="abc123",
            user_id="user1",
            user_login="testuser",
            expires_at=datetime.now(UTC) + timedelta(days=7),
            family_id="family1",
        )
        assert data.user_id == "user1"
        assert data.user_login == "testuser"
        assert data.revoked is False

    def test_is_expired(self):
        """Test expiration check."""
        past = datetime.now(UTC) - timedelta(hours=1)
        data = RefreshTokenData(
            token_hash="abc",
            user_id="user1",
            user_login="testuser",
            expires_at=past,
            family_id="f1",
        )
        assert data.is_expired is True

    def test_is_not_expired(self):
        """Test non-expired token."""
        future = datetime.now(UTC) + timedelta(hours=1)
        data = RefreshTokenData(
            token_hash="abc",
            user_id="user1",
            user_login="testuser",
            expires_at=future,
            family_id="f1",
        )
        assert data.is_expired is False

    def test_is_valid_when_not_revoked_and_not_expired(self):
        """Test validity check."""
        future = datetime.now(UTC) + timedelta(hours=1)
        data = RefreshTokenData(
            token_hash="abc",
            user_id="user1",
            user_login="testuser",
            expires_at=future,
            family_id="f1",
            revoked=False,
        )
        assert data.is_valid is True

    def test_is_invalid_when_revoked(self):
        """Test revoked token is invalid."""
        future = datetime.now(UTC) + timedelta(hours=1)
        data = RefreshTokenData(
            token_hash="abc",
            user_id="user1",
            user_login="testuser",
            expires_at=future,
            family_id="f1",
            revoked=True,
        )
        assert data.is_valid is False


class TestRefreshTokenResult:
    """Tests for RefreshTokenResult."""

    def test_success_result(self):
        """Test successful result."""
        result = RefreshTokenResult(
            success=True,
            access_token="access123",
            refresh_token="refresh123",
            expires_in=3600,
        )
        assert result.success is True
        assert result.error is None

    def test_failed_result(self):
        """Test failed result factory method."""
        result = RefreshTokenResult.failed("invalid_token", "Token has been revoked")
        assert result.success is False
        assert result.error == "invalid_token"
        assert result.error_description == "Token has been revoked"


class TestInMemoryRefreshTokenStore:
    """Tests for in-memory token store."""

    @pytest.fixture
    def store(self):
        """Create fresh store for each test."""
        return InMemoryRefreshTokenStore()

    @pytest.fixture
    def sample_token_data(self):
        """Sample token data for testing."""
        return RefreshTokenData(
            token_hash="hash123",
            user_id="user1",
            user_login="testuser",
            expires_at=datetime.now(UTC) + timedelta(days=7),
            family_id="family1",
        )

    @pytest.mark.asyncio
    async def test_save_and_get(self, store, sample_token_data):
        """Test saving and retrieving token."""
        await store.save(sample_token_data)
        retrieved = await store.get("hash123")
        assert retrieved is not None
        assert retrieved.user_id == "user1"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, store):
        """Test retrieving non-existent token."""
        retrieved = await store.get("nonexistent")
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_revoke(self, store, sample_token_data):
        """Test revoking token."""
        await store.save(sample_token_data)
        result = await store.revoke("hash123", reason="test")
        assert result is True
        token = await store.get("hash123")
        assert token.revoked is True

    @pytest.mark.asyncio
    async def test_revoke_nonexistent(self, store):
        """Test revoking non-existent token."""
        result = await store.revoke("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_revoke_family(self, store):
        """Test revoking entire token family."""
        # Create multiple tokens in same family
        for i in range(3):
            await store.save(
                RefreshTokenData(
                    token_hash=f"hash{i}",
                    user_id="user1",
                    user_login="testuser",
                    expires_at=datetime.now(UTC) + timedelta(days=7),
                    family_id="family1",
                )
            )

        count = await store.revoke_family("family1")
        assert count == 3

        # All should be revoked
        for i in range(3):
            token = await store.get(f"hash{i}")
            assert token.revoked is True

    @pytest.mark.asyncio
    async def test_revoke_user(self, store):
        """Test revoking all tokens for user."""
        # Create tokens in different families
        await store.save(
            RefreshTokenData(
                token_hash="hash1",
                user_id="user1",
                user_login="testuser",
                expires_at=datetime.now(UTC) + timedelta(days=7),
                family_id="family1",
            )
        )
        await store.save(
            RefreshTokenData(
                token_hash="hash2",
                user_id="user1",
                user_login="testuser",
                expires_at=datetime.now(UTC) + timedelta(days=7),
                family_id="family2",
            )
        )
        # Different user - should not be affected
        await store.save(
            RefreshTokenData(
                token_hash="hash3",
                user_id="user2",
                user_login="otheruser",
                expires_at=datetime.now(UTC) + timedelta(days=7),
                family_id="family3",
            )
        )

        count = await store.revoke_user("user1")
        assert count == 2

        # User1 tokens revoked
        token1 = await store.get("hash1")
        token2 = await store.get("hash2")
        assert token1.revoked is True
        assert token2.revoked is True

        # User2 token still valid
        token3 = await store.get("hash3")
        assert token3.revoked is False


class TestRefreshTokenService:
    """Tests for RefreshTokenService."""

    @pytest.fixture
    def service(self):
        """Create service with in-memory store."""
        store = InMemoryRefreshTokenStore()
        return RefreshTokenService(
            store=store,
            access_token_ttl_seconds=3600,
            refresh_token_ttl_seconds=604800,  # 7 days
            rotate_on_refresh=True,
        )

    @staticmethod
    def mock_access_token_generator(user_id: str) -> str:
        """Mock access token generator for testing."""
        return f"mock_access_token_{user_id}_{datetime.now(UTC).timestamp()}"

    @pytest.mark.asyncio
    async def test_create_tokens(self, service):
        """Test creating access and refresh tokens."""
        result = await service.create_tokens(
            user_id="user1",
            user_login="testuser",
            generate_access_token=self.mock_access_token_generator,
        )

        assert result.success is True
        assert result.access_token is not None
        assert result.refresh_token is not None
        assert result.expires_in == 3600

    @pytest.mark.asyncio
    async def test_refresh_tokens(self, service):
        """Test refreshing tokens."""
        # Create initial tokens
        result = await service.create_tokens(
            user_id="user1",
            user_login="testuser",
            generate_access_token=self.mock_access_token_generator,
        )
        refresh_token = result.refresh_token

        # Wait a tiny bit to ensure different timestamps
        time.sleep(0.01)

        # Refresh
        new_result = await service.refresh(
            refresh_token,
            generate_access_token=self.mock_access_token_generator,
        )

        assert new_result.success is True
        assert new_result.access_token != result.access_token
        # Refresh token should rotate
        assert new_result.refresh_token != refresh_token

    @pytest.mark.asyncio
    async def test_refresh_invalid_token(self, service):
        """Test refreshing invalid token fails."""
        result = await service.refresh(
            "invalid-token",
            generate_access_token=self.mock_access_token_generator,
        )
        assert result.success is False
        assert "not found" in result.error.lower() or "invalid" in result.error.lower()

    @pytest.mark.asyncio
    async def test_revoke(self, service):
        """Test revoking a refresh token."""
        result = await service.create_tokens(
            user_id="user1",
            user_login="testuser",
            generate_access_token=self.mock_access_token_generator,
        )
        refresh_token = result.refresh_token

        # Revoke
        revoke_success = await service.revoke(refresh_token)
        assert revoke_success is True

        # Try to use revoked token
        new_result = await service.refresh(
            refresh_token,
            generate_access_token=self.mock_access_token_generator,
        )
        assert new_result.success is False

    @pytest.mark.asyncio
    async def test_revoke_all_user_tokens(self, service):
        """Test revoking all tokens for user."""
        # Create multiple token families
        result1 = await service.create_tokens(
            user_id="user1",
            user_login="testuser",
            generate_access_token=self.mock_access_token_generator,
        )
        result2 = await service.create_tokens(
            user_id="user1",
            user_login="testuser",
            generate_access_token=self.mock_access_token_generator,
        )

        # Revoke all
        count = await service.revoke_all_user_tokens("user1")
        assert count >= 2

        # Both should be invalid
        r1 = await service.refresh(
            result1.refresh_token,
            generate_access_token=self.mock_access_token_generator,
        )
        r2 = await service.refresh(
            result2.refresh_token,
            generate_access_token=self.mock_access_token_generator,
        )
        assert r1.success is False
        assert r2.success is False

    @pytest.mark.asyncio
    async def test_token_reuse_detection(self, service):
        """Test reusing old refresh token revokes entire family."""
        # Create tokens
        result = await service.create_tokens(
            user_id="user1",
            user_login="testuser",
            generate_access_token=self.mock_access_token_generator,
        )
        old_refresh = result.refresh_token

        # Rotate to get new token
        new_result = await service.refresh(
            old_refresh,
            generate_access_token=self.mock_access_token_generator,
        )
        new_refresh = new_result.refresh_token

        # Try to use old token again (replay attack)
        reused_result = await service.refresh(
            old_refresh,
            generate_access_token=self.mock_access_token_generator,
        )

        # Should fail and revoke entire family
        assert reused_result.success is False

        # Even the new token should be revoked
        final_result = await service.refresh(
            new_refresh,
            generate_access_token=self.mock_access_token_generator,
        )
        assert final_result.success is False
