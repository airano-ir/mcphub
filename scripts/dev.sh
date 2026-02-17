#!/bin/bash

# ============================================
# MCP Hub - Development Server
# ============================================

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}════════════════════════════════════${NC}"
echo -e "${BLUE}  MCP Hub - Dev Server${NC}"
echo -e "${BLUE}════════════════════════════════════${NC}"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}⚠ Virtual environment not found${NC}"
    echo "Run: ./scripts/setup.sh"
    exit 1
fi

# Activate virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${BLUE}ℹ Activating virtual environment...${NC}"
    source venv/bin/activate
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠ .env file not found${NC}"
    if [ -f ".env.example" ]; then
        echo -e "${BLUE}ℹ Creating .env from .env.example...${NC}"
        cp .env.example .env
        echo -e "${YELLOW}⚠ Please edit .env with your credentials${NC}"
        echo "  nano .env"
        exit 1
    else
        echo -e "${RED}✗ .env.example not found${NC}"
        exit 1
    fi
fi

# Create logs directory if it doesn't exist
mkdir -p logs

# Start development server
echo -e "${GREEN}✓ Starting development server...${NC}"
echo ""
echo -e "${BLUE}Press Ctrl+C to stop${NC}"
echo ""

# Run with auto-reload if available
if command -v watchmedo &> /dev/null; then
    watchmedo auto-restart --directory=./src --pattern=*.py --recursive -- python src/main.py
else
    python src/main.py
fi
