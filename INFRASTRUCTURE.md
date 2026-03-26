# agentic-brain Infrastructure - Bulletproof Setup

This directory contains infrastructure reliability enhancements for agentic-brain:

- **Health Monitoring**: Continuous monitoring of Redis, Neo4j, and Redpanda
- **Auto-Restart**: Automatic recovery when services go down
- **Event Bridge**: Redis ↔ Redpanda for hybrid ephemeral/persistent architecture
- **Auto-Start Daemon**: Background process that keeps services alive
- **Mac Integration**: LaunchAgent for auto-start on boot

## Quick Start

### 1. Start Infrastructure Daemon

The daemon continuously monitors services and auto-restarts them if needed:

```bash
# Start daemon
./scripts/infra-daemon.sh start

# Check status
./scripts/infra-daemon.sh status

# View logs
./scripts/infra-daemon.sh logs

# Stop daemon
./scripts/infra-daemon.sh stop
```

### 2. Enable Mac Auto-Start on Boot

```bash
# Copy plist to LaunchAgents
cp scripts/com.agentic-brain.infra-daemon.plist ~/Library/LaunchAgents/

# Load the agent
launchctl load ~/Library/LaunchAgents/com.agentic-brain.infra-daemon.plist

# Verify it's running
launchctl list | grep agentic-brain

# To disable auto-start
launchctl unload ~/Library/LaunchAgents/com.agentic-brain.infra-daemon.plist
```

### 3. Use Docker Compose with Healthchecks

Updated `docker-compose.yml` includes:
- `restart: always` - Services auto-restart on failure
- Healthchecks for all services - Docker verifies liveness
- `depends_on: condition: service_healthy` - Proper startup order

```bash
# Start services with healthchecks
docker-compose up -d

# Check service health
docker-compose ps

# View healthcheck status
docker inspect agentic-brain-redis | grep -A 10 '"Health"'
```

## Architecture

### Health Monitor (`src/agentic_brain/infra/health_monitor.py`)

Continuously monitors three services:

```python
from agentic_brain.infra import HealthMonitor

monitor = HealthMonitor(
    redis_host="localhost",
    redis_port=6379,
    neo4j_uri="bolt://localhost:7687",
    redpanda_host="localhost",
    redpanda_port=9644,
    check_interval=30,  # Check every 30 seconds
    max_restart_attempts=5,
)

# Start background monitoring
await monitor.start_monitoring()

# Get health status
status = monitor.get_status_dict()
print(status)
# {
#   "redis": {"status": "healthy", "response_time_ms": 2.5, ...},
#   "neo4j": {"status": "healthy", "response_time_ms": 15.3, ...},
#   "redpanda": {"status": "healthy", "response_time_ms": 5.1, ...}
# }
```

**Features:**
- Response time monitoring
- Restart attempt tracking
- Event logging
- Auto-restart with cooldown
- Callback system for restart events

### Event Bridge (`src/agentic_brain/infra/event_bridge.py`)

Redis ↔ Redpanda bridge for hybrid storage:

```python
from agentic_brain.infra import RedisRedpandaBridge

bridge = RedisRedpandaBridge(
    redis_host="localhost",
    redis_port=6379,
    redpanda_brokers="localhost:9092",
)

await bridge.start()

# Register callback for events
async def handle_llm_request(event):
    print(f"LLM Request: {event.payload}")

bridge.register_event_callback("brain.llm.request", handle_llm_request)
```

**Architecture:**
- **Redis**: Fast, ephemeral pub/sub for real-time chat
- **Redpanda**: Durable event log for persistent storage
- **Bridge**: Forward critical messages from Redis to Redpanda
- **Replay**: Restore state from Redpanda on restart

### Auto-Start Daemon (`scripts/infra-daemon.sh`)

Background process that:
- Checks service health every 30 seconds
- Auto-restarts failed services
- Logs all events to `logs/infra.log`
- Can be managed by systemd or launchd

```bash
# Commands
./scripts/infra-daemon.sh start    # Start daemon
./scripts/infra-daemon.sh stop     # Stop daemon
./scripts/infra-daemon.sh restart  # Restart daemon
./scripts/infra-daemon.sh status   # Show status
./scripts/infra-daemon.sh logs     # Tail logs
```

## Health Check Endpoints

The health monitor exposes service status through APIs:

### Docker Healthchecks

Each service includes a healthcheck:

```bash
# Redis healthcheck
docker exec agentic-brain-redis redis-cli ping

# Neo4j healthcheck
curl http://localhost:7474/

# Redpanda healthcheck
curl http://localhost:9644/v1/status/ready

# API healthcheck
curl http://localhost:8000/health
```

### Python API

```python
from agentic_brain.infra import HealthMonitor

monitor = HealthMonitor()
await monitor.initialize()

# Check all services
await monitor.check_all()

# Get status
status = monitor.get_status_dict()

# Check properties
print(f"All healthy: {monitor.all_healthy}")
print(f"Any unhealthy: {monitor.any_unhealthy}")
```

## Restart Behavior

### Automatic Restart Conditions

A service is restarted if:
1. Health check fails twice consecutively
2. Max restart attempts not exceeded
3. Cooldown period has passed since last restart

### Restart Limits

- **Max attempts**: 5 (configurable)
- **Cooldown**: 60 seconds between attempts
- **Failure logs**: All failures logged to `logs/infra.log`

### Manual Restart

```bash
# Restart specific service via Docker
docker restart agentic-brain-redis
docker restart agentic-brain-neo4j
docker restart agentic-brain-redpanda

# Restart all via Docker Compose
docker-compose restart
```

## Testing

Run infrastructure tests:

```bash
# All tests
pytest tests/test_infrastructure.py -v

# Specific test class
pytest tests/test_infrastructure.py::TestHealthMonitor -v

# With Docker integration tests
pytest tests/test_infrastructure.py -v -m docker

# With coverage
pytest tests/test_infrastructure.py --cov=agentic_brain.infra
```

## Configuration

### Environment Variables

```bash
# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=brain_secure_2024

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=changeme

# Redpanda
REDPANDA_BROKERS=localhost:9092
REDPANDA_ADMIN_PORT=9644

# Daemon
HEALTH_CHECK_INTERVAL=30
MAX_RESTART_ATTEMPTS=5
```

### Docker Compose

Edit `docker-compose.yml` to customize:

```yaml
services:
  redis:
    restart: always  # Always restart on failure
    healthcheck:     # Monitor health
      interval: 10s
      
  neo4j:
    restart: always
    healthcheck:
      interval: 10s
      
  redpanda:
    restart: always
    healthcheck:
      interval: 10s
```

## Monitoring and Logs

### Daemon Logs

```bash
# View daemon logs
tail -f logs/infra.log

# Follow in real-time
./scripts/infra-daemon.sh logs

# Check daemon status
./scripts/infra-daemon.sh status
```

### Docker Logs

```bash
# Service logs
docker-compose logs redis
docker-compose logs neo4j
docker-compose logs redpanda

# Follow in real-time
docker-compose logs -f
```

### Healthcheck Status

```bash
# Check healthcheck results
docker inspect agentic-brain-redis | grep -A 20 '"Health"'

# All services health
docker-compose ps
```

## Troubleshooting

### Service Won't Start

```bash
# Check Docker daemon
docker ps

# Check logs
docker-compose logs <service>

# Check port availability
lsof -i :6379   # Redis
lsof -i :7687   # Neo4j
lsof -i :9092   # Redpanda
```

### Daemon Not Running

```bash
# Check if daemon is running
./scripts/infra-daemon.sh status

# Check PID file
cat /tmp/agentic-brain-infra-daemon.pid

# Check logs
tail -f logs/infra.log

# Restart daemon
./scripts/infra-daemon.sh restart
```

### Healthchecks Failing

```bash
# Manual health checks
docker exec agentic-brain-redis redis-cli ping
curl http://localhost:7474/
curl http://localhost:9644/v1/status/ready

# Check container logs
docker-compose logs <service>

# Restart service
docker-compose restart <service>
```

## Best Practices

1. **Always use Docker Compose** for consistent configuration
2. **Enable the daemon** for 24/7 service availability
3. **Monitor logs** regularly for issues
4. **Set up alerts** for when services fail
5. **Test restarts** periodically
6. **Keep volumes** for data persistence
7. **Use proper passwords** (change `brain_secure_2024`!)
8. **Back up Neo4j data** regularly

## Advanced Usage

### Register Restart Callbacks

```python
monitor = HealthMonitor()

async def on_redis_restart(service_name):
    print(f"{service_name} was restarted - rebuilding cache")
    # Rebuild cache
    # Restore state
    # Notify users

monitor.register_restart_callback("redis", on_redis_restart)
```

### Event Bridge Callbacks

```python
bridge = RedisRedpandaBridge()

async def on_llm_event(event):
    print(f"LLM Event: {event.payload}")

bridge.register_event_callback("brain.llm.request", on_llm_event)
```

### Replay from Redpanda

```python
# Restore Redis state from Redpanda after restart
await bridge.replay_from_redpanda("redis_brain.llm.requests")
```

## Architecture Diagram

```
┌─────────────────────────────────────────────────┐
│         agentic-brain Infrastructure            │
└─────────────────────────────────────────────────┘

                    Infra Daemon
                   (background)
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼
    ┌─────┐         ┌───────┐     ┌──────────┐
    │Redis│         │ Neo4j │     │ Redpanda │
    └──┬──┘         └───┬───┘     └────┬─────┘
       │                │              │
       └────────────────┼──────────────┘
                        │
                 ┌──────▼──────┐
                 │   Bridge    │
                 │ (ephemeral) │
                 │  (durable)  │
                 └─────────────┘

Health Monitor checks every 30s
Auto-restarts failed services
Logs all events
```

## Related Files

- `src/agentic_brain/infra/health_monitor.py` - Health monitoring
- `src/agentic_brain/infra/event_bridge.py` - Redis ↔ Redpanda bridge
- `scripts/infra-daemon.sh` - Auto-start daemon
- `scripts/com.agentic-brain.infra-daemon.plist` - Mac LaunchAgent
- `docker-compose.yml` - Service configuration
- `tests/test_infrastructure.py` - Infrastructure tests

## Support

For issues or questions:
1. Check `logs/infra.log` for error messages
2. Run health checks manually
3. Review Docker Compose configuration
4. Check service logs: `docker-compose logs <service>`
5. Test with: `pytest tests/test_infrastructure.py -v`
