# ============================================================================
# STAGE 1: Builder - Build wheels and dependencies
# ============================================================================
FROM python:3.12-slim AS builder

LABEL org.opencontainers.image.title="Agentic Brain"
LABEL org.opencontainers.image.description="Universal AI Assistant Framework"
LABEL org.opencontainers.image.source="https://github.com/joseph-webber/agentic-brain"

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy only what's needed for building
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Build wheel
RUN pip install --no-cache-dir build && \
    python -m build --wheel && \
    pip wheel --no-cache-dir --wheel-dir /wheels dist/*.whl

# ============================================================================
# STAGE 2: Development - Hot reload and tooling
# ============================================================================
FROM python:3.12-slim AS development

WORKDIR /app

# Install development and testing dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy project files for editable install
COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY tests/ ./tests/

# Install package in editable mode with dev extras
RUN pip install --no-cache-dir -e ".[dev]"

# Create non-root user for development
RUN useradd -m -u 1000 -s /bin/bash agentic && \
    mkdir -p /app/data && \
    chown -R agentic:agentic /app

USER agentic

# Expose API port
EXPOSE 8000

# Default command for development: enable auto-reload
CMD ["agentic-brain", "serve", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ============================================================================
# STAGE 3: Production - Minimal runtime image
# ============================================================================
FROM python:3.12-slim

LABEL org.opencontainers.image.title="Agentic Brain"
LABEL org.opencontainers.image.description="Universal AI Assistant Framework"
LABEL org.opencontainers.image.source="https://github.com/joseph-webber/agentic-brain"

WORKDIR /app

# Install only runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy wheels from builder and install
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/*.whl && \
    rm -rf /wheels

# Create non-root user for security
RUN useradd -m -u 1000 -s /bin/bash agentic && \
    mkdir -p /app/data && \
    chown -R agentic:agentic /app

# Switch to non-root user
USER agentic

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Default command: run the API server
CMD ["agentic-brain", "serve", "--host", "0.0.0.0", "--port", "8000"]
