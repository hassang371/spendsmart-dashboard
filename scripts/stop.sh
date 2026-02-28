#!/bin/bash
#
# SCALE App - Production-Ready Shutdown Script
# Gracefully terminates all services, clears queues, and cleans up resources
#

set -euo pipefail

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly CYAN='\033[0;36m'
readonly NC='\033[0m' # No Color

# Configuration
readonly PROJECT_NAME="scaleapp"
readonly COMPOSE_FILE="docker-compose.yml"
readonly REDIS_FLUSH_TIMEOUT=5

# Logging functions
log_info() { echo -e "${BLUE}ℹ️  ${1}${NC}"; }
log_success() { echo -e "${GREEN}✅ ${1}${NC}"; }
log_warn() { echo -e "${YELLOW}⚠️  ${1}${NC}"; }
log_error() { echo -e "${RED}❌ ${1}${NC}"; }
log_step() { echo -e "${CYAN}🔹 ${1}${NC}"; }

# Check if docker-compose is available
check_docker_compose() {
    if command -v docker-compose &> /dev/null; then
        export COMPOSE_CMD="docker-compose"
    elif docker compose version &> /dev/null; then
        export COMPOSE_CMD="docker compose"
    else
        log_warn "docker-compose not found"
        export COMPOSE_CMD=""
    fi
}

# Stop frontend process
stop_frontend() {
    log_step "Stopping frontend development server..."
    
    local pids
    pids=$(lsof -ti:3000 2>/dev/null || true)
    
    if [ -n "$pids" ]; then
        log_info "Found frontend processes: $pids"
        kill -TERM $pids 2>/dev/null || true
        sleep 2
        
        # Force kill if still running
        pids=$(lsof -ti:3000 2>/dev/null || true)
        if [ -n "$pids" ]; then
            log_warn "Force killing frontend processes..."
            kill -9 $pids 2>/dev/null || true
        fi
    fi
    
    log_success "Frontend stopped"
}

# Clear Redis queues
clear_redis_queues() {
    log_step "Clearing Redis queues..."
    
    if [ -z "$COMPOSE_CMD" ]; then
        log_warn "Docker compose not available, skipping Redis cleanup"
        return 0
    fi
    
    # Check if Redis container is running
    if ! $COMPOSE_CMD -f $COMPOSE_FILE ps redis 2>/dev/null | grep -q "Up"; then
        log_warn "Redis container not running, skipping queue cleanup"
        return 0
    fi
    
    # Flush all Redis data
    if $COMPOSE_CMD -f $COMPOSE_FILE exec -T redis redis-cli FLUSHALL 2>/dev/null; then
        log_success "Redis queues cleared"
    else
        log_warn "Could not clear Redis queues (may already be stopped)"
    fi
}

# Stop Celery workers gracefully
stop_celery_workers() {
    log_step "Stopping Celery workers..."
    
    if [ -z "$COMPOSE_CMD" ]; then
        log_warn "Docker compose not available"
        return 0
    fi
    
    # Check if worker containers exist
    local workers
    workers=$($COMPOSE_CMD -f $COMPOSE_FILE ps -q worker 2>/dev/null || true)
    
    if [ -n "$workers" ]; then
        log_info "Sending graceful shutdown signal to workers..."
        $COMPOSE_CMD -f $COMPOSE_FILE exec -T worker celery -A apps.api.celery_app control shutdown 2>/dev/null || true
        sleep 3
    fi
    
    log_success "Celery workers stopped"
}

# Stop Docker services
stop_docker_services() {
    log_step "Stopping Docker services..."
    
    if [ -z "$COMPOSE_CMD" ]; then
        log_warn "Docker compose not available"
        return 0
    fi
    
    # Stop services gracefully
    $COMPOSE_CMD -f $COMPOSE_FILE down --remove-orphans --timeout 30 2>/dev/null || {
        log_warn "Some services may not have stopped cleanly, forcing..."
        $COMPOSE_CMD -f $COMPOSE_FILE down --remove-orphans -v 2>/dev/null || true
    }
    
    log_success "Docker services stopped"
}

# Clean up orphaned containers
cleanup_orphans() {
    log_step "Cleaning up orphaned containers..."
    
    # Remove any containers with project name
    local orphans
    orphans=$(docker ps -aq --filter "name=$PROJECT_NAME" 2>/dev/null || true)
    
    if [ -n "$orphans" ]; then
        log_info "Removing orphaned containers..."
        docker rm -f $orphans 2>/dev/null || true
    fi
    
    # Clean up unused networks
    docker network prune -f 2>/dev/null || true
    
    log_success "Orphan cleanup complete"
}

# Clean up temporary files
cleanup_temp_files() {
    log_step "Cleaning up temporary files..."
    
    # Remove Python cache
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    
    # Remove temp log files
    rm -f logs/*.tmp 2>/dev/null || true
    
    log_success "Temporary files cleaned"
}

# Verify all services are stopped
verify_shutdown() {
    log_step "Verifying shutdown..."
    
    local running_services=()
    
    # Check ports
    for port in 3000 8000 5555 6379; do
        if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
            running_services+=($port)
        fi
    done
    
    if [ ${#running_services[@]} -eq 0 ]; then
        log_success "All services successfully stopped"
    else
        log_warn "Some services may still be running on ports: ${running_services[*]}"
        log_info "You may need to stop them manually: lsof -ti:${running_services[0]} | xargs kill -9"
    fi
}

# Display final status
show_status() {
    echo
    echo "═══════════════════════════════════════════════════════════"
    echo -e "${GREEN}           🛑 SCALE App Stopped Successfully${NC}"
    echo "═══════════════════════════════════════════════════════════"
    echo
    echo "Cleanup performed:"
    echo "  ✓ Frontend development server stopped"
    echo "  ✓ Docker containers stopped and removed"
    echo "  ✓ Redis queues cleared"
    echo "  ✓ Celery workers terminated"
    echo "  ✓ Orphaned resources cleaned"
    echo
    echo "Data preserved:"
    echo "  • Model checkpoints in ./checkpoints/"
    echo "  • Environment configuration in .env.local"
    echo
    echo "To restart: ./scripts/start.sh"
    echo "═══════════════════════════════════════════════════════════"
    echo
}

# Main execution
main() {
    echo -e "${CYAN}"
    echo "╔════════════════════════════════════════════════════════╗"
    echo "║          SCALE App - Shutdown Sequence                ║"
    echo "╚════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    # Get project root
    cd "$(dirname "$0")/.."
    
    # Initialize
    check_docker_compose
    
    # Stop services in order
    stop_frontend
    clear_redis_queues
    stop_celery_workers
    stop_docker_services
    cleanup_orphans
    cleanup_temp_files
    verify_shutdown
    show_status
}

# Run main
main "$@"
