#!/usr/bin/env bash
#
# Infrastructure Daemon - Keeps agentic-brain services always running
#
# Monitors and auto-restarts:
# - Redis
# - Neo4j
# - Redpanda (if configured)
#
# Usage:
#   ./infra-daemon.sh start    # Start daemon
#   ./infra-daemon.sh stop     # Stop daemon
#   ./infra-daemon.sh restart  # Restart daemon
#   ./infra-daemon.sh status   # Show status
#   ./infra-daemon.sh logs     # Show daemon logs
#
# For Mac auto-start on boot:
#   cp com.agentic-brain.infra-daemon.plist ~/Library/LaunchAgents/
#   launchctl load ~/Library/LaunchAgents/com.agentic-brain.infra-daemon.plist

set -e

# === Configuration ===
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_DIR="$SCRIPT_DIR"
DAEMON_LOG_DIR="$PROJECT_DIR/logs"
DAEMON_LOG="$DAEMON_LOG_DIR/infra.log"
DAEMON_PID_FILE="/tmp/agentic-brain-infra-daemon.pid"
HEALTH_CHECK_INTERVAL=30
MAX_RESTART_ATTEMPTS=5

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# === Helper Functions ===

log_info() {
    local msg="$1"
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} ℹ️  $msg" | tee -a "$DAEMON_LOG"
}

log_success() {
    local msg="$1"
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} ✓ $msg" | tee -a "$DAEMON_LOG"
}

log_error() {
    local msg="$1"
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} ✗ $msg" | tee -a "$DAEMON_LOG"
}

log_warn() {
    local msg="$1"
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} ⚠ $msg" | tee -a "$DAEMON_LOG"
}

# === Initialize ===

mkdir -p "$DAEMON_LOG_DIR"
echo "" >> "$DAEMON_LOG"
log_info "================================================="
log_info "agentic-brain Infrastructure Daemon"
log_info "================================================="

# === Service Checks ===

check_docker() {
    if ! docker ps > /dev/null 2>&1; then
        log_error "Docker daemon is not running"
        return 1
    fi
    return 0
}

check_redis() {
    local container_name="agentic-brain-redis"
    
    # Check if container exists and is running
    if docker ps --format "{{.Names}}" | grep -q "^${container_name}$"; then
        # Check health
        if docker exec "$container_name" redis-cli ping > /dev/null 2>&1; then
            log_success "Redis is running and healthy"
            return 0
        else
            log_error "Redis container is running but not responsive"
            return 1
        fi
    else
        log_warn "Redis container not running"
        return 1
    fi
}

check_neo4j() {
    local container_name="agentic-brain-neo4j"
    
    # Check if container exists and is running
    if docker ps --format "{{.Names}}" | grep -q "^${container_name}$"; then
        # Check health via HTTP
        if curl -s http://localhost:7474 > /dev/null 2>&1; then
            log_success "Neo4j is running and healthy"
            return 0
        else
            log_error "Neo4j container is running but not responsive"
            return 1
        fi
    else
        log_warn "Neo4j container not running"
        return 1
    fi
}

check_redpanda() {
    local container_name="agentic-brain-redpanda"
    
    # Check if container exists and is running (optional)
    if docker ps --format "{{.Names}}" | grep -q "^${container_name}$"; then
        # Check health via admin API
        if curl -s http://localhost:9644/v1/status/ready > /dev/null 2>&1; then
            log_success "Redpanda is running and healthy"
            return 0
        else
            log_error "Redpanda container is running but not responsive"
            return 1
        fi
    else
        log_info "Redpanda container not running (optional)"
        return 0  # Redpanda is optional
    fi
}

# === Service Restart ===

restart_redis() {
    local container_name="agentic-brain-redis"
    
    log_info "Restarting Redis..."
    
    if docker ps -a --format "{{.Names}}" | grep -q "^${container_name}$"; then
        docker restart "$container_name" >> "$DAEMON_LOG" 2>&1 || {
            log_error "Failed to restart Redis container"
            return 1
        }
        sleep 5
        
        if docker exec "$container_name" redis-cli ping > /dev/null 2>&1; then
            log_success "Redis restarted successfully"
            return 0
        else
            log_error "Redis restart failed - not responsive"
            return 1
        fi
    else
        log_error "Redis container does not exist"
        return 1
    fi
}

restart_neo4j() {
    local container_name="agentic-brain-neo4j"
    
    log_info "Restarting Neo4j..."
    
    if docker ps -a --format "{{.Names}}" | grep -q "^${container_name}$"; then
        docker restart "$container_name" >> "$DAEMON_LOG" 2>&1 || {
            log_error "Failed to restart Neo4j container"
            return 1
        }
        sleep 10  # Neo4j takes longer to start
        
        if curl -s http://localhost:7474 > /dev/null 2>&1; then
            log_success "Neo4j restarted successfully"
            return 0
        else
            log_error "Neo4j restart failed - not responsive"
            return 1
        fi
    else
        log_error "Neo4j container does not exist"
        return 1
    fi
}

restart_redpanda() {
    local container_name="agentic-brain-redpanda"
    
    log_info "Restarting Redpanda..."
    
    if docker ps -a --format "{{.Names}}" | grep -q "^${container_name}$"; then
        docker restart "$container_name" >> "$DAEMON_LOG" 2>&1 || {
            log_error "Failed to restart Redpanda container"
            return 1
        }
        sleep 5
        
        if curl -s http://localhost:9644/v1/status/ready > /dev/null 2>&1; then
            log_success "Redpanda restarted successfully"
            return 0
        else
            log_error "Redpanda restart failed - not responsive"
            return 1
        fi
    else
        log_info "Redpanda container does not exist (optional)"
        return 0
    fi
}

# === Main Daemon Loop ===

daemon_loop() {
    log_info "Starting infrastructure daemon loop (check interval: ${HEALTH_CHECK_INTERVAL}s)"
    
    local redis_failures=0
    local neo4j_failures=0
    local redpanda_failures=0
    
    while true; do
        log_info "Performing health checks..."
        
        # Check Docker
        if ! check_docker; then
            log_error "Docker daemon is not running - exiting"
            return 1
        fi
        
        # Check and restart Redis
        if ! check_redis; then
            redis_failures=$((redis_failures + 1))
            if [ $redis_failures -ge 2 ]; then
                log_warn "Redis failed $redis_failures times - attempting restart"
                if restart_redis; then
                    redis_failures=0
                fi
            fi
        else
            redis_failures=0
        fi
        
        # Check and restart Neo4j
        if ! check_neo4j; then
            neo4j_failures=$((neo4j_failures + 1))
            if [ $neo4j_failures -ge 2 ]; then
                log_warn "Neo4j failed $neo4j_failures times - attempting restart"
                if restart_neo4j; then
                    neo4j_failures=0
                fi
            fi
        else
            neo4j_failures=0
        fi
        
        # Check and restart Redpanda (optional)
        if ! check_redpanda; then
            redpanda_failures=$((redpanda_failures + 1))
            if [ $redpanda_failures -ge 2 ]; then
                log_warn "Redpanda failed $redpanda_failures times - attempting restart"
                if restart_redpanda; then
                    redpanda_failures=0
                fi
            fi
        else
            redpanda_failures=0
        fi
        
        # Sleep before next check
        sleep "$HEALTH_CHECK_INTERVAL"
    done
}

# === Commands ===

cmd_start() {
    log_info "Starting infrastructure daemon..."
    
    if [ -f "$DAEMON_PID_FILE" ]; then
        local pid=$(cat "$DAEMON_PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            log_warn "Daemon is already running (PID: $pid)"
            return 0
        fi
    fi
    
    # Start daemon in background
    daemon_loop &
    local pid=$!
    echo "$pid" > "$DAEMON_PID_FILE"
    
    log_success "Infrastructure daemon started (PID: $pid)"
    log_info "Logs: $DAEMON_LOG"
    log_info "To stop: $0 stop"
}

cmd_stop() {
    log_info "Stopping infrastructure daemon..."
    
    if [ ! -f "$DAEMON_PID_FILE" ]; then
        log_warn "Daemon is not running"
        return 0
    fi
    
    local pid=$(cat "$DAEMON_PID_FILE")
    if ! kill -0 "$pid" 2>/dev/null; then
        log_warn "Daemon process not found"
        rm -f "$DAEMON_PID_FILE"
        return 0
    fi
    
    kill "$pid"
    rm -f "$DAEMON_PID_FILE"
    
    log_success "Infrastructure daemon stopped"
}

cmd_restart() {
    cmd_stop
    sleep 1
    cmd_start
}

cmd_status() {
    echo ""
    echo -e "${BLUE}=== agentic-brain Infrastructure Status ===${NC}"
    echo ""
    
    if [ ! -f "$DAEMON_PID_FILE" ]; then
        echo -e "${RED}Daemon:${NC} Not running"
    else
        local pid=$(cat "$DAEMON_PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            echo -e "${GREEN}Daemon:${NC} Running (PID: $pid)"
        else
            echo -e "${RED}Daemon:${NC} Not running (stale PID file)"
        fi
    fi
    
    echo ""
    echo -e "${BLUE}Services:${NC}"
    
    if check_docker 2>/dev/null; then
        check_redis 2>/dev/null || echo -e "${RED}✗ Redis${NC}: Not running"
        check_neo4j 2>/dev/null || echo -e "${RED}✗ Neo4j${NC}: Not running"
        check_redpanda 2>/dev/null || echo -e "${RED}✗ Redpanda${NC}: Not running"
    else
        echo -e "${RED}✗ Docker${NC}: Not running"
    fi
    
    echo ""
    echo -e "${BLUE}Logs:${NC}"
    echo "  $DAEMON_LOG"
    echo ""
}

cmd_logs() {
    if [ ! -f "$DAEMON_LOG" ]; then
        echo "No logs yet"
        return 0
    fi
    
    tail -f "$DAEMON_LOG"
}

# === Main ===

case "${1:-status}" in
    start)
        cmd_start
        ;;
    stop)
        cmd_stop
        ;;
    restart)
        cmd_restart
        ;;
    status)
        cmd_status
        ;;
    logs)
        cmd_logs
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs}"
        echo ""
        echo "Commands:"
        echo "  start      Start infrastructure daemon"
        echo "  stop       Stop infrastructure daemon"
        echo "  restart    Restart infrastructure daemon"
        echo "  status     Show daemon and services status"
        echo "  logs       Show real-time daemon logs"
        exit 1
        ;;
esac
