# Docker Setup for Agentic Brain

## Quick Start

```bash
# Build and start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Stop and remove volumes (clean slate)
docker-compose down -v
```

## Services

### Neo4j Database
- **Container**: agentic-brain-neo4j
- **Image**: neo4j:5-community with APOC plugin
- **Ports**: 
  - Bolt: 7687
  - HTTP: 7474
  - HTTPS: 7473
- **Credentials**: neo4j / AgenticBrainPassword123!
- **Volumes**:
  - `agentic_brain_neo4j_data`: Database files
  - `agentic_brain_neo4j_logs`: Log files
  - `agentic_brain_neo4j_import`: Import directory

### Agentic Brain API
- **Container**: agentic-brain-api
- **Port**: 8000
- **Environment**:
  - NEO4J_URI: bolt://neo4j:7687
  - NEO4J_USER: neo4j
  - NEO4J_PASSWORD: AgenticBrainPassword123!
  - OLLAMA_BASE_URL: http://host.docker.internal:11434 (for local Ollama)
- **Volumes**:
  - `./data`: Application data directory

## Configuration

### Neo4j Settings
Edit `docker-compose.yml` to customize:
- Memory allocation: `NEO4J_server_memory_heap_*`
- APOC plugins: `NEO4J_PLUGINS`
- Port mappings in `ports` section

### Agentic Brain Settings
- Modify `Dockerfile` to change the default command
- Override environment variables in `docker-compose.yml`
- Mount additional volumes as needed

## Database Access

### From Host Machine
```bash
# Using cypher-shell
docker exec -it agentic-brain-neo4j cypher-shell -u neo4j -p AgenticBrainPassword123!

# Using HTTP (Neo4j Browser)
# Open http://localhost:7474 in your browser
```

### From within Container
```bash
docker exec -it agentic-brain-api python -c "
from neo4j import GraphDatabase
driver = GraphDatabase.driver(
    'bolt://neo4j:7687',
    auth=('neo4j', 'AgenticBrainPassword123!')
)
with driver.session() as session:
    result = session.run('RETURN 1 as num')
    print(result.single())
driver.close()
"
```

## Health Checks

Neo4j includes a health check that verifies connectivity via cypher-shell. The API waits for Neo4j to be healthy before starting (`depends_on` with `service_healthy`).

Check status:
```bash
docker-compose ps
```

## Networking

- **Network**: `agentic-brain-network` (bridge)
- **Service Discovery**: Use service names (e.g., `neo4j:7687` for Neo4j)
- **Ollama Access**: `host.docker.internal:11434` for local Ollama on macOS/Windows

## Volumes

All Neo4j data is persisted in named volumes:
- `agentic_brain_neo4j_data`
- `agentic_brain_neo4j_logs`
- `agentic_brain_neo4j_import`

To inspect:
```bash
docker volume inspect agentic_brain_neo4j_data
```

## Troubleshooting

### Neo4j Won't Start
```bash
# Check logs
docker logs agentic-brain-neo4j

# Verify volume permissions
docker exec agentic-brain-neo4j ls -la /var/lib/neo4j/data
```

### API Connection Issues
```bash
# Test Neo4j connectivity from API container
docker exec agentic-brain-api python -c "
from neo4j import GraphDatabase
driver = GraphDatabase.driver(
    'bolt://neo4j:7687',
    auth=('neo4j', 'AgenticBrainPassword123!')
)
print('Connected to Neo4j:', driver.get_server_info())
driver.close()
"
```

### Clean Start
```bash
# Remove containers and volumes
docker-compose down -v

# Rebuild images
docker-compose build --no-cache

# Start fresh
docker-compose up -d
```

## Production Notes

For production deployments:
1. Change the default Neo4j password in `docker-compose.yml`
2. Use environment files (`.env`) for sensitive data
3. Configure resource limits in `docker-compose.yml`
4. Use persistent volumes or external storage
5. Set up proper monitoring and logging
6. Configure backup strategies for Neo4j data
