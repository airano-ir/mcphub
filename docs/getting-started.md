# 🚀 Getting Started with MCP Hub

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Running the Server](#running-the-server)
5. [Testing Your Setup](#testing-your-setup)
6. [Using MCP Tools](#using-mcp-tools)
7. [Docker Deployment](#docker-deployment)
8. [Coolify Deployment](#coolify-deployment)
9. [Next Steps](#next-steps)

---

## Prerequisites

Before you begin, ensure you have the following installed:

### Required

- **Python 3.11+**: [Download Python](https://www.python.org/downloads/)
- **Git**: [Download Git](https://git-scm.com/downloads)

### Optional (for Docker deployment)

- **Docker**: [Download Docker Desktop](https://www.docker.com/products/docker-desktop)
- **Docker Compose**: Included with Docker Desktop

### WordPress Requirements

For each WordPress site you want to manage:

- WordPress 5.0+
- **Application Passwords** enabled (WordPress 5.6+)
- **WooCommerce** 3.0+ (if using WooCommerce tools)
- **Rank Math** or **Yoast SEO** (if using SEO tools)
- HTTPS enabled (recommended)

---

## Installation

### Option 1: Automated Setup (Recommended)

#### Linux/Mac

```bash
# Clone the repository
git clone https://github.com/mcphub/mcphub.git
cd mcphub

# Run setup script
chmod +x scripts/setup.sh
./scripts/setup.sh
```

#### Windows (PowerShell)

```powershell
# Clone the repository
git clone https://github.com/mcphub/mcphub.git
cd mcphub

# Run setup script
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
.\scripts\setup.ps1
```

### Option 2: Manual Setup

```bash
# 1. Clone repository
git clone https://github.com/mcphub/mcphub.git
cd mcphub

# 2. Create virtual environment
python3 -m venv venv

# 3. Activate virtual environment
# Linux/Mac:
source venv/bin/activate
# Windows:
.\venv\Scripts\Activate.ps1

# 4. Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# 5. Copy environment template
cp .env.example .env
```

---

## Configuration

### Step 1: Generate WordPress Application Passwords

For each WordPress site:

1. Log in to WordPress admin
2. Navigate to: **Users → Your Profile**
3. Scroll to **Application Passwords** section
4. Enter name: `MCP Server`
5. Click **Add New Application Password**
6. Copy the generated password (format: `xxxx xxxx xxxx xxxx xxxx xxxx`)

**Important**: Save this password immediately. You cannot retrieve it later.

### Step 2: Generate WooCommerce API Keys

If using WooCommerce tools:

1. Go to: **WooCommerce → Settings → Advanced → REST API**
2. Click **Add Key**
3. Fill in:
   - **Description**: `MCP Server`
   - **User**: Select admin user
   - **Permissions**: `Read/Write`
4. Click **Generate API Key**
5. Copy **Consumer Key** and **Consumer Secret**

### Step 3: Configure Environment Variables

Edit `.env` file:

```bash
# Basic Configuration
MCP_SERVER_NAME=mcphub
MCP_SERVER_VERSION=1.0.0

# Site 1 - Main WordPress Site
WORDPRESS_SITE1_URL=https://example.com
WORDPRESS_SITE1_USERNAME=admin
WORDPRESS_SITE1_APP_PASSWORD=xxxx xxxx xxxx xxxx xxxx xxxx
WORDPRESS_SITE1_WC_CONSUMER_KEY=ck_xxxxxxxxxxxxx
WORDPRESS_SITE1_WC_CONSUMER_SECRET=cs_xxxxxxxxxxxxx
WORDPRESS_SITE1_ALIAS=mainsite

# Site 2 - E-commerce Site (Optional)
WORDPRESS_SITE2_URL=https://shop.example.com
WORDPRESS_SITE2_USERNAME=admin
WORDPRESS_SITE2_APP_PASSWORD=yyyy yyyy yyyy yyyy yyyy yyyy
WORDPRESS_SITE2_WC_CONSUMER_KEY=ck_yyyyyyyyyyyyy
WORDPRESS_SITE2_WC_CONSUMER_SECRET=cs_yyyyyyyyyyyyy
WORDPRESS_SITE2_ALIAS=shop

# Site 3 - Blog Site (Optional)
WORDPRESS_SITE3_URL=https://blog.example.com
WORDPRESS_SITE3_USERNAME=admin
WORDPRESS_SITE3_APP_PASSWORD=zzzz zzzz zzzz zzzz zzzz zzzz
WORDPRESS_SITE3_ALIAS=blog

# Rate Limiting (Optional)
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_PER_HOUR=1000
RATE_LIMIT_PER_DAY=10000

# Logging (Optional)
LOG_LEVEL=INFO
```

### Configuration Tips

- **Site Aliases**: Use friendly names like `mainsite`, `shop`, or `blog`
- **Minimal WooCommerce**: Only configure WooCommerce keys if you need e-commerce tools
- **Testing**: Start with one site, verify it works, then add more
- **Security**: Never commit `.env` file to git

---

## Running the Server

### Development Mode

```bash
# Activate virtual environment (if not already active)
source venv/bin/activate  # Linux/Mac
.\venv\Scripts\Activate.ps1  # Windows

# Run server
python src/main.py

# Or use the dev script
./scripts/dev.sh  # Linux/Mac
```

### Verify Server is Running

Check logs for:

```
INFO: MCP Server initialized
INFO: Registered 390 tools
INFO: Server ready
```

---

## Testing Your Setup

### Quick Health Check

Run the test script:

```bash
./scripts/test.sh quick
```

### Manual Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov

# Run specific test
pytest tests/test_wordpress_plugin.py
```

### Verify Tool Registration

Check that tools are registered:

```bash
python -c "
from src.main import app
tools = app.list_tools()
print(f'Total tools: {len(tools)}')
"
```

Expected output: `Total tools: 390` (for 3 configured sites)

---

## Using MCP Tools

### Tool Naming Convention

#### Per-Site Tools (Legacy)
```
wordpress_{site}_action
```
Examples:
- `wordpress_site1_list_posts`
- `wordpress_site2_get_product`
- `wordpress_site3_create_page`

#### Unified Tools (Recommended)
```
wordpress_action(site="site_id", ...)
```
Examples:
- `wordpress_list_posts(site="site1")`
- `wordpress_get_product(site="shop", product_id=123)`
- `wordpress_create_page(site="blog", title="Hello", content="...")`

### Using Site Aliases

If you configured `WORDPRESS_SITE2_ALIAS=shop`:

```python
# Both work the same
wordpress_list_products(site="site2")
wordpress_list_products(site="shop")
```

### Example: List Posts

**Using Per-Site Tools**:
```python
result = wordpress_site1_list_posts(per_page=10, status="publish")
```

**Using Unified Tools**:
```python
result = wordpress_list_posts(site="mainsite", per_page=10, status="publish")
```

### Example: Create Product

```python
result = wordpress_create_product(
    site="shop",
    name="New Product",
    type="simple",
    regular_price="29.99",
    description="Product description",
    status="publish"
)
```

### Example: Update Page

```python
result = wordpress_update_page(
    site="blog",
    page_id=42,
    title="Updated Title",
    content="<p>Updated content</p>",
    status="publish"
)
```

---

## Docker Deployment

### Quick Start

```bash
# Deploy with Docker
./scripts/deploy.sh

# Or manually
docker compose up -d
```

### Docker Commands

```bash
# View logs
docker compose logs -f

# Check status
docker compose ps

# Restart
docker compose restart

# Stop
docker compose down

# Rebuild
docker compose up --build -d
```

### Health Check

```bash
# Check container health
docker compose ps

# Test API endpoint
curl http://localhost:8000/health
```

---

## Coolify Deployment

### Prerequisites

- Coolify instance running
- Docker registry access (optional)

### Step 1: Create New Resource

1. Log in to Coolify dashboard
2. Click **+ New Resource**
3. Select **Docker Compose**

### Step 2: Configure Repository

1. **Git Repository**: `https://github.com/mcphub/mcphub.git`
2. **Branch**: `main`
3. **Build Pack**: `Docker Compose`

### Step 3: Configure Environment Variables

Add all required environment variables from `.env.example`:

```
WORDPRESS_SITE1_URL=https://example.com
WORDPRESS_SITE1_USERNAME=admin
WORDPRESS_SITE1_APP_PASSWORD=xxxx xxxx xxxx xxxx xxxx xxxx
...
```

### Step 4: Configure Health Check

- **Path**: `/health`
- **Port**: `8000`
- **Interval**: `30s`
- **Timeout**: `10s`
- **Retries**: `3`

### Step 5: Deploy

1. Click **Deploy**
2. Wait for build to complete
3. Check logs for successful startup

### Coolify-Specific Configuration

Add to `docker-compose.yml` if needed:

```yaml
services:
  mcp-server:
    labels:
      - "coolify.managed=true"
      - "coolify.port=8000"
      - "coolify.health_check=/health"
```

---

## Next Steps

### 1. Explore Available Tools

Check the [README](../README.md) for complete tool listing.

### 2. Configure Monitoring

- View health metrics: Use `check_all_projects_health` tool
- Check rate limits: Use `get_rate_limit_stats` tool
- Review audit logs: `tail -f logs/audit.log`

### 3. Customize Configuration

- Adjust rate limits in `.env`
- Configure log levels
- Add more WordPress sites

### 4. Read Documentation

- [Troubleshooting Guide](troubleshooting.md)
- [Security Policy](../SECURITY.md)
- [Contributing Guide](../CONTRIBUTING.md)

### 5. Join Community

- **Repository**: [github.com/mcphub/mcphub](https://github.com/mcphub/mcphub)
- **Contact**: hello@mcphub.dev
- **Website**: [mcphub.dev](https://mcphub.dev)

---

---
