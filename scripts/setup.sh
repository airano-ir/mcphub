#!/bin/bash

# ============================================
# MCP Hub - Setup Script (Linux/Mac)
# ============================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
print_info() {
    echo -e "${BLUE}ℹ ${1}${NC}"
}

print_success() {
    echo -e "${GREEN}✓ ${1}${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ ${1}${NC}"
}

print_error() {
    echo -e "${RED}✗ ${1}${NC}"
}

print_header() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════${NC}"
    echo -e "${BLUE}  ${1}${NC}"
    echo -e "${BLUE}═══════════════════════════════════════${NC}"
    echo ""
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Main setup
main() {
    print_header "MCP Hub Setup"

    # 1. Check Python version
    print_info "Checking Python version..."
    if ! command_exists python3; then
        print_error "Python 3 is not installed. Please install Python 3.11 or higher."
        exit 1
    fi

    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)

    if [ "$PYTHON_MAJOR" -lt 3 ] || { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 11 ]; }; then
        print_error "Python 3.11+ is required. Found: $PYTHON_VERSION"
        exit 1
    fi

    print_success "Python $PYTHON_VERSION found"

    # 2. Check Docker
    print_info "Checking Docker..."
    if command_exists docker; then
        DOCKER_VERSION=$(docker --version | cut -d' ' -f3 | sed 's/,$//')
        print_success "Docker $DOCKER_VERSION found"
    else
        print_warning "Docker not found. Docker is optional but recommended for deployment."
    fi

    # 3. Check Docker Compose
    print_info "Checking Docker Compose..."
    if command_exists docker && docker compose version >/dev/null 2>&1; then
        COMPOSE_VERSION=$(docker compose version --short)
        print_success "Docker Compose $COMPOSE_VERSION found"
    else
        print_warning "Docker Compose not found. Required for Docker deployment."
    fi

    # 4. Create virtual environment
    print_info "Creating virtual environment..."
    if [ -d "venv" ]; then
        print_warning "Virtual environment already exists. Skipping creation."
    else
        python3 -m venv venv
        print_success "Virtual environment created"
    fi

    # 5. Activate virtual environment
    print_info "Activating virtual environment..."
    source venv/bin/activate
    print_success "Virtual environment activated"

    # 6. Upgrade pip
    print_info "Upgrading pip..."
    pip install --upgrade pip >/dev/null 2>&1
    print_success "pip upgraded"

    # 7. Install dependencies
    print_info "Installing dependencies..."
    if [ -f "requirements.txt" ]; then
        pip install -r requirements.txt >/dev/null 2>&1
        print_success "Dependencies installed"
    else
        print_error "requirements.txt not found"
        exit 1
    fi

    # 8. Install development dependencies
    print_info "Installing development dependencies..."
    pip install pytest pytest-asyncio pytest-cov pytest-mock black ruff mypy >/dev/null 2>&1
    print_success "Development dependencies installed"

    # 9. Setup environment file
    print_info "Setting up environment file..."
    if [ -f ".env" ]; then
        print_warning ".env file already exists. Skipping creation."
        print_warning "Please ensure your .env file is properly configured."
    else
        if [ -f ".env.example" ]; then
            cp .env.example .env
            print_success ".env file created from .env.example"
            print_warning "Please edit .env file with your WordPress credentials."
        else
            print_error ".env.example not found"
            exit 1
        fi
    fi

    # 10. Create logs directory
    print_info "Creating logs directory..."
    mkdir -p logs
    print_success "Logs directory ready"

    # 11. Run tests (optional)
    print_info "Running tests..."
    if pytest --version >/dev/null 2>&1; then
        if pytest -q 2>&1 | tail -1 | grep -q "passed"; then
            print_success "All tests passed!"
        else
            print_warning "Some tests failed. Please check the output above."
        fi
    else
        print_warning "pytest not available. Skipping tests."
    fi

    # 12. Final instructions
    print_header "Setup Complete!"

    echo -e "${GREEN}✓ Setup completed successfully!${NC}"
    echo ""
    echo "Next steps:"
    echo ""
    echo "1. Edit the .env file with your credentials:"
    echo -e "   ${BLUE}nano .env${NC}"
    echo ""
    echo "2. Activate the virtual environment:"
    echo -e "   ${BLUE}source venv/bin/activate${NC}"
    echo ""
    echo "3. Run the MCP server:"
    echo -e "   ${BLUE}python src/main.py${NC}"
    echo ""
    echo "4. Or deploy with Docker:"
    echo -e "   ${BLUE}docker compose up -d${NC}"
    echo ""
    echo "5. Run tests:"
    echo -e "   ${BLUE}pytest --cov${NC}"
    echo ""
    echo "For more information, visit:"
    echo -e "${BLUE}https://github.com/airano-ir/mcphub${NC}"
    echo ""
}

# Run main function
main
