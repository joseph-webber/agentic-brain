# ============================================================================
# STAGE 1: Builder - Build wheels and dependencies
# ============================================================================
FROM python:3.12-slim AS builder

LABEL org.opencontainers.image.title="Agentic Brain"
LABEL org.opencontainers.image.description="Universal AI Assistant Framework"
LABEL org.opencontainers.image.source="https://github.com/joseph-webber/agentic-brain"

# Configure pip for corporate proxies (Windows SSL interception)
ENV PIP_TRUSTED_HOST="pypi.org pypi.python.org files.pythonhosted.org"

# SSL/TLS settings for corporate networks with SSL inspection proxies
ENV PYTHONHTTPSVERIFY=0
ENV REQUESTS_CA_BUNDLE=""
ENV CURL_CA_BUNDLE=""
ENV NODE_TLS_REJECT_UNAUTHORIZED=0

WORKDIR /build

# NOTE: pip config global.trusted-host doesn't work on Windows/corporate networks
# Use --trusted-host flags on EVERY pip command instead

# Upgrade pip first to clear cache
RUN pip install --no-cache-dir --upgrade pip \
    --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy only what's needed for building
COPY pyproject.toml README.md ./
COPY src/ ./src/

# Build wheel (with trusted hosts for corporate proxies)
RUN pip install --no-cache-dir \
    --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org \
    build && \
    python -m build --wheel && \
    pip wheel --no-cache-dir \
    --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org \
    --wheel-dir /wheels dist/*.whl

# ============================================================================
# STAGE 2: Development - Hot reload and tooling
# ============================================================================
FROM python:3.12-slim AS development

# Configure pip for corporate proxies (Windows SSL interception)
ENV PIP_TRUSTED_HOST="pypi.org pypi.python.org files.pythonhosted.org"

# SSL/TLS settings for corporate networks with SSL inspection proxies
ENV PYTHONHTTPSVERIFY=0
ENV REQUESTS_CA_BUNDLE=""
ENV CURL_CA_BUNDLE=""
ENV NODE_TLS_REJECT_UNAUTHORIZED=0

WORKDIR /app

# Configure pip for corporate proxies (trusted hosts) - MUST be in EACH stage!
RUN pip config set global.trusted-host "pypi.org pypi.python.org files.pythonhosted.org"

# Upgrade pip first to clear cache
RUN pip install --no-cache-dir --upgrade pip \
    --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org

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

# Install package in editable mode with dev extras (with trusted hosts for corporate proxies)
RUN pip install --no-cache-dir --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org -e ".[dev]"

# Explicitly install uvicorn with standard extras for API server support
RUN pip install --no-cache-dir --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org uvicorn[standard]

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

# Configure pip for corporate proxies (Windows SSL interception)
ENV PIP_TRUSTED_HOST="pypi.org pypi.python.org files.pythonhosted.org"

# SSL/TLS settings for corporate networks with SSL inspection proxies
ENV PYTHONHTTPSVERIFY=0
ENV REQUESTS_CA_BUNDLE=""
ENV CURL_CA_BUNDLE=""
ENV NODE_TLS_REJECT_UNAUTHORIZED=0

WORKDIR /app

# Install only runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy wheels from builder and install (with trusted hosts for corporate proxies)
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir \
    --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org \
    /wheels/*.whl && \
    rm -rf /wheels

# Explicitly install uvicorn with standard extras for API server support
RUN pip install --no-cache-dir --trusted-host pypi.org --trusted-host pypi.python.org --trusted-host files.pythonhosted.org uvicorn[standard]

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
