#!/bin/bash

# ==============================================================================
# SCALE API - Chaos Engineering Experiments
# ==============================================================================
# Description:
#   Utility script to simulate infrastructure failures for reliability testing.
#   Uses Docker to inject faults into local or staging environments.
#
# Requirements:
#   - Docker & Docker Compose
#   - SCALE API containers must be running (`docker compose up -d`)
#
# Usage:
#   ./scripts/chaos_experiments.sh [command]
#
# Commands:
#   kill_redis        - Pauses the Redis container for 30s to test rate-limiter fail-open.
#   kill_api          - Kills an API container to test load balancing/recovery.
#   network_latency   - Injects 200ms of latency into the API container for 30s using tc.
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

print_header() {
    echo -e "\n========================================"
    echo -e "⚡️ CHAOS EXPERIMENT: $1"
    echo -e "========================================\n"
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        echo "Error: docker could not be found."
        exit 1
    fi
}

kill_redis() {
    print_header "Redis Outage Simulation"
    echo "1. Pausing the Redis container to simulate network partition/crash..."
    docker compose -f "$PROJECT_ROOT/docker-compose.yml" pause redis

    echo "2. Redis is down. Run 'k6 run tests/performance/load_test.js' within the next 30s to verify fail-open."
    echo "   Sleeping for 30 seconds..."
    sleep 30

    echo "3. Restoring Redis container..."
    docker compose -f "$PROJECT_ROOT/docker-compose.yml" unpause redis
    echo "✅ Redis restored."
}

kill_api() {
    print_header "API Pod Crash Simulation"
    echo "1. Killing the API container abruptly..."
    docker compose -f "$PROJECT_ROOT/docker-compose.yml" kill api

    echo "2. API is dead. docker-compose should automatically restart it (restart: unless-stopped)."
    echo "   Monitoring status for 15s..."
    for i in {1..15}; do
        sleep 1
        status=$(docker compose -f "$PROJECT_ROOT/docker-compose.yml" ps -q api | xargs docker inspect -f '{{.State.Status}}' 2>/dev/null || echo "dead")
        echo "   Status: $status"
        if [ "$status" == "running" ]; then
            echo "✅ API successfully recovered!"
            return
        fi
    done
    echo "❌ API failed to recover automatically."
}

network_latency() {
    print_header "Network Latency Injection (200ms)"

    API_CONTAINER=$(docker compose -f "$PROJECT_ROOT/docker-compose.yml" ps -q api)
    if [ -z "$API_CONTAINER" ]; then
        echo "Error: API container is not running."
        exit 1
    fi

    echo "1. Injecting 200ms latency into API container (requires NET_ADMIN capabilities)..."
    # Note: If this fails, the container needs --cap-add=NET_ADMIN in docker-compose
    docker exec "$API_CONTAINER" apt-get update -yqq && docker exec "$API_CONTAINER" apt-get install -yqq iproute2
    docker exec "$API_CONTAINER" tc qdisc add dev eth0 root netem delay 200ms

    echo "2. Latency injected. Test endpoints and verify Sentry captures timeouts if configured."
    echo "   Sleeping for 30 seconds..."
    sleep 30

    echo "3. Removing latency..."
    docker exec "$API_CONTAINER" tc qdisc del dev eth0 root netem delay 200ms || true
    echo "✅ Network restored to normal."
}

case "$1" in
    kill_redis)
        check_docker
        kill_redis
        ;;
    kill_api)
        check_docker
        kill_api
        ;;
    network_latency)
        check_docker
        network_latency
        ;;
    *)
        echo "Usage: $0 {kill_redis|kill_api|network_latency}"
        exit 1
        ;;
esac
