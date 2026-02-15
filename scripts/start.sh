#!/bin/bash
#
# SCALE App - Production-Ready Startup Script
# Initializes full development stack with Docker Compose, Redis, Celery, API, and Flower
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
readonly REQUIRED_PORTS=(8000 6379 5555)
readonly HEALTH_CHECK_RETRIES=30
readonly HEALTH_CHECK_INTERVAL=2

# Track PIDs for cleanup
FRONTEND_PID=""

# Logging functions
log_info() { echo -e "${BLUE}ℹ️  ${1}${NC}"; }
log_success() { echo -e "${GREEN}✅ ${1}${NC}"; }
log_warn() { echo -e "${YELLOW}⚠️  ${1}${NC}"; }
log_error() { echo -e "${RED}❌ ${1}${NC}"; }
log_step() { echo -e "${CYAN}🔹 ${1}${NC}"; }

# Cleanup function - runs on exit
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        log_error "Startup failed with exit code $exit_code"
        log_info "Running cleanup..."
        ./scripts/stop.sh 2>/dev/null || true
    fi
    exit $exit_code
}

# Set trap for cleanup
trap cleanup EXIT ERR INT TERM

# Check if running on macOS or Linux
check_platform() {
    local os
    os=$(uname -s)
    case "$os" in
        Linux*|Darwin*)
            log_info "Platform: $os"
            ;;
        *)
            log_error "Unsupported platform: $os"
            exit 1
            ;;
    esac
}

# Check if Docker is running
check_docker() {
    log_step "Checking Docker status..."
    if ! docker info >/dev/null 2>&1; then
        log_error "Docker is not running. Please start Docker Desktop first."
        
        # Try to start Docker Desktop on macOS
        if [[ "$OSTYPE" == "darwin"* ]]; then
            log_info "Attempting to start Docker Desktop..."
            open -a Docker
            
            # Wait for Docker to start
            local retries=30
            while [ $retries -gt 0 ]; do
                if docker info >/dev/null 2>&1; then
                    log_success "Docker started successfully"
                    return 0
                fi
                sleep 2
                retries=$((retries - 1))
            done
            
            log_error "Docker failed to start. Please start it manually."
            exit 1
        fi
        
        exit 1
    fi
    log_success "Docker is running"
}

# Check if docker-compose is available
check_docker_compose() {
    log_step "Checking docker-compose..."
    if command -v docker-compose &> /dev/null; then
        export COMPOSE_CMD="docker-compose"
    elif docker compose version &> /dev/null; then
        export COMPOSE_CMD="docker compose"
    else
        log_error "docker-compose not found. Please install it."
        exit 1
    fi
    log_success "Using: $COMPOSE_CMD"
}

# Check if required ports are available
check_ports() {
    log_step "Checking port availability..."
    local unavailable_ports=()
    
    for port in "${REQUIRED_PORTS[@]}"; do
        if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
            unavailable_ports+=($port)
        fi
    done
    
    if [ ${#unavailable_ports[@]} -gt 0 ]; then
        log_warn "Some ports are already in use: ${unavailable_ports[*]}"
        log_info "Attempting to free ports..."
        
        for port in "${unavailable_ports[@]}"; do
            local pids
            pids=$(lsof -ti:$port 2>/dev/null || true)
            if [ -n "$pids" ]; then
                log_info "Killing process on port $port (PIDs: $pids)"
                kill -9 $pids 2>/dev/null || true
                sleep 1
            fi
        done
        
        # Verify ports are now free
        for port in "${unavailable_ports[@]}"; do
            if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
                log_error "Port $port is still in use. Please free it manually."
                exit 1
            fi
        done
        
        log_success "Ports freed successfully"
    else
        log_success "All required ports are available"
    fi
}

# Check environment files
check_environment() {
    log_step "Checking environment configuration..."
    
    if [ ! -f ".env.local" ]; then
        if [ -f ".env.example" ]; then
            log_warn ".env.local not found, copying from .env.example"
            cp .env.example .env.local
            log_warn "Please edit .env.local with your credentials before running again."
            exit 1
        else
            log_error ".env.local and .env.example not found. Please create .env.local."
            exit 1
        fi
    fi
    
    # Source environment variables
    set -a
    source .env.local
    set +a
    
    # Check critical variables
    if [ -z "${SUPABASE_URL:-}" ] || [ -z "${SUPABASE_ANON_KEY:-}" ]; then
        log_warn "Supabase credentials not configured in .env.local"
        log_info "Some features may not work correctly."
    fi
    
    log_success "Environment configured"
}

# Create necessary directories
setup_directories() {
    log_step "Setting up directories..."
    mkdir -p checkpoints logs
    log_success "Directories created"
}

# Pull latest images
pull_images() {
    log_step "Pulling Docker images..."
    $COMPOSE_CMD -f $COMPOSE_FILE pull --quiet 2>/dev/null || log_warn "Some images couldn't be pulled, will build locally"
}

# Build services
build_services() {
    log_step "Building Docker images..."
    $COMPOSE_CMD -f $COMPOSE_FILE build --parallel
    log_success "Images built successfully"
}

# Start services
start_services() {
    log_step "Starting Docker services..."
    $COMPOSE_CMD -f $COMPOSE_FILE up -d --remove-orphans
    log_success "Services started"
}

# Wait for service health
wait_for_health() {
    local service=$1
    local url=$2
    local max_retries=${3:-$HEALTH_CHECK_RETRIES}
    
    log_step "Waiting for $service to be healthy..."
    
    local retries=0
    while [ $retries -lt $max_retries ]; do
        if curl -sf "$url" >/dev/null 2>&1; then
            log_success "$service is healthy"
            return 0
        fi
        
        retries=$((retries + 1))
        echo -n "."
        sleep $HEALTH_CHECK_INTERVAL
    done
    
    echo
    log_error "$service failed to become healthy after $max_retries attempts"
    return 1
}

# Wait for Redis
wait_for_redis() {
    log_step "Waiting for Redis..."
    local retries=0
    
    while [ $retries -lt $HEALTH_CHECK_RETRIES ]; do
        if $COMPOSE_CMD -f $COMPOSE_FILE exec -T redis redis-cli ping 2>/dev/null | grep -q "PONG"; then
            log_success "Redis is ready"
            return 0
        fi
        
        retries=$((retries + 1))
        echo -n "."
        sleep $HEALTH_CHECK_INTERVAL
    done
    
    echo
    log_error "Redis failed to start"
    return 1
}

# Check all services health
check_all_health() {
    log_step "Performing health checks..."
    
    # Wait for Redis first
    wait_for_redis
    
    # Wait for API
    wait_for_health "API" "http://localhost:8000/api/v1/health" 60
    
    # Wait for Flower (optional)
    if wait_for_health "Flower" "http://localhost:5555" 10; then
        log_success "Flower monitoring is available"
    else
        log_warn "Flower monitoring may not be fully ready yet"
    fi
    
    log_success "All critical services are healthy"
}

# Start frontend
start_frontend() {
    log_step "Starting frontend development server..."
    
    if ! command -v npm &> /dev/null; then
        log_error "npm not found. Please install Node.js."
        return 1
    fi
    
    cd apps/web
    
    # Install dependencies if needed
    if [ ! -d "node_modules" ]; then
        log_info "Installing frontend dependencies..."
        npm install
    fi
    
    # Start dev server in background
    npm run dev &
    FRONTEND_PID=$!
    
    # Wait for frontend to be ready
    local retries=0
    while [ $retries -lt 30 ]; do
        if curl -sf http://localhost:3000 >/dev/null 2>&1; then
            log_success "Frontend is ready on http://localhost:3000"
            cd ../..
            return 0
        fi
        
        retries=$((retries + 1))
        echo -n "."
        sleep 1
    done
    
    echo
    cd ../..
    log_warn "Frontend may still be starting..."
    return 0
}

# Display final status
show_status() {
    echo
    echo "═══════════════════════════════════════════════════════════"
    echo -e "${GREEN}           🎉 SCALE App is Fully Operational!${NC}"
    echo "═══════════════════════════════════════════════════════════"
    echo
    echo "Services:"
    echo "  🌐 Frontend:     http://localhost:3000"
    echo "  🔌 API:          http://localhost:8000"
    echo "  📚 API Docs:     http://localhost:8000/docs"
    echo "  🌸 Flower UI:    http://localhost:5555"
    echo "  📊 Health Check: http://localhost:8000/api/v1/health"
    echo
    echo "Commands:"
    echo "  View logs:     docker-compose logs -f"
    echo "  Stop all:      ./scripts/stop.sh"
    echo "  Restart:       ./scripts/stop.sh && ./scripts/start.sh"
    echo
    echo "═══════════════════════════════════════════════════════════"
    echo
}

# Wait for interrupt to keep script running
wait_for_interrupt() {
    echo -e "${YELLOW}Press Ctrl+C to stop all services${NC}"
    while true; do
        sleep 1
    done
}

# Main execution
main() {
    echo -e "${CYAN}"
    echo "╔════════════════════════════════════════════════════════╗"
    echo "║          SCALE App - Development Environment          ║"
    echo "╚════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    # Get project root
    cd "$(dirname "$0")/.."
    
    # Run all checks and startup steps
    check_platform
    check_docker
    check_docker_compose
    check_ports
    check_environment
    setup_directories
    pull_images
    build_services
    start_services
    check_all_health
    start_frontend
    show_status
    
    # Keep script running to manage frontend process
    if [ -n "$FRONTEND_PID" ]; then
        wait $FRONTEND_PID
    else
        wait_for_interrupt
    fi
}

# Run main
main "$@"
