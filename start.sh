#!/bin/bash

# Obelisk Development Environment Starter
# Simple shell wrapper for the Python start script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/start.py"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 Obelisk Development Environment${NC}"
echo -e "${BLUE}=================================${NC}"

# Check if Python script exists
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo -e "${RED}❌ Error: start.py not found at $PYTHON_SCRIPT${NC}"
    exit 1
fi

# Check if we're in a virtual environment
if [[ "$VIRTUAL_ENV" != "" ]]; then
    echo -e "${GREEN}✅ Virtual environment detected: $VIRTUAL_ENV${NC}"
elif [[ "$CONDA_DEFAULT_ENV" != "" ]]; then
    echo -e "${GREEN}✅ Conda environment detected: $CONDA_DEFAULT_ENV${NC}"
else
    echo -e "${YELLOW}⚠️  No virtual environment detected${NC}"
    echo -e "${YELLOW}   It's recommended to run this in a virtual environment${NC}"
    echo -e "${YELLOW}   Dependencies will not be automatically installed${NC}"
    echo ""
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}👋 Setup cancelled${NC}"
        exit 0
    fi
fi

echo ""
echo -e "${BLUE}🔥 Starting all services...${NC}"
echo ""

# Run the Python script
if python3 "$PYTHON_SCRIPT" "$@"; then
    echo -e "${GREEN}✅ Services started successfully${NC}"
else
    echo -e "${RED}❌ Failed to start services${NC}"
    exit 1
fi
