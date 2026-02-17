#!/bin/bash

# ============================================
# MCP Hub - Deployment Script
# ============================================

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_header() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════${NC}"
    echo -e "${BLUE}  ${1}${NC}"
    echo -e "${BLUE}═══════════════════════════════════════${NC}"
    echo ""
}

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

# Parse arguments
DEPLOY_MODE=${1:-production}

print_header "MCP Hub Deployment"

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed"
    exit 1
fi

if ! docker compose version &> /dev/null; then
    print_error "Docker Compose is not available"
    exit 1
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    print_error ".env file not found"
    print_info "Please create .env file from .env.example:"
    echo "  cp .env.example .env"
    echo "  nano .env"
    exit 1
fi

case "$DEPLOY_MODE" in
    production|prod)
        print_info "Deploying in production mode..."

        # Run tests first
        print_info "Running tests..."
        if ./scripts/test.sh quick no > /dev/null 2>&1; then
            print_success "Tests passed"
        else
            print_error "Tests failed. Aborting deployment."
            exit 1
        fi

        # Build and deploy
        print_info "Building Docker images..."
        docker compose build --no-cache

        print_info "Starting containers..."
        docker compose up -d

        # Wait for health check
        print_info "Waiting for health check..."
        sleep 5

        if docker compose ps | grep -q "Up"; then
            print_success "Containers are running"

            # Show logs
            print_info "Recent logs:"
            docker compose logs --tail=20

            print_success "Deployment completed!"
            echo ""
            echo "Container status:"
            docker compose ps
            echo ""
            echo "To view logs: docker compose logs -f"
            echo "To stop: docker compose down"
        else
            print_error "Deployment failed. Checking logs..."
            docker compose logs --tail=50
            exit 1
        fi
        ;;

    development|dev)
        print_info "Starting development environment..."

        docker compose up --build
        ;;

    stop)
        print_info "Stopping containers..."
        docker compose down
        print_success "Containers stopped"
        ;;

    restart)
        print_info "Restarting containers..."
        docker compose restart
        print_success "Containers restarted"
        ;;

    logs)
        print_info "Showing logs..."
        docker compose logs -f
        ;;

    status)
        print_info "Container status:"
        docker compose ps
        echo ""
        docker compose exec mcp-server curl -s http://localhost:8000/health | python -m json.tool 2>/dev/null || echo "Health check failed"
        ;;

    clean)
        print_warning "This will remove all containers, images, and volumes"
        read -p "Are you sure? (yes/no): " -r
        if [ "$REPLY" = "yes" ]; then
            docker compose down -v --rmi all
            print_success "Cleaned up successfully"
        else
            print_info "Cancelled"
        fi
        ;;

    *)
        print_error "Unknown deployment mode: $DEPLOY_MODE"
        echo ""
        echo "Usage: ./scripts/deploy.sh [MODE]"
        echo ""
        echo "Modes:"
        echo "  production|prod   - Deploy in production mode (default)"
        echo "  development|dev   - Start development environment"
        echo "  stop              - Stop running containers"
        echo "  restart           - Restart containers"
        echo "  logs              - View container logs"
        echo "  status            - Show container status and health"
        echo "  clean             - Remove all containers and images"
        echo ""
        echo "Examples:"
        echo "  ./scripts/deploy.sh"
        echo "  ./scripts/deploy.sh dev"
        echo "  ./scripts/deploy.sh stop"
        echo "  ./scripts/deploy.sh logs"
        exit 1
        ;;
esac
