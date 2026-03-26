#!/bin/bash

###############################################################################
# Deploy Local - Docker Deployment Script for Agentic Brain
# 
# This script builds and deploys the Agentic Brain application with all
# required services (Neo4j, Redis) on a local Mac machine.
#
# Usage: ./scripts/deploy-local.sh [clean|stop|logs]
#   - No args: Build and start services
#   - clean: Stop and remove all services/volumes
#   - stop: Stop services without removing
#   - logs: Show live logs
###############################################################################

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_FILE="$PROJECT_ROOT/docker-compose.yml"
IMAGE_NAME="agentic-brain"
IMAGE_TAG="latest"
FULL_IMAGE="$IMAGE_NAME:$IMAGE_TAG"
CONTAINER_API="agentic-brain-api"
CONTAINER_NEO4J="agentic-brain-neo4j"
CONTAINER_REDIS="agentic-brain-redis"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

###############################################################################
# Helper Functions
###############################################################################

log_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

log_success() {
    echo -e "${GREEN}✓${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

log_error() {
    echo -e "${RED}✗${NC} $1"
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed or not in PATH"
        exit 1
    fi
    log_success "Docker is available"
}

check_docker_compose() {
    if ! command -v docker-compose &> /dev/null; then
        log_error "docker-compose is not installed or not in PATH"
        exit 1
    fi
    log_success "docker-compose is available"
}

check_compose_file() {
    if [ ! -f "$COMPOSE_FILE" ]; then
        log_error "docker-compose.yml not found at $COMPOSE_FILE"
        exit 1
    fi
    log_success "docker-compose.yml found"
}

build_image() {
    log_info "Building Docker image: $FULL_IMAGE"
    cd "$PROJECT_ROOT"
    
    if docker build -t "$FULL_IMAGE" .; then
        log_success "Docker image built successfully"
    else
        log_error "Failed to build Docker image"
        exit 1
    fi
}

verify_image() {
    log_info "Verifying image works..."
    
    # Try to run a simple Python check
    if docker run --rm "$FULL_IMAGE" python -c "from agentic_brain import __version__; print(f'✓ agentic-brain version available')" 2>&1; then
        log_success "Image verification passed"
        return 0
    else
        log_warning "Could not verify image version (may be normal if package not yet installed)"
        return 1
    fi
}

start_services() {
    log_info "Starting services via docker-compose..."
    cd "$PROJECT_ROOT"
    
    if docker-compose -f "$COMPOSE_FILE" up -d; then
        log_success "Services started"
    else
        log_error "Failed to start services"
        exit 1
    fi
}

wait_for_health_checks() {
    log_info "Waiting for health checks to pass..."
    
    local max_attempts=60
    local attempt=0
    local all_healthy=false
    
    while [ $attempt -lt $max_attempts ]; do
        attempt=$((attempt + 1))
        
        # Check Neo4j
        local neo4j_status=$(docker inspect --format='{{.State.Health.Status}}' "$CONTAINER_NEO4J" 2>/dev/null || echo "unknown")
        
        # Check Redis
        local redis_status=$(docker inspect --format='{{.State.Health.Status}}' "$CONTAINER_REDIS" 2>/dev/null || echo "unknown")
        
        # Check API
        local api_status=$(docker inspect --format='{{.State.Health.Status}}' "$CONTAINER_API" 2>/dev/null || echo "unknown")
        
        log_info "Health check attempt $attempt/$max_attempts - Neo4j: $neo4j_status, Redis: $redis_status, API: $api_status"
        
        if [ "$neo4j_status" = "healthy" ] && [ "$redis_status" = "healthy" ] && [ "$api_status" = "healthy" ]; then
            all_healthy=true
            break
        fi
        
        sleep 2
    done
    
    if [ "$all_healthy" = true ]; then
        log_success "All services are healthy!"
        return 0
    else
        log_warning "Services did not reach healthy state in time"
        log_info "Showing container status:"
        docker-compose -f "$COMPOSE_FILE" ps
        log_info "Checking logs for errors..."
        docker-compose -f "$COMPOSE_FILE" logs --tail=20
        return 1
    fi
}

show_service_info() {
    log_info "Service Information:"
    echo ""
    
    # Get container IPs
    local api_ip=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$CONTAINER_API" 2>/dev/null || echo "unknown")
    local neo4j_ip=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$CONTAINER_NEO4J" 2>/dev/null || echo "unknown")
    local redis_ip=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' "$CONTAINER_REDIS" 2>/dev/null || echo "unknown")
    
    echo -e "${GREEN}Agentic Brain API:${NC}"
    echo "  Container: $CONTAINER_API"
    echo "  IP: $api_ip"
    echo "  URL: http://localhost:8000"
    echo "  Health: http://localhost:8000/health"
    echo ""
    
    echo -e "${GREEN}Neo4j:${NC}"
    echo "  Container: $CONTAINER_NEO4J"
    echo "  IP: $neo4j_ip"
    echo "  Browser: http://localhost:7474"
    echo "  Bolt: bolt://localhost:7687"
    echo "  Credentials: neo4j / (see .env or docker-compose.yml)"
    echo ""
    
    echo -e "${GREEN}Redis:${NC}"
    echo "  Container: $CONTAINER_REDIS"
    echo "  IP: $redis_ip"
    echo "  Host: localhost:6379"
    echo "  CLI: redis-cli -h localhost -p 6379"
    echo ""
}

stop_services() {
    log_info "Stopping services..."
    cd "$PROJECT_ROOT"
    
    if docker-compose -f "$COMPOSE_FILE" stop; then
        log_success "Services stopped"
    else
        log_warning "Failed to stop services (they may already be stopped)"
    fi
}

remove_services() {
    log_info "Removing containers and volumes..."
    cd "$PROJECT_ROOT"
    
    if docker-compose -f "$COMPOSE_FILE" down -v; then
        log_success "Containers and volumes removed"
    else
        log_error "Failed to remove containers and volumes"
        exit 1
    fi
}

show_logs() {
    log_info "Showing live logs (Ctrl+C to exit)..."
    cd "$PROJECT_ROOT"
    docker-compose -f "$COMPOSE_FILE" logs -f
}

###############################################################################
# Main Script
###############################################################################

main() {
    local command="${1:-deploy}"
    
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║     Agentic Brain - Local Docker Deployment Script        ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    
    case "$command" in
        deploy|"")
            log_info "Deployment mode: Build and start services"
            echo ""
            
            check_docker
            check_docker_compose
            check_compose_file
            echo ""
            
            build_image
            echo ""
            
            verify_image
            echo ""
            
            start_services
            echo ""
            
            wait_for_health_checks
            echo ""
            
            show_service_info
            echo ""
            
            log_success "Deployment complete!"
            ;;
            
        clean)
            log_info "Clean mode: Stop and remove all services/volumes"
            echo ""
            
            check_docker
            check_docker_compose
            check_compose_file
            echo ""
            
            remove_services
            echo ""
            
            log_success "Clean complete!"
            ;;
            
        stop)
            log_info "Stop mode: Stop services without removing"
            echo ""
            
            check_docker
            check_docker_compose
            check_compose_file
            echo ""
            
            stop_services
            echo ""
            
            log_success "Stop complete!"
            ;;
            
        logs)
            log_info "Logs mode: Show live logs"
            echo ""
            
            check_docker
            check_docker_compose
            check_compose_file
            echo ""
            
            show_logs
            ;;
            
        status)
            log_info "Status mode: Show service status"
            echo ""
            
            check_docker
            check_docker_compose
            check_compose_file
            echo ""
            
            cd "$PROJECT_ROOT"
            docker-compose -f "$COMPOSE_FILE" ps
            echo ""
            
            show_service_info
            ;;
            
        *)
            echo "Usage: $0 [command]"
            echo ""
            echo "Commands:"
            echo "  deploy   - Build and start services (default)"
            echo "  clean    - Stop and remove all services/volumes"
            echo "  stop     - Stop services without removing"
            echo "  logs     - Show live logs"
            echo "  status   - Show service status and info"
            echo ""
            exit 1
            ;;
    esac
}

main "$@"
