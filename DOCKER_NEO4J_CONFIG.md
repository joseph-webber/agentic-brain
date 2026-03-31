# Neo4j Docker Configuration - Agentic Brain

## Status: ✅ VERIFIED CORRECT

This document verifies that Neo4j Docker connection configuration is properly set up.

## Configuration Summary

### 1. docker-compose.yml - Agentic Brain Service

**Environment Variables (Lines 27-30):**
```yaml
# Neo4j connection
NEO4J_URI: bolt://neo4j:7687
NEO4J_USER: ${NEO4J_USER:-neo4j}
NEO4J_PASSWORD: ${NEO4J_PASSWORD:-Brain2026}
NEO4J_DATABASE: ${NEO4J_DATABASE:-neo4j}
```

**Service Dependencies (Lines 42-48):**
```yaml
depends_on:
  neo4j:
    condition: service_healthy
  redis:
    condition: service_healthy
  redpanda:
    condition: service_healthy
```

**Health Check (Lines 49-54):**
```yaml
healthcheck:
  test: ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:8000/health')\" || exit 1"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 60s
```

### 2. docker-compose.yml - Neo4j Service

**Port Configuration (Lines 72-73):**
```yaml
ports:
  - "${NEO4J_HTTP_PORT:-7474}:7474"  # Browser/HTTP
  - "${NEO4J_BOLT_PORT:-7687}:7687"  # Bolt protocol
```

**Authentication (Line 76):**
```yaml
NEO4J_AUTH: neo4j/${NEO4J_PASSWORD:-Brain2026}
```

### 3. Code-Level Configuration

**File: `src/agentic_brain/pooling/neo4j_pool.py` (Lines 99-103)**

The Neo4jPoolConfig reads environment variables at initialization:
```python
def __post_init__(self) -> None:
    """Load from environment variables if set."""
    self.uri = os.environ.get("NEO4J_URI", self.uri)
    self.user = os.environ.get("NEO4J_USER", self.user)
    self.password = os.environ.get("NEO4J_PASSWORD", self.password)
```

**File: `src/agentic_brain/neo4j/brain_graph.py` (Lines 23-26)**

The brain graph driver initialization:
```python
def get_driver():
    """Get or create Neo4j driver."""
    global _driver
    if _driver is None:
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD", "Brain2026")
        _driver = GraphDatabase.driver(uri, auth=(user, password))
    return _driver
```

### 4. Environment Files

**File: `.env.docker` (Lines 16-19)**
```env
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=Brain2026
NEO4J_DATABASE=neo4j
```

**File: `.env` (Local - Lines 5-7)**
```env
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=Brain2026
```

## Verification Checklist

- [x] **NEO4J_URI** configured to `bolt://neo4j:7687` in docker-compose.yml
- [x] **NEO4J_USER** configured with fallback to `neo4j`
- [x] **NEO4J_PASSWORD** configured with fallback to `Brain2026`
- [x] **agentic-brain** service has `depends_on` neo4j with `service_healthy` condition
- [x] **neo4j** service has healthcheck configured
- [x] **Bolt port 7687** exposed on neo4j container
- [x] **Code** reads NEO4J_URI from environment variables
- [x] **Code** reads NEO4J_USER from environment variables
- [x] **Code** reads NEO4J_PASSWORD from environment variables
- [x] **.env.docker** has all required variables
- [x] **.env** local configuration correct

## Docker Compose Startup Order

When running `docker compose up -d`:

1. **neo4j** starts first
2. **Redis** starts first  
3. **Redpanda** starts first
4. **agentic-brain** waits for all three services to report healthy
5. Once all dependencies are healthy, **agentic-brain** starts

## Connection Flow

```
agentic-brain container
    ↓
  Reads environment variables:
    - NEO4J_URI=bolt://neo4j:7687
    - NEO4J_USER=neo4j
    - NEO4J_PASSWORD=Brain2026
    ↓
  Initializes Neo4jPoolConfig (pooling/neo4j_pool.py)
    ↓
  Creates GraphDatabase driver (neo4j/brain_graph.py)
    ↓
  Connects to neo4j service on internal Docker network
    ↓
  neo4j service on bolt://0.0.0.0:7687
```

## Testing Neo4j Connection

### From outside Docker:
```bash
# Connect to localhost:7687
neo4j-cli cypher -u neo4j -p Brain2026 --uri bolt://localhost:7687
```

### From inside Docker:
```bash
docker exec agentic-brain python -c "
from agentic_brain.neo4j import get_driver
driver = get_driver()
print('Connected:', driver)
"
```

### Health Check:
```bash
# Check neo4j health
docker exec agentic-brain-neo4j wget --no-verbose --tries=1 --spider http://localhost:7474

# Check agentic-brain health
curl http://localhost:8000/health
```

## Network Configuration

- **Network Name**: `agentic-brain-network`
- **Driver**: `bridge`
- **Internal DNS**: Docker DNS allows container-to-container communication by service name
- **agentic-brain** can reach neo4j at: `neo4j:7687`

## Volume Configuration

- **neo4j_data**: Persistent Neo4j data storage
- **neo4j_logs**: Neo4j logs
- **neo4j_plugins**: APOC and GDS plugins

## Troubleshooting

If Neo4j connection fails:

1. **Check Neo4j is running:**
   ```bash
   docker ps | grep agentic-brain-neo4j
   ```

2. **Check Neo4j logs:**
   ```bash
   docker logs agentic-brain-neo4j
   ```

3. **Check agentic-brain logs:**
   ```bash
   docker logs agentic-brain
   ```

4. **Verify environment variables:**
   ```bash
   docker exec agentic-brain env | grep NEO4J
   ```

5. **Test Bolt connection:**
   ```bash
   docker exec agentic-brain python -c "
   from neo4j import GraphDatabase
   driver = GraphDatabase.driver('bolt://neo4j:7687', auth=('neo4j', 'Brain2026'))
   with driver.session() as session:
       result = session.run('RETURN 1')
       print(result.single())
   "
   ```

## Related Files

- `docker-compose.yml` - Container orchestration
- `Dockerfile` - App image build
- `Dockerfile.neo4j` - Neo4j image build with plugins
- `src/agentic_brain/pooling/neo4j_pool.py` - Connection pool implementation
- `src/agentic_brain/neo4j/brain_graph.py` - Driver initialization
- `.env.docker` - Docker environment configuration
- `.env` - Local development environment

## Last Verified

- Date: 2026-03-26
- Configuration Status: ✅ Correct
- All dependencies: ✅ Properly configured
- Environment variables: ✅ Matching between docker-compose.yml and code
