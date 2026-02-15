#!/bin/bash
# Start SCALE API with training infrastructure locally

set -e

echo "🚀 Starting SCALE API Local Development Environment..."

# Check if .env.local exists
if [ ! -f .env.local ]; then
    echo "❌ .env.local not found. Copy from .env.example and configure."
    exit 1
fi

# Create checkpoint directory
mkdir -p checkpoints

# Build and start services
echo "📦 Building Docker images..."
docker-compose build

echo "🟢 Starting services..."
docker-compose up -d

echo "⏳ Waiting for services to be healthy..."
sleep 10

# Check health
echo "🏥 Checking service health..."
if curl -s http://localhost:8000/api/v1/health > /dev/null; then
    echo "✅ API is healthy"
else
    echo "⚠️ API health check failed. Check logs: docker-compose logs api"
fi

echo ""
echo "🎉 SCALE API is running!"
echo "   API: http://localhost:8000"
echo "   Flower (Celery UI): http://localhost:5555"
echo "   Health: http://localhost:8000/api/v1/health"
echo ""
echo "Useful commands:"
echo "   View logs: docker-compose logs -f"
echo "   Stop: ./scripts/stop-local.sh"
