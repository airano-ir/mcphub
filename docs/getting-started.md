# Getting Started with MCP Hub

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Running the Server](#running-the-server)
5. [Connect Your AI Client](#connect-your-ai-client)
6. [Using MCP Tools](#using-mcp-tools)
7. [Docker Deployment](#docker-deployment)
8. [Coolify Deployment](#coolify-deployment)
9. [Next Steps](#next-steps)

---

## Prerequisites

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

### Option 1: Docker (Recommended)

```bash
git clone https://github.com/airano-ir/mcphub.git
cd mcphub
cp env.example .env
# Edit .env with your site credentials
docker compose up -d
```

### Option 2: PyPI

```bash
pip install mcphub-server
```

### Option 3: From Source

```bash
git clone https://github.com/airano-ir/mcphub.git
cd mcphub
pip install -e .
cp env.example .env
# Edit .env with your site credentials
python server.py --transport sse --port 8000
```

### Option 4: Automated Setup Scripts

#### Linux/Mac

```bash
git clone https://github.com/airano-ir/mcphub.git
cd mcphub
chmod +x scripts/setup.sh
./scripts/setup.sh
```

#### Windows (PowerShell)

```powershell
git clone https://github.com/airano-ir/mcphub.git
cd mcphub
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
.\scripts\setup.ps1
```

---

## Configuration

### Step 1: Generate WordPress Application Passwords

For each WordPress site:

1. Log in to WordPress admin
2. Navigate to: **Users > Your Profile**
3. Scroll to **Application Passwords** section
4. Enter name: `MCP Hub`
5. Click **Add New Application Password**
6. Copy the generated password (format: `xxxx xxxx xxxx xxxx xxxx xxxx`)

**Important**: Save this password immediately. You cannot retrieve it later.

### Step 2: Generate WooCommerce API Keys

If using WooCommerce tools:

1. Go to: **WooCommerce > Settings > Advanced > REST API**
2. Click **Add Key**
3. Fill in:
   - **Description**: `MCP Hub`
   - **User**: Select admin user
   - **Permissions**: `Read/Write`
4. Click **Generate API Key**
5. Copy **Consumer Key** and **Consumer Secret**

### Step 3: Configure Environment Variables

Edit the `.env` file with your credentials:

```bash
# ============================================
# Required
# ============================================
MASTER_API_KEY=your-secure-key-here

# ============================================
# WordPress Site
# ============================================
WORDPRESS_SITE1_URL=https://myblog.com
WORDPRESS_SITE1_USERNAME=admin
WORDPRESS_SITE1_APP_PASSWORD=xxxx xxxx xxxx xxxx xxxx xxxx
WORDPRESS_SITE1_ALIAS=myblog

# ============================================
# WooCommerce Store (separate plugin)
# ============================================
WOOCOMMERCE_STORE1_URL=https://mystore.com
WOOCOMMERCE_STORE1_CONSUMER_KEY=ck_xxxxx
WOOCOMMERCE_STORE1_CONSUMER_SECRET=cs_xxxxx
WOOCOMMERCE_STORE1_ALIAS=mystore

# ============================================
# Gitea Instance (optional)
# ============================================
GITEA_REPO1_URL=https://git.example.com
GITEA_REPO1_TOKEN=your_gitea_token
GITEA_REPO1_ALIAS=mygitea

# ============================================
# OAuth (required for Claude/ChatGPT auto-registration)
# ============================================
OAUTH_JWT_SECRET_KEY=your-jwt-secret
OAUTH_BASE_URL=https://your-server:8000

# ============================================
# Optional
# ============================================
LOG_LEVEL=INFO
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_PER_HOUR=1000
RATE_LIMIT_PER_DAY=10000
```

### Configuration Tips

- **Site Aliases**: Use friendly names like `myblog`, `mystore`, or `mygitea`
- **Separate plugins**: WordPress and WooCommerce are separate plugins with separate env var prefixes
- **Testing**: Start with one site, verify it works, then add more
- **Security**: Never commit `.env` file to git

---

## Running the Server

### SSE Transport (for remote AI clients)

```bash
python server.py --transport sse --port 8000
```

### Stdio Transport (for Claude Desktop local)

```bash
python server.py
```

### Verify Server is Running

Check logs for:

```
INFO: MCP Hub initialized
INFO: Registered 589 tools
INFO: Server ready
```

Or test the health endpoint:

```bash
curl http://localhost:8000/health
```

---

## Connect Your AI Client

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mcphub": {
      "url": "https://your-server:8000/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_MASTER_API_KEY"
      }
    }
  }
}
```

### Claude Code

Add to `.mcp.json` in your project:

```json
{
  "mcpServers": {
    "mcphub": {
      "type": "sse",
      "url": "https://your-server:8000/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_MASTER_API_KEY"
      }
    }
  }
}
```

### Cursor

Go to **Settings > MCP Servers > Add Server**:

- **Name**: MCP Hub
- **URL**: `https://your-server:8000/mcp`
- **Headers**: `Authorization: Bearer YOUR_MASTER_API_KEY`

### VS Code + Copilot

Add to `.vscode/mcp.json`:

```json
{
  "servers": {
    "mcphub": {
      "type": "sse",
      "url": "https://your-server:8000/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_MASTER_API_KEY"
      }
    }
  }
}
```

### ChatGPT (Remote MCP)

MCP Hub supports **Open Dynamic Client Registration** (RFC 7591). ChatGPT can auto-register as an OAuth client:

1. Deploy MCP Hub with `OAUTH_BASE_URL` set
2. In ChatGPT, add MCP server: `https://your-server:8000/mcp`
3. ChatGPT auto-discovers OAuth metadata and registers

---

## Using MCP Tools

### 589 Tools Across 9 Plugins

| Plugin | Tools | Env Prefix |
|--------|-------|------------|
| WordPress | 67 | `WORDPRESS_` |
| WooCommerce | 28 | `WOOCOMMERCE_` |
| WordPress Advanced | 22 | `WORDPRESS_` (same sites, advanced ops) |
| Gitea | 56 | `GITEA_` |
| n8n | 56 | `N8N_` |
| Supabase | 70 | `SUPABASE_` |
| OpenPanel | 73 | `OPENPANEL_` |
| Appwrite | 100 | `APPWRITE_` |
| Directus | 100 | `DIRECTUS_` |
| System | 17 | (no config needed) |

### Unified Tool Pattern

All tools use a `site` parameter to select which site to operate on:

```python
wordpress_list_posts(site="myblog", per_page=10, status="publish")
wordpress_create_post(site="myblog", title="Hello", content="World")
woocommerce_list_products(site="mystore")
gitea_list_repos(site="mygitea")
```

The `site` parameter accepts either a **site_id** (e.g., `site1`) or an **alias** (e.g., `myblog`).

### Multi-Endpoint Architecture

Use specific endpoints to limit tool access:

```
/mcp                        → All 589 tools (Master API Key)
/system/mcp                 → System tools only (17 tools)
/wordpress/mcp              → WordPress tools (67 tools)
/woocommerce/mcp            → WooCommerce tools (28 tools)
/gitea/mcp                  → Gitea tools (56 tools)
/project/{alias}/mcp        → Per-project (auto-injects site)
```

---

## Docker Deployment

### Quick Start

```bash
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

### Step 1: Create New Resource

1. Log in to Coolify dashboard
2. Click **+ New Resource**
3. Select **Docker Compose**

### Step 2: Configure Repository

1. **Git Repository**: `https://github.com/airano-ir/mcphub.git`
2. **Branch**: `main`
3. **Build Pack**: `Docker Compose`

### Step 3: Configure Environment Variables

Add all required environment variables in Coolify's environment variable UI:

```
MASTER_API_KEY=your-secure-key-here
OAUTH_JWT_SECRET_KEY=your-jwt-secret
OAUTH_BASE_URL=https://your-domain.com
WORDPRESS_SITE1_URL=https://example.com
WORDPRESS_SITE1_USERNAME=admin
WORDPRESS_SITE1_APP_PASSWORD=xxxx xxxx xxxx xxxx
```

The server auto-discovers all `WORDPRESS_*`, `WOOCOMMERCE_*`, `GITEA_*`, and other plugin environment variables at startup.

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

---

## Next Steps

1. **Explore the full tool list**: See the [README](../README.md) for all 589 tools
2. **Set up API keys**: [API Keys Guide](API_KEYS_GUIDE.md) for per-project access control
3. **Configure OAuth**: [OAuth Guide](OAUTH_GUIDE.md) for Claude/ChatGPT auto-registration
4. **Monitor health**: Use `check_all_projects_health` tool or visit the web dashboard
5. **Troubleshoot issues**: [Troubleshooting Guide](troubleshooting.md)

---
