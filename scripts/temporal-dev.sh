#!/bin/bash

# Obelisk Temporal Development Environment Manager
# Usage: ./scripts/temporal-dev.sh [start|stop|restart|status|logs]

set -e

COMPOSE_FILE="docker-compose.temporal.yml"
PROJECT_NAME="obelisk-temporal"

case "$1" in
    start)
        echo "🚀 Starting Temporal development environment..."
        docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" up -d
        echo "✅ Temporal services started!"
        echo "📊 Temporal Web UI: http://localhost:8080"
        echo "🔧 Temporal gRPC: localhost:7233"
        echo "💾 PostgreSQL: localhost:5432"
        ;;
    
    stop)
        echo "🛑 Stopping Temporal development environment..."
        docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" down
        echo "✅ Temporal services stopped!"
        ;;
    
    restart)
        echo "🔄 Restarting Temporal development environment..."
        docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" down
        docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" up -d
        echo "✅ Temporal services restarted!"
        ;;
    
    status)
        echo "📊 Temporal services status:"
        docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" ps
        ;;
    
    logs)
        echo "📋 Showing Temporal logs (press Ctrl+C to exit):"
        docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" logs -f
        ;;
    
    clean)
        echo "🧹 Cleaning up Temporal environment (this will remove data)..."
        docker-compose -f "$COMPOSE_FILE" -p "$PROJECT_NAME" down -v
        echo "✅ Temporal environment cleaned!"
        ;;
    
    *)
        echo "Obelisk Temporal Development Environment Manager"
        echo ""
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  start    - Start Temporal development environment"
        echo "  stop     - Stop Temporal development environment"
        echo "  restart  - Restart Temporal development environment"
        echo "  status   - Show status of Temporal services"
        echo "  logs     - Show logs from Temporal services"
        echo "  clean    - Stop and remove all Temporal data (destructive)"
        echo ""
        echo "URLs:"
        echo "  Temporal Web UI: http://localhost:8080"
        echo "  Temporal gRPC:   localhost:7233"
        echo "  PostgreSQL:      localhost:5432"
        ;;
esac 