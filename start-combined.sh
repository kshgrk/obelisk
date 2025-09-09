#!/bin/bash

# Start Obelisk with Combined Container
echo "🚀 Starting Obelisk (Combined Container)..."

# Create necessary directories
mkdir -p data logs

# Stop any existing containers
echo "🛑 Stopping existing containers..."
docker-compose -f docker-compose.combined.yml down

# Build and start the combined service
echo "🔨 Building and starting combined container..."
docker-compose -f docker-compose.combined.yml up --build -d

# Wait for service to be healthy
echo "⏳ Waiting for service to start..."
sleep 15

# Check service status
echo "📊 Service Status:"
docker-compose -f docker-compose.combined.yml ps

echo ""
echo "✅ Obelisk is running!"
echo "🌐 Combined App: http://localhost"
echo "📋 Health Check: http://localhost/health"
echo ""
echo "📜 View logs with: docker-compose -f docker-compose.combined.yml logs -f"
echo "🛑 Stop with: docker-compose -f docker-compose.combined.yml down"
