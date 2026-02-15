#!/bin/bash
# Stop SCALE API local development environment

echo "🛑 Stopping SCALE API services..."

docker-compose down

echo "✅ Services stopped. Checkpoints preserved in ./checkpoints/"
