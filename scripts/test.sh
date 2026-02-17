#!/bin/bash

# ============================================
# MCP Hub - Test Runner Script
# ============================================

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}════════════════════════════════════${NC}"
echo -e "${BLUE}  MCP Hub - Test Runner${NC}"
echo -e "${BLUE}════════════════════════════════════${NC}"
echo ""

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${YELLOW}⚠ Virtual environment not activated${NC}"
    echo "Activating..."
    source venv/bin/activate
fi

# Parse arguments
TEST_TYPE=${1:-all}
COVERAGE=${2:-yes}

case "$TEST_TYPE" in
    unit)
        echo -e "${BLUE}Running unit tests...${NC}"
        if [ "$COVERAGE" = "yes" ]; then
            pytest tests/test_*.py --cov=src --cov-report=term-missing --cov-report=html -v
        else
            pytest tests/test_*.py -v
        fi
        ;;

    integration)
        echo -e "${BLUE}Running integration tests...${NC}"
        if [ "$COVERAGE" = "yes" ]; then
            pytest tests/integration/ --cov=src --cov-report=term-missing -v
        else
            pytest tests/integration/ -v
        fi
        ;;

    security)
        echo -e "${BLUE}Running security tests...${NC}"
        pytest tests/test_security.py -v
        ;;

    quick)
        echo -e "${BLUE}Running quick tests (no coverage)...${NC}"
        pytest -x --ff
        ;;

    all)
        echo -e "${BLUE}Running all tests with coverage...${NC}"
        pytest --cov=src --cov-report=term-missing --cov-report=html -v
        ;;

    *)
        echo -e "${YELLOW}Unknown test type: $TEST_TYPE${NC}"
        echo ""
        echo "Usage: ./scripts/test.sh [TYPE] [COVERAGE]"
        echo ""
        echo "Types:"
        echo "  all          - Run all tests (default)"
        echo "  unit         - Run only unit tests"
        echo "  integration  - Run only integration tests"
        echo "  security     - Run only security tests"
        echo "  quick        - Quick test run (exit on first failure)"
        echo ""
        echo "Coverage (optional):"
        echo "  yes  - Generate coverage report (default)"
        echo "  no   - Skip coverage"
        echo ""
        echo "Examples:"
        echo "  ./scripts/test.sh"
        echo "  ./scripts/test.sh unit"
        echo "  ./scripts/test.sh all no"
        echo "  ./scripts/test.sh quick"
        exit 1
        ;;
esac

echo ""
if [ "$COVERAGE" = "yes" ]; then
    echo -e "${GREEN}✓ Coverage report saved to: htmlcov/index.html${NC}"
fi
echo -e "${GREEN}✓ Tests completed${NC}"
