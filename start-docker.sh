#!/bin/bash

# Obelisk Docker Startup Script
echo "🚀 Starting Obelisk with Docker..."

# Create necessary directories
mkdir -p data logs

# Stop any existing containers
echo "🛑 Stopping existing containers..."
docker-compose down

# Build and start services
echo "🔨 Building and starting services..."
docker-compose up --build -d

# Wait for services to be healthy
echo "⏳ Waiting for services to start..."
sleep 10

# Check service status
echo "📊 Service Status:"
docker-compose ps

echo ""
echo "✅ Obelisk is running!"
echo "📱 Frontend: http://localhost:3000"
echo "🔧 Backend API: http://localhost:8001"
echo "📋 Health Check: http://localhost:8001/health"
echo "🕐 Temporal UI: http://localhost:8080"
echo ""
echo "📜 View logs with: docker-compose logs -f"
echo "🛑 Stop with: docker-compose down"
