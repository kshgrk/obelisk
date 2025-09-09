#!/bin/bash

# Start Obelisk with Simple Combined Container
echo "🚀 Starting Obelisk (Simple Combined)..."

# Create necessary directories
mkdir -p data logs

# Stop any existing containers
echo "🛑 Stopping existing containers..."
docker-compose -f docker-compose.simple.yml down

# Build and start the simple service
echo "🔨 Building and starting simple container..."
docker-compose -f docker-compose.simple.yml up --build -d

# Wait for service to be healthy
echo "⏳ Waiting for service to start..."
sleep 10

# Check service status
echo "📊 Service Status:"
docker-compose -f docker-compose.simple.yml ps

echo ""
echo "✅ Obelisk is running!"
echo "🌐 App: http://localhost:8000"
echo "📋 Health Check: http://localhost:8000/health"
echo ""
echo "📜 View logs with: docker-compose -f docker-compose.simple.yml logs -f"
echo "🛑 Stop with: docker-compose -f docker-compose.simple.yml down"
