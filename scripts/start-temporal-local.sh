#!/bin/bash

# Obelisk Local Temporal Development Environment
# Starts Temporal server and workers locally (no Docker)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
TEMPORAL_VERSION=${TEMPORAL_VERSION:-"1.24.2"}
TEMPORAL_DIR="$HOME/.temporal"
TEMPORAL_BIN="$TEMPORAL_DIR/temporal"
LOG_DIR="./logs"
PID_DIR="./pids"

# Create directories
mkdir -p "$LOG_DIR" "$PID_DIR"

echo -e "${BLUE}🚀 Obelisk Local Temporal Environment Manager${NC}"
echo -e "${BLUE}=================================================${NC}"

# Function to check if Temporal CLI is installed
check_temporal_cli() {
    if [ -f "$TEMPORAL_BIN" ]; then
        echo -e "${GREEN}✅ Temporal CLI found at $TEMPORAL_BIN${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠️  Temporal CLI not found, attempting to install...${NC}"
        return 1
    fi
}

# Function to install Temporal CLI
install_temporal_cli() {
    echo -e "${BLUE}📥 Installing Temporal CLI v${TEMPORAL_VERSION}...${NC}"
    
    # Create temporal directory
    mkdir -p "$TEMPORAL_DIR"
    
    # Detect OS and architecture
    OS=$(uname -s | tr '[:upper:]' '[:lower:]')
    ARCH=$(uname -m)
    
    if [ "$ARCH" = "x86_64" ]; then
        ARCH="amd64"
    elif [ "$ARCH" = "arm64" ] || [ "$ARCH" = "aarch64" ]; then
        ARCH="arm64"
    fi
    
    # Download URL
    DOWNLOAD_URL="https://github.com/temporalio/cli/releases/download/v${TEMPORAL_VERSION}/temporal_cli_${TEMPORAL_VERSION}_${OS}_${ARCH}.tar.gz"
    
    echo -e "${BLUE}📥 Downloading from: $DOWNLOAD_URL${NC}"
    
    # Download and extract
    curl -L "$DOWNLOAD_URL" | tar -xz -C "$TEMPORAL_DIR"
    
    if [ -f "$TEMPORAL_BIN" ]; then
        chmod +x "$TEMPORAL_BIN"
        echo -e "${GREEN}✅ Temporal CLI installed successfully${NC}"
    else
        echo -e "${RED}❌ Failed to install Temporal CLI${NC}"
        exit 1
    fi
}

# Function to start Temporal server
start_temporal_server() {
    echo -e "${BLUE}🔧 Starting Temporal development server...${NC}"
    
    # Check if server is already running
    if pgrep -f "temporal server start-dev" > /dev/null; then
        echo -e "${YELLOW}⚠️  Temporal server is already running${NC}"
        return 0
    fi
    
    # Start Temporal server in development mode
    nohup "$TEMPORAL_BIN" server start-dev \
        --namespace default \
        --port 7233 \
        --http-port 8233 \
        --metrics-port 8234 \
        --headless \
        > "$LOG_DIR/temporal-server.log" 2>&1 &
    
    TEMPORAL_PID=$!
    echo $TEMPORAL_PID > "$PID_DIR/temporal-server.pid"
    
    echo -e "${GREEN}✅ Temporal server started (PID: $TEMPORAL_PID)${NC}"
    echo -e "${BLUE}📊 Web UI will be available at: http://localhost:8233${NC}"
    echo -e "${BLUE}🔧 gRPC endpoint: localhost:7233${NC}"
    
    # Wait for server to be ready
    echo -e "${YELLOW}⏳ Waiting for Temporal server to be ready...${NC}"
    for i in {1..30}; do
        if curl -sf http://localhost:8233/api/v1/namespaces > /dev/null 2>&1; then
            echo -e "${GREEN}✅ Temporal server is ready!${NC}"
            return 0
        fi
        sleep 1
        echo -n "."
    done
    
    echo -e "\n${RED}❌ Temporal server failed to start or took too long${NC}"
    return 1
}

# Function to start chat worker
start_chat_worker() {
    echo -e "${BLUE}👷 Starting Obelisk Chat Worker...${NC}"
    
    # Check if worker is already running
    if pgrep -f "chat_worker.py" > /dev/null; then
        echo -e "${YELLOW}⚠️  Chat worker is already running${NC}"
        return 0
    fi
    
    # Start the chat worker
    nohup python -m src.temporal.workers.chat_worker \
        > "$LOG_DIR/chat-worker.log" 2>&1 &
    
    WORKER_PID=$!
    echo $WORKER_PID > "$PID_DIR/chat-worker.pid"
    
    echo -e "${GREEN}✅ Chat worker started (PID: $WORKER_PID)${NC}"
}

# Function to check status
check_status() {
    echo -e "${BLUE}📊 Service Status:${NC}"
    echo "===================="
    
    # Check Temporal server
    if pgrep -f "temporal server start-dev" > /dev/null; then
        echo -e "Temporal Server: ${GREEN}✅ Running${NC}"
        if curl -sf http://localhost:8233/api/v1/namespaces > /dev/null 2>&1; then
            echo -e "Temporal Web UI: ${GREEN}✅ Available at http://localhost:8233${NC}"
        else
            echo -e "Temporal Web UI: ${YELLOW}⚠️  Starting...${NC}"
        fi
    else
        echo -e "Temporal Server: ${RED}❌ Not running${NC}"
    fi
    
    # Check Chat worker
    if pgrep -f "chat_worker.py" > /dev/null; then
        echo -e "Chat Worker: ${GREEN}✅ Running${NC}"
    else
        echo -e "Chat Worker: ${RED}❌ Not running${NC}"
    fi
}

# Function to stop services
stop_services() {
    echo -e "${YELLOW}🛑 Stopping Temporal services...${NC}"
    
    # Stop chat worker
    if [ -f "$PID_DIR/chat-worker.pid" ]; then
        WORKER_PID=$(cat "$PID_DIR/chat-worker.pid")
        if kill "$WORKER_PID" 2>/dev/null; then
            echo -e "${GREEN}✅ Chat worker stopped${NC}"
        fi
        rm -f "$PID_DIR/chat-worker.pid"
    fi
    
    # Stop Temporal server
    if [ -f "$PID_DIR/temporal-server.pid" ]; then
        TEMPORAL_PID=$(cat "$PID_DIR/temporal-server.pid")
        if kill "$TEMPORAL_PID" 2>/dev/null; then
            echo -e "${GREEN}✅ Temporal server stopped${NC}"
        fi
        rm -f "$PID_DIR/temporal-server.pid"
    fi
    
    # Kill any remaining processes
    pkill -f "temporal server start-dev" || true
    pkill -f "chat_worker.py" || true
    
    echo -e "${GREEN}✅ All services stopped${NC}"
}

# Function to show logs
show_logs() {
    echo -e "${BLUE}📋 Service Logs:${NC}"
    echo "=================="
    
    if [ -f "$LOG_DIR/temporal-server.log" ]; then
        echo -e "\n${BLUE}--- Temporal Server Log ---${NC}"
        tail -n 20 "$LOG_DIR/temporal-server.log"
    fi
    
    if [ -f "$LOG_DIR/chat-worker.log" ]; then
        echo -e "\n${BLUE}--- Chat Worker Log ---${NC}"
        tail -n 20 "$LOG_DIR/chat-worker.log"
    fi
}

# Main script logic
case "$1" in
    start)
        echo -e "${BLUE}🚀 Starting Obelisk Temporal Environment...${NC}"
        
        # Check and install Temporal CLI if needed
        if ! check_temporal_cli; then
            install_temporal_cli
        fi
        
        # Start services
        start_temporal_server
        sleep 3  # Give server time to start
        start_chat_worker
        
        echo -e "\n${GREEN}🎉 Obelisk Temporal Environment is ready!${NC}"
        echo -e "${BLUE}📊 Web UI: http://localhost:8233${NC}"
        echo -e "${BLUE}🔧 gRPC: localhost:7233${NC}"
        echo -e "${BLUE}📝 Task Queue: obelisk-task-queue${NC}"
        ;;
    
    stop)
        stop_services
        ;;
    
    restart)
        echo -e "${BLUE}🔄 Restarting Obelisk Temporal Environment...${NC}"
        stop_services
        sleep 2
        "$0" start
        ;;
    
    status)
        check_status
        ;;
    
    logs)
        show_logs
        echo -e "\n${BLUE}💡 Use 'tail -f logs/*.log' to follow logs in real-time${NC}"
        ;;
    
    install)
        install_temporal_cli
        ;;
    
    *)
        echo "Obelisk Local Temporal Environment Manager"
        echo ""
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  start     - Start Temporal server and workers locally"
        echo "  stop      - Stop all services"
        echo "  restart   - Restart all services"
        echo "  status    - Show status of all services"
        echo "  logs      - Show recent logs from all services"
        echo "  install   - Install/reinstall Temporal CLI"
        echo ""
        echo "URLs:"
        echo "  Temporal Web UI: http://localhost:8233"
        echo "  Temporal gRPC:   localhost:7233"
        echo ""
        echo "Notes:"
        echo "  - This script runs Temporal locally without Docker"
        echo "  - Logs are stored in ./logs/"
        echo "  - PIDs are stored in ./pids/"
        ;;
esac 