# Security Hardening Guide for Agentic Brain

**Last Updated:** 2026-03-25  
**Status:** ✅ PRODUCTION READY  

This guide covers critical security configurations for Agentic Brain before public release.

## Table of Contents

1. [Redis Password Security](#redis-password-security)
2. [WebSocket Authentication](#websocket-authentication)
3. [API Rate Limiting](#api-rate-limiting)
4. [RAG Loader Rate Limiting](#rag-loader-rate-limiting)
5. [Environment Security](#environment-security)
6. [Security Headers](#security-headers)
7. [Deployment Checklist](#deployment-checklist)

---

## Redis Password Security

Redis is a critical component that handles caching, session storage, and inter-bot communication.

### Configuration

#### 1. Docker Compose (REQUIRED)

The docker-compose.yml already includes password enforcement:

```yaml
redis:
  image: redis:7-alpine
  command: redis-server --requirepass ${REDIS_PASSWORD:-agentic_brain_redis_2026}
```

The `--requirepass` flag is **MANDATORY** for production deployments.

#### 2. Environment Variables

Create `.env.docker` (NEVER commit to git):

```bash
# Generate a secure password
openssl rand -base64 32

# Set in .env.docker
REDIS_PASSWORD=your_generated_password_here
```

#### 3. Application Configuration

All Redis clients automatically use the password from `REDIS_PASSWORD` environment variable:

- `src/agentic_brain/router/redis_cache.py` - LLM response caching
- `src/agentic_brain/interbot/protocol.py` - Inter-bot messaging
- `src/agentic_brain/api/redis_health.py` - Health checks
- `src/agentic_brain/config/settings.py` - Configuration management

### Verification

Test Redis authentication:

```bash
# Without password (should FAIL in production)
redis-cli -h localhost -p 6379 ping

# With password (should SUCCEED)
redis-cli -h localhost -p 6379 -a "your_password" ping

# Using Redis URL with password
redis-cli -u redis://:your_password@localhost:6379/0 ping
```

---

## WebSocket Authentication

WebSocket connections are the primary real-time interface. All connections **MUST** authenticate.

### Configuration

#### 1. JWT Secret (REQUIRED)

Set in `.env.docker` or environment:

```bash
# Generate a secure JWT secret
openssl rand -hex 32

# Set in environment
export JWT_SECRET=your_generated_secret_here
```

#### 2. WebSocket Authentication Methods

The WebSocket authenticator supports multiple token delivery methods:

**Method 1: Query Parameter (Recommended)**
```javascript
const token = 'eyJhbGc...'  // Your JWT token
const ws = new WebSocket('wss://api.example.com/ws/chat?token=' + token)
```

**Method 2: Authorization Header**
```javascript
const ws = new WebSocket('wss://api.example.com/ws/chat')
```

**Method 3: Sec-WebSocket-Protocol Header**
```javascript
const ws = new WebSocket(
    'wss://api.example.com/ws/chat',
    ['eyJhbGc...']  // JWT token in protocols
)
```

#### 3. Token Generation

Python example:

```python
import jwt
import os
from datetime import datetime, timedelta

secret = os.getenv("JWT_SECRET")
payload = {
    "sub": "user_id",
    "iat": datetime.utcnow(),
    "exp": datetime.utcnow() + timedelta(hours=1)
}
token = jwt.encode(payload, secret, algorithm="HS256")
```

### Security Features

- **Token expiry:** Maximum 1 hour (configurable)
- **Immediate rejection:** Unauthenticated connections rejected with WS_1008_POLICY_VIOLATION
- **HTTPS/WSS:** Always use wss:// in production (not ws://)
- **Certificate:** Use valid SSL certificate from trusted CA
- **Logging:** All auth failures logged for monitoring

---

## API Rate Limiting

Protects against brute force attacks and denial-of-service (DoS).

### Configuration

```bash
# Install slowapi (optional but recommended)
pip install slowapi
```

### Default Limits

| Endpoint | Authenticated | Anonymous | Purpose |
|----------|---------------|-----------|---------|
| `/api/chat` | 100/min | 10/min | Chat messaging |
| `/ws/chat` | 50/min | 5/min | WebSocket connections |
| `/auth/login` | 10/min | 5/min | Login attempts |
| `/auth/token` | 20/min | 5/min | Token generation |
| **Global** | 1000/min | 100/min | All endpoints |

### Configuration

In `.env`:

```bash
# Rate limiting (if using slowapi)
RATELIMIT_ENABLED=true
RATELIMIT_STORAGE_URL=redis://localhost:6379
```

### Implementation

Rate limiting is implemented in:
- `src/agentic_brain/api/rate_limiting.py` - Middleware and decorators

### Monitoring

Track rate limit hits in logs:

```python
import logging
logger = logging.getLogger("slowapi")
logger.setLevel(logging.INFO)
```

---

## RAG Loader Rate Limiting

**New in v0.6.3** - Advanced rate limiting for RAG document loaders protects against API rate limits and resource exhaustion.

### Overview

The smart rate limiter (`agentic_brain.rag.rate_limiter`) provides:
- **Per-loader rate limits** matching external API constraints
- **Concurrent request limiting** prevents resource exhaustion
- **Exponential backoff** with jitter for failures
- **IP-based rate limiting** for API endpoints
- **Document size and batch limits** prevent memory issues
- **Redis-backed distributed limiting** for multi-instance deployments

### Configuration

#### 1. Loader-Specific Limits

Each loader has tailored limits based on external API constraints:

| Loader | Requests/Min | Max Concurrent | Notes |
|--------|--------------|----------------|-------|
| **Notion** | 3 | 1 | Very strict API limits |
| **GitHub** | 30 | 5 | 5000/hour limit |
| **Slack** | 50 | 3 | Tier 2 rate limit |
| **Confluence** | 100 | 10 | More permissive |
| **Salesforce** | 100 | 5 | Standard tier |
| **JIRA** | 100 | 5 | Atlassian standard |
| **Zendesk** | 200 | 10 | Higher limits |
| **SharePoint** | 60 | 5 | Microsoft throttling |
| **Google Drive** | 100 | 10 | Standard quota |

#### 2. Basic Usage

```python
from agentic_brain.rag.rate_limiter import rate_limited

@rate_limited("github", timeout=60)
async def fetch_repository_data(repo_url: str):
    """Fetch data from GitHub - automatically rate limited"""
    # Your API call here
    pass
```

#### 3. Manual Rate Limiting

```python
from agentic_brain.rag.rate_limiter import get_rate_limiter

limiter = get_rate_limiter()

# Check if can proceed
if await limiter.acquire("notion"):
    try:
        # Make API call
        result = await fetch_notion_data()
        limiter.record_success("notion")
    except Exception as e:
        # Record failure (triggers backoff if rate limit error)
        limiter.record_failure("notion", trigger_backoff=True)
    finally:
        limiter.release("notion")
```

#### 4. Document Size Limits

```python
# Check document size before processing
can_process = await limiter.check_document_limits(
    loader_name="github",
    document_size_mb=25.5,
    batch_size=10
)

if not can_process:
    # Split into smaller batches or reject
    pass
```

#### 5. IP-Based Rate Limiting (API Endpoints)

```python
from agentic_brain.rag.rate_limiter import IPRateLimiter

ip_limiter = IPRateLimiter(requests_per_minute=60)

@app.get("/api/load-document")
async def load_document(request: Request):
    client_ip = request.client.host
    
    if not ip_limiter.is_allowed(client_ip):
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. {ip_limiter.get_remaining(client_ip)} requests remaining"
        )
    
    # Process request
    pass
```

### Redis-Backed Distributed Limiting

For multi-instance deployments, use Redis for shared rate limit state:

```python
from agentic_brain.rag.rate_limiter import SmartRateLimiter

# Initialize with Redis
limiter = SmartRateLimiter(
    use_redis=True,
    redis_url="redis://:password@localhost:6379"
)
```

Benefits:
- Rate limits shared across all API instances
- Consistent limiting in load-balanced environments
- Persistent state across restarts

### Monitoring

#### Get Rate Limit Stats

```python
stats = limiter.get_stats("github")
# Returns:
# {
#     "loader": "github",
#     "requests_last_minute": 15,
#     "limit_per_minute": 30,
#     "concurrent": 2,
#     "max_concurrent": 5,
#     "consecutive_failures": 0,
#     "backoff_active": False,
#     "backoff_remaining": 0
# }
```

#### Log Rate Limit Events

```python
import logging
logging.getLogger("agentic_brain.rag.rate_limiter").setLevel(logging.INFO)
```

### Error Handling

The decorator automatically:
1. **Detects rate limit errors** (429, "rate limit exceeded", "too many requests")
2. **Triggers exponential backoff** with jitter
3. **Re-raises the exception** for your code to handle

```python
@rate_limited("github", timeout=30)
async def fetch_data():
    # If rate limit exceeded after waiting 30s, raises:
    # RateLimitExceeded: Rate limit exceeded for github (waited 30s)
    pass
```

### Best Practices

1. **Use the decorator** - Simplest and most reliable
2. **Set appropriate timeouts** - Balance responsiveness vs success rate
3. **Handle RateLimitExceeded** - Inform user or queue for retry
4. **Monitor stats** - Watch for frequent backoffs (indicates need for tuning)
5. **Use Redis in production** - Essential for multi-instance deployments
6. **Check document limits** - Before processing large batches

### Security Benefits

1. **Prevents API bans** - Respects external service limits
2. **Protects resources** - Concurrent limits prevent memory exhaustion
3. **DoS protection** - IP-based limiting stops floods
4. **Adaptive behavior** - Exponential backoff reduces load during issues
5. **Fair usage** - Prevents single user from monopolizing resources

### Testing

Run the comprehensive test suite:

```bash
pytest tests/test_rag_rate_limiter.py -v
```

Tests cover:
- Per-loader rate limits
- Concurrent limiting
- Exponential backoff
- IP-based limiting
- Document size limits
- Redis fallback
- Edge cases and thread safety

---

## Environment Security

### 1. .gitignore (VERIFIED ✓)

Ensure `.env` files are not committed:

```
.env
.env.local
.env.*.local
.env.docker
!.env.example
!.env.docker.example
```

### 2. Secrets in Code

NEVER hardcode secrets. Use environment variables:

```python
# BAD: Do not use
REDIS_PASSWORD = "my_password"

# GOOD: Use environment variables
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")
```

### 3. Example Files

Keep `.env.example` and `.env.docker.example` safe for public release:

```bash
# These files contain ONLY placeholder values
REDIS_PASSWORD=your_redis_password_here
JWT_SECRET=your_jwt_secret_here
NEO4J_PASSWORD=your_neo4j_password_here
```

### 4. Secrets Scanning

Before release, scan for hardcoded secrets:

```bash
# Using git-secrets
git secrets --scan

# Using detect-secrets
detect-secrets scan

# Using truffleHog
truffleHog filesystem .
```

---

## Security Headers

All responses include OWASP-recommended security headers.

### Headers Added Automatically

| Header | Value | Purpose |
|--------|-------|---------|
| `X-Content-Type-Options` | `nosniff` | Prevent MIME sniffing |
| `X-Frame-Options` | `DENY` | Prevent clickjacking |
| `X-XSS-Protection` | `1; mode=block` | XSS protection |
| `Strict-Transport-Security` | `max-age=31536000` | Force HTTPS |
| `Content-Security-Policy` | `default-src 'self'` | Restrict content sources |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Control referrer info |
| `Permissions-Policy` | Various | Disable unused features |

### Verification

```bash
curl -I https://api.example.com/health
# Check for security headers in response
```

---

## Deployment Checklist

Before public release, verify ALL of these:

### Redis Security
- [ ] Password set and enforced in docker-compose.yml
- [ ] All Redis clients use password
- [ ] redis-cli connection test passes with password
- [ ] Network firewall restricts Redis access (not exposed to internet)

### WebSocket Security
- [ ] JWT_SECRET environment variable set
- [ ] Unauthenticated WebSocket connections rejected
- [ ] Token validation tested
- [ ] WSS (secure WebSocket) enabled in production
- [ ] SSL certificate is valid and up to date

### Rate Limiting
- [ ] slowapi installed and configured
- [ ] Rate limits applied to auth endpoints
- [ ] Global limits in place
- [ ] Monitoring enabled for rate limit violations

### Environment Security
- [ ] `.env` and `.env.docker` added to .gitignore
- [ ] No secrets in committed code
- [ ] `.env.example` contains only placeholders
- [ ] Secrets scanning passed

### Security Headers
- [ ] Middleware configured and active
- [ ] Headers verified in HTTP responses
- [ ] CSP policy tested with real workload

### Dependencies
- [ ] All packages up to date
- [ ] Security vulnerabilities checked
- [ ] CVEs scanned

### Logging & Monitoring
- [ ] Security events logged
- [ ] Rate limit violations tracked
- [ ] Authentication failures logged
- [ ] Alerts configured for suspicious activity

### Testing
- [ ] Security tests passing
- [ ] Auth tests passing
- [ ] WebSocket tests passing
- [ ] No security warnings in logs

---

## Production Deployment

### Quick Start

```bash
# 1. Generate secure passwords
openssl rand -base64 32
openssl rand -hex 32

# 2. Create .env.docker (NEVER commit)
# Copy values from above and populate .env.docker

# 3. Deploy with environment file
docker-compose --env-file .env.docker up -d

# 4. Verify security
docker-compose logs redis | grep requirepass
```

### Monitoring

Watch for security events:

```bash
# Redis password failures
docker-compose logs redis | grep "NOAUTH"

# WebSocket auth failures
docker-compose logs api | grep "WebSocket REJECTED"

# Rate limit hits
docker-compose logs api | grep "Rate limit exceeded"
```

---

## References

- OWASP Security Headers: https://owasp.org/www-project-secure-headers/
- OWASP API Security: https://owasp.org/www-project-api-security/
- Redis Security: https://redis.io/topics/security
- FastAPI Security: https://fastapi.tiangolo.com/tutorial/security/
- JWT Best Practices: https://tools.ietf.org/html/rfc8725

---

**Questions?** Contact security@agentic-brain.dev
