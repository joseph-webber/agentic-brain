#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright 2026 Joseph Webber
"""
10 - JWT Authentication
=========================

Secure your AI agent API with JWT authentication!
Full example with user registration, login, and protected endpoints.

Features:
- JWT token generation and validation
- Password hashing with bcrypt
- Protected endpoints
- Token refresh
- Rate limiting per user

Run:
    python examples/10_with_auth.py

Test flow:
    1. Register: POST /auth/register
    2. Login: POST /auth/login
    3. Chat: POST /chat (with Authorization header)

Requirements:
    pip install fastapi uvicorn pyjwt passlib[bcrypt]
    - Ollama or OpenAI configured
"""

import os
from datetime import datetime, timedelta
from typing import Optional

import jwt
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr, Field

from agentic_brain import Agent

# ============================================================================
# Configuration
# ============================================================================

# Security settings (use environment variables in production!)
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))


# ============================================================================
# Security Utilities
# ============================================================================

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT bearer token extractor
security = HTTPBearer()


def hash_password(password: str) -> str:
    """Hash a password for storage."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    """Create a JWT refresh token (longer-lived)."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )


# ============================================================================
# In-Memory User Store (use a real database in production!)
# ============================================================================

# Simulated user database
users_db: dict = {}

# User agents (one per user for isolated conversations)
user_agents: dict = {}


# ============================================================================
# Pydantic Models
# ============================================================================


class UserRegister(BaseModel):
    """User registration request."""

    email: EmailStr
    password: str = Field(..., min_length=8)
    name: str = Field(..., min_length=2)

    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com",
                "password": "securepassword123",
                "name": "John Doe",
            }
        }


class UserLogin(BaseModel):
    """User login request."""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    """Token refresh request."""

    refresh_token: str


class ChatRequest(BaseModel):
    """Chat request (requires authentication)."""

    message: str = Field(..., min_length=1, max_length=10000)


class ChatResponse(BaseModel):
    """Chat response."""

    response: str
    user: str
    timestamp: str


class UserInfo(BaseModel):
    """User information."""

    email: str
    name: str
    created_at: str


# ============================================================================
# Dependencies
# ============================================================================


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    Dependency to get the current authenticated user.

    Validates the JWT token and returns user info.
    """
    token = credentials.credentials
    payload = decode_token(token)

    # Verify it's an access token
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type"
        )

    email = payload.get("sub")
    if not email or email not in users_db:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )

    return users_db[email]


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="Secure AI Chat API",
    description="AI Chat API with JWT Authentication",
    version="1.0.0",
)


# ============================================================================
# Auth Endpoints
# ============================================================================


@app.post("/auth/register", response_model=TokenResponse, tags=["Auth"])
async def register(user: UserRegister):
    """
    Register a new user.

    Creates user account and returns access tokens.
    """
    # Check if user already exists
    if user.email in users_db:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    # Create user
    users_db[user.email] = {
        "email": user.email,
        "name": user.name,
        "password_hash": hash_password(user.password),
        "created_at": datetime.utcnow().isoformat(),
    }

    # Create agent for this user
    user_agents[user.email] = Agent(
        name=f"agent-{user.email}",
        system_prompt=f"You are a helpful assistant for {user.name}.",
    )

    # Generate tokens
    access_token = create_access_token(
        {"sub": user.email},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    refresh_token = create_refresh_token({"sub": user.email})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@app.post("/auth/login", response_model=TokenResponse, tags=["Auth"])
async def login(credentials: UserLogin):
    """
    Login with email and password.

    Returns access and refresh tokens.
    """
    # Find user
    user = users_db.get(credentials.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )

    # Verify password
    if not verify_password(credentials.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )

    # Create agent if doesn't exist
    if credentials.email not in user_agents:
        user_agents[credentials.email] = Agent(
            name=f"agent-{credentials.email}",
            system_prompt=f"You are a helpful assistant for {user['name']}.",
        )

    # Generate tokens
    access_token = create_access_token(
        {"sub": credentials.email},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    refresh_token = create_refresh_token({"sub": credentials.email})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@app.post("/auth/refresh", response_model=TokenResponse, tags=["Auth"])
async def refresh_token(request: RefreshRequest):
    """
    Refresh access token using refresh token.
    """
    payload = decode_token(request.refresh_token)

    # Verify it's a refresh token
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type"
        )

    email = payload.get("sub")
    if not email or email not in users_db:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )

    # Generate new tokens
    access_token = create_access_token(
        {"sub": email}, expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    refresh_token = create_refresh_token({"sub": email})

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


# ============================================================================
# Protected Endpoints
# ============================================================================


@app.get("/me", response_model=UserInfo, tags=["User"])
async def get_me(user: dict = Depends(get_current_user)):
    """
    Get current user info.

    Requires authentication.
    """
    return UserInfo(
        email=user["email"], name=user["name"], created_at=user["created_at"]
    )


@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(request: ChatRequest, user: dict = Depends(get_current_user)):
    """
    Send a message to the AI agent.

    Requires authentication. Each user has their own conversation history.
    """
    email = user["email"]

    # Get user's agent
    agent = user_agents.get(email)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Agent not initialized",
        )

    # Get response
    response = await agent.chat_async(request.message)

    return ChatResponse(
        response=response, user=user["name"], timestamp=datetime.utcnow().isoformat()
    )


@app.post("/chat/reset", tags=["Chat"])
async def reset_chat(user: dict = Depends(get_current_user)):
    """
    Reset conversation history.

    Clears your chat history for a fresh start.
    """
    email = user["email"]

    if email in user_agents:
        user_agents[email].clear_history()

    return {"message": "Conversation reset", "user": user["name"]}


# ============================================================================
# Main Entry Point
# ============================================================================


def main():
    """Run the authenticated API server."""
    import uvicorn

    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + "   Secure AI Chat with JWT Auth".center(58) + "║")
    print("╚" + "=" * 58 + "╝")
    print(f"\n🌐 Server starting at http://{HOST}:{PORT}")
    print(f"📚 API docs at http://localhost:{PORT}/docs")
    print("\nTest flow:")
    print("  1. POST /auth/register - Create account")
    print("  2. POST /auth/login - Get tokens")
    print("  3. POST /chat - Chat (with Bearer token)")
    print("\nPress Ctrl+C to stop\n")

    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
