# ===================================
# Coolify Projects MCP Server - Dockerfile
# ===================================
# Multi-stage build for optimized image size
# Production-ready with security best practices
# ===================================

# Stage 1: Build stage
FROM python:3.12-alpine AS builder

# Install build dependencies
RUN apk add --no-cache \
    gcc \
    musl-dev \
    libffi-dev \
    openssl-dev

# Create build directory
WORKDIR /build

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Production stage
FROM python:3.12-alpine AS production

# CRITICAL: Install wget for health checks + docker-cli for WP-CLI tools
RUN apk add --no-cache wget curl docker-cli

# Create non-root user for security and grant Docker socket access
# Docker group (GID 999) allows access to /var/run/docker.sock
RUN addgroup -g 1001 appgroup && \
    adduser -u 1001 -G appgroup -s /bin/sh -D appuser && \
    addgroup -g 999 docker 2>/dev/null || true && \
    adduser appuser docker 2>/dev/null || true

# Set working directory
WORKDIR /app

# Copy Python packages from builder
COPY --from=builder /root/.local /home/appuser/.local

# Copy application code
COPY --chown=appuser:appgroup . .

# Create data directories for API keys and logs with correct ownership
# This must be done before switching to non-root user
RUN mkdir -p /app/data /app/logs && \
    chown -R appuser:appgroup /app/data /app/logs && \
    chmod 755 /app/data /app/logs

# Make server.py executable
RUN chmod +x server.py

# Switch to non-root user
USER appuser

# Add local packages to PATH
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1

# CRITICAL: EXPOSE port for Coolify
EXPOSE 8000

# CRITICAL: Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8000/health || exit 1

# CRITICAL: Listen on 0.0.0.0 (not localhost!)
# Run server with streamable-http transport on port 8000
CMD ["python", "server.py", "--transport", "streamable-http", "--port", "8000", "--host", "0.0.0.0"]
