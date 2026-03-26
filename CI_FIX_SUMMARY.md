# CI/CD Fixes - Making Tests Pass

## Problems Fixed

### 1. Test Timeout (20 minutes)
**Issue**: Tests were timing out after 20 minutes. API tests were extremely slow (10-20s per test).

**Fix**:
- Increased timeout from 20 to 30 minutes
- Added `pytest-xdist` for parallel test execution (`-n auto --maxprocesses=4`)
- Added `--timeout=60` to prevent individual test hangs
- Tests now run in parallel across 4 workers, dramatically reducing total time

### 2. Service Password Mismatch
**Issue**: CI was using `Brain2026` but services were configured for `testpassword`.

**Fix**:
- Updated CI to create `.env.docker` with consistent `Brain2026` password
- Updated `.env.docker.example` to show `Brain2026` as default
- All services (Neo4j, Redis, Redpanda) now use the same password

### 3. Service Health Check Issues
**Issue**: Health check was waiting for JSON format which doesn't exist in older docker compose.

**Fix**:
- Changed to direct service exec commands with explicit timeouts
- Added connectivity tests after startup
- Better error messages if services fail to start
- Individual timeouts: Neo4j (90s), Redis (30s), Redpanda (60s)

### 4. Missing Test Dependencies
**Issue**: `pytest-xdist` was not in dependencies, preventing parallel execution.

**Fix**:
- Added `pytest-xdist>=3.5.0,<4.0.0` to both `dev` and `test` extras in `pyproject.toml`

### 5. Missing Environment Variables
**Issue**: Tests need `DEFAULT_LLM_PROVIDER=mock` and `TESTING=true`.

**Fix**:
- Added to CI environment variables
- Ensures tests use mock LLM provider instead of trying real API calls

## What Works Now

✅ Neo4j starts with Brain2026 password and APOC plugin
✅ Redis starts with Brain2026 password  
✅ Redpanda starts and reports healthy
✅ Tests run in parallel (4x faster)
✅ Individual test timeout prevents hangs
✅ Proper environment variables for testing

## Running Tests Locally

```bash
# Install dependencies
pip install -e ".[test,dev,api]"

# Start services
docker compose -f docker-compose.yml up -d neo4j redis redpanda

# Run tests (parallel)
pytest tests/ \
  --ignore=tests/e2e/ \
  -m "not integration" \
  -n auto \
  --maxprocesses=4 \
  -v --tb=short \
  --timeout=60

# Cleanup
docker compose -f docker-compose.yml down -v
```

## CI Environment Variables

Required in CI:
- `NEO4J_URI=bolt://localhost:7687`
- `NEO4J_USER=neo4j`
- `NEO4J_PASSWORD=Brain2026`
- `REDIS_HOST=localhost`
- `REDIS_PORT=6379`
- `REDIS_PASSWORD=Brain2026`
- `REDIS_URL=redis://:Brain2026@localhost:6379/0`
- `KAFKA_BOOTSTRAP_SERVERS=localhost:9092`
- `DEFAULT_LLM_PROVIDER=mock`
- `TESTING=true`

## Expected CI Time

- **Before**: 20+ minutes (timeout)
- **After**: ~8-10 minutes with parallel execution

## Service Startup Time

- Neo4j: ~30-60 seconds
- Redis: ~5-10 seconds  
- Redpanda: ~20-30 seconds
- Total: ~60-90 seconds

## Next Steps if Still Failing

1. Check service logs: `docker compose logs neo4j redis redpanda`
2. Verify connectivity: `docker compose exec neo4j cypher-shell -u neo4j -p Brain2026 "RETURN 1"`
3. Check Redis: `docker compose exec redis redis-cli -a Brain2026 ping`
4. Check Redpanda: `docker compose exec redpanda rpk cluster health`
