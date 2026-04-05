# SPDX-License-Identifier: Apache-2.0
"""
Lightweight REST API router for Agentic Brain.

Provides RAG query, indexing, graph queries, evaluation, metrics and configuration
endpoints. Adds simple API-key authentication middleware and an in-process
rate-limiter to protect endpoints in environments where external tooling
(slowapi) is not available.

This module exposes register_rest_routes(app) which is called from
api.routes.register_routes to mount the router into the main application.

Author: Copilot
"""
from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from typing import Deque

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware import Middleware
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware

from ..monitoring.metrics import global_metrics
from .auth import AuthContext, get_api_keys, require_auth

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000, example="What is AI?")
    top_k: int = Field(5, gt=0, le=50)


class SourceItem(BaseModel):
    id: str
    score: float
    snippet: str


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceItem] = []


class IndexRequest(BaseModel):
    doc_id: str | None = None
    content: str = Field(..., min_length=1)
    metadata: dict | None = None


class IndexResponse(BaseModel):
    id: str
    status: str


class GraphQueryRequest(BaseModel):
    cypher: str = Field(..., min_length=1)


class GraphQueryResponse(BaseModel):
    results: list[dict] = []


class EvaluateRequest(BaseModel):
    reference: str = Field(..., min_length=1)
    candidate: str = Field(..., min_length=1)


class EvaluateResponse(BaseModel):
    score: float
    reason: str | None = None


class ConfigModel(BaseModel):
    values: dict = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


# ---------------------------------------------------------------------------
# Simple middleware: API key auth and rate limiter
# ---------------------------------------------------------------------------


class ApiKeyAuthMiddleware(BaseHTTPMiddleware):
    """Attach validated API key (if provided) to request.state.api_key."""

    async def dispatch(self, request: Request, call_next):
        api_key = request.headers.get("X-API-Key") or request.query_params.get(
            "api_key"
        )
        request.state.api_key = None
        if api_key:
            valid = get_api_keys()
            if api_key in valid:
                request.state.api_key = api_key
        return await call_next(request)


class SimpleRateLimitMiddleware(BaseHTTPMiddleware):
    """In-process sliding window rate limiter.

    Authenticated (API key): default 100/min
    Anonymous (by IP): default 10/min
    """

    def __init__(
        self,
        app,
        *,
        auth_limit: int = 100,
        anon_limit: int = 10,
        window_seconds: int = 60,
    ):
        super().__init__(app)
        self.auth_limit = int(os.getenv("REST_RATE_LIMIT_AUTH", str(auth_limit)))
        self.anon_limit = int(os.getenv("REST_RATE_LIMIT_ANON", str(anon_limit)))
        self.window = window_seconds
        self.calls: dict[str, Deque[float]] = defaultdict(lambda: deque())

    async def dispatch(self, request: Request, call_next):
        # Determine key: api_key if present else client ip
        key = None
        if getattr(request.state, "api_key", None):
            key = f"api:{request.state.api_key}"
            limit = self.auth_limit
        else:
            client = request.client.host if request.client else "unknown"
            key = f"ip:{client}"
            limit = self.anon_limit

        now = time.time()
        q = self.calls[key]
        # Evict old timestamps
        cutoff = now - self.window
        while q and q[0] <= cutoff:
            q.popleft()

        if len(q) >= limit:
            # Return JSON response instead of raising to avoid TaskGroup exception
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"error": "Rate limit exceeded"},
            )

        q.append(now)
        response = await call_next(request)
        return response


# ---------------------------------------------------------------------------
# Router and registration
# ---------------------------------------------------------------------------

router = APIRouter()

# In-memory config store (app.state.config will be authoritative if set)
_default_config = {"version": "1.0", "name": "agentic-brain-rest"}


@router.post("/query", response_model=QueryResponse, tags=["rag"])
async def rag_query(req: QueryRequest, request: Request):
    """Simple RAG query placeholder. Returns an answer and fake sources."""
    # Record metrics
    global_metrics.record_request()

    # Placeholder logic: echo + fake sources
    answer = f"Answer: {req.question}"
    sources = [
        SourceItem(id=f"doc_{i}", score=1.0 / (i + 1), snippet=f"Snippet for {i}")
        for i in range(min(req.top_k, 5))
    ]
    return QueryResponse(answer=answer, sources=sources)


@router.post("/index", response_model=IndexResponse, tags=["rag"])
async def index_document(payload: IndexRequest, request: Request):
    """Index or ingest a document into the knowledge store (placeholder)."""
    global_metrics.record_request()
    # Simulate storing and returning an ID
    doc_id = payload.doc_id or f"doc_{int(time.time()*1000)}"
    return IndexResponse(id=doc_id, status="indexed")


@router.get("/metrics", summary="Prometheus metrics", tags=["health"])
async def metrics_endpoint():
    """Expose Prometheus metrics collected by the in-process collector."""
    body = global_metrics.generate_prometheus_metrics()
    return Response(content=body, media_type="text/plain")


from fastapi.responses import (
    JSONResponse,
    Response,
)  # placed here to avoid import ordering


@router.post("/graph/query", response_model=GraphQueryResponse, tags=["graph"])
async def graph_query(payload: GraphQueryRequest, request: Request):
    """Run a graph query against Neo4j (placeholder)."""
    global_metrics.record_request()
    # Placeholder: return cypher echoed back
    results = [{"row": [payload.cypher], "meta": {}}]
    return GraphQueryResponse(results=results)


@router.post("/evaluate", response_model=EvaluateResponse, tags=["rag"])
async def evaluate(payload: EvaluateRequest, request: Request):
    """Evaluate candidate against reference (simple length-based score)."""
    global_metrics.record_request()
    # Very simple eval: proportion of matching words
    ref_words = set(payload.reference.split())
    cand_words = set(payload.candidate.split())
    score = 0.0 if not ref_words else len(ref_words & cand_words) / len(ref_words)
    return EvaluateResponse(score=round(float(score), 3), reason="simple token overlap")


@router.get("/config", response_model=ConfigModel, tags=["config"])
async def get_config(request: Request):
    global_metrics.record_request()
    cfg = getattr(request.app.state, "rest_config", _default_config)
    return ConfigModel(values=cfg)


@router.put("/config", response_model=ConfigModel, tags=["config"])
async def update_config(
    new_cfg: ConfigModel, request: Request, auth: AuthContext = Depends(require_auth)
):
    """Update in-memory config. In production this should persist to file or DB.

    This endpoint requires authentication when AUTH_ENABLED=true.
    """
    global_metrics.record_request()
    request.app.state.rest_config = new_cfg.values
    return ConfigModel(values=request.app.state.rest_config)


def register_rest_routes(app: FastAPI):
    """Attach middleware and register the REST router on the app.

    Important: add the API key auth middleware BEFORE the rate limiter so that
    request.state.api_key is populated when the limiter runs. Starlette executes
    middleware in reverse order of registration, so register the rate limiter
    first and then the auth middleware.
    """
    # Register rate limiter first (outer) then auth middleware so auth runs first
    app.add_middleware(SimpleRateLimitMiddleware)
    app.add_middleware(ApiKeyAuthMiddleware)
    app.include_router(router)


__all__ = ["register_rest_routes", "router"]
