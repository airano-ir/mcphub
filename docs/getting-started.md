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
# Edit .env — set MASTER_API_KEY and add your site credentials (see Configuration below)
docker compose up -d
```

After starting, see [Verify Installation](#verify-installation) below.

### Option 2: Docker Hub (No Clone)

```bash
# 1. Create a .env file (see Configuration section below)
# 2. Run:
docker run -d --name mcphub -p 8000:8000 --env-file .env airano/mcphub:latest
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
# Authentication (recommended — auto-generates temp key if omitted)
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

### WordPress Plugin Requirements

Some WordPress tools require additional plugins on your WordPress site:

| MCP Tool Category | WordPress Plugin Required |
|-------------------|--------------------------|
| SEO tools (`get_post_seo`, `update_post_seo`) | **Rank Math** or **Yoast SEO** |
| WP-CLI tools (`wp_cache_flush`, `wp_db_export`, etc.) | Docker socket access + `CONTAINER` env var |
| WooCommerce tools | **WooCommerce** 3.0+ (separate `WOOCOMMERCE_` config) |

### Docker Socket for WP-CLI Tools

WP-CLI tools (cache management, database export, plugin updates via CLI) require Docker socket access:

1. Add the container name to your `.env`:
   ```bash
   WORDPRESS_SITE1_CONTAINER=your-wp-container-name
   ```

2. Mount the Docker socket in `docker-compose.yaml`:
   ```yaml
   volumes:
     - /var/run/docker.sock:/var/run/docker.sock:ro
   ```

Without Docker socket, WP-CLI tools will return a "not available" message but all REST API tools work normally.

### Environment Variable Naming Convention

All site configuration follows the pattern: `{PLUGIN_PREFIX}_{SITE_ID}_{CONFIG_KEY}`

| Plugin | Prefix | Example |
|--------|--------|---------|
| WordPress | `WORDPRESS_` | `WORDPRESS_SITE1_URL` |
| WooCommerce | `WOOCOMMERCE_` | `WOOCOMMERCE_STORE1_URL` |
| WordPress Advanced | `WORDPRESS_ADVANCED_` | `WORDPRESS_ADVANCED_SITE1_URL` |
| Gitea | `GITEA_` | `GITEA_REPO1_URL` |
| n8n | `N8N_` | `N8N_INSTANCE1_URL` |
| Supabase | `SUPABASE_` | `SUPABASE_PROJECT1_URL` |
| OpenPanel | `OPENPANEL_` | `OPENPANEL_INSTANCE1_URL` |
| Appwrite | `APPWRITE_` | `APPWRITE_PROJECT1_URL` |
| Directus | `DIRECTUS_` | `DIRECTUS_INSTANCE1_URL` |

- `SITE_ID` can be any alphanumeric identifier (e.g., `SITE1`, `PROD`, `MYBLOG`)
- Add `_ALIAS` for a friendly name used in tool calls (e.g., `WORDPRESS_SITE1_ALIAS=myblog`)

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

### Verify Installation

After starting (via Docker or locally), wait ~30 seconds for the server to initialize, then:

**1. Check health:**

```bash
curl http://localhost:8000/health
# Expected: {"status": "ok", "tools_loaded": 596, ...}
```

**2. Open the web dashboard:**

Open **http://localhost:8000/dashboard** in your browser. Log in with your `MASTER_API_KEY`.

The dashboard lets you:
- View all connected sites and their health status
- Create and manage per-project API keys
- View audit logs
- Monitor rate limits

**3. Check container status (Docker only):**

```bash
docker compose ps
# Look for Status: "Up (healthy)"
# Note: Health check starts after 40 seconds — "starting" is normal initially

# View logs if something is wrong:
docker compose logs -f mcphub
```

**4. Troubleshooting:**

| Problem | Solution |
|---------|----------|
| Container exits immediately | Check logs: `docker compose logs mcphub` |
| Port 8000 already in use | Change port in docker-compose.yaml: `"8001:8000"` |
| Health check shows "unhealthy" | Wait 60 seconds, then check logs for startup errors |
| Dashboard login fails | Make sure you're using the `MASTER_API_KEY` value from your `.env` |
| Sites not showing up | Restart after adding new env vars: `docker compose restart` |

---

## Connect Your AI Client

MCP Hub uses **SSE (Server-Sent Events)** transport over HTTP. All requests require **Bearer token** authentication via the `Authorization` header. Query parameter auth is not supported.

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

### 596 Tools Across 9 Plugins

| Plugin | Tools | Env Prefix |
|--------|-------|------------|
| WordPress | 67 | `WORDPRESS_` |
| WooCommerce | 28 | `WOOCOMMERCE_` |
| WordPress Advanced | 22 | `WORDPRESS_ADVANCED_` |
| Gitea | 56 | `GITEA_` |
| n8n | 56 | `N8N_` |
| Supabase | 70 | `SUPABASE_` |
| OpenPanel | 73 | `OPENPANEL_` |
| Appwrite | 100 | `APPWRITE_` |
| Directus | 100 | `DIRECTUS_` |
| System | 24 | (no config needed) |

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

Use specific endpoints to limit tool access and save tokens:

```
/mcp                        → All 596 tools (Master API Key)
/system/mcp                 → System tools only (24 tools)
/wordpress/mcp              → WordPress tools (67 tools)
/woocommerce/mcp            → WooCommerce tools (28 tools)
/gitea/mcp                  → Gitea tools (56 tools)
/n8n/mcp                    → n8n tools (56 tools)
/supabase/mcp               → Supabase tools (70 tools)
/openpanel/mcp              → OpenPanel tools (73 tools)
/appwrite/mcp               → Appwrite tools (100 tools)
/directus/mcp               → Directus tools (100 tools)
/project/{alias}/mcp        → Per-project (auto-injects site)
```

> **Recommendation**: Use plugin-specific endpoints (e.g., `/wordpress/mcp`) instead of `/mcp` when possible. This reduces the number of tools your AI client loads, saving context tokens and improving response quality.

**Plugin endpoint vs Project endpoint:**

| Feature | Plugin endpoint (`/wordpress/mcp`) | Project endpoint (`/project/myblog/mcp`) |
|---------|-----------------------------------|----------------------------------------|
| Tools loaded | All tools for that plugin type | Same tools, but `site` parameter auto-injected |
| Site selection | Must pass `site` parameter manually | Site is auto-selected (no `site` param needed) |
| Best for | Managing multiple sites of same type | Dedicated access to a single site |

---

## Docker Deployment

### Quick Start

```bash
docker compose up -d
```

After starting, verify the installation:

```bash
curl http://localhost:8000/health          # server health
open http://localhost:8000/dashboard        # web dashboard
```

See [Verify Installation](#verify-installation) for detailed steps.

### Docker Commands

```bash
# View logs
docker compose logs -f mcphub

# Check status (look for "healthy")
docker compose ps

# Restart (needed after .env changes)
docker compose restart

# Stop
docker compose down

# Rebuild (after code changes)
docker compose up --build -d
```

### Adding Sites After Startup

1. Edit your `.env` file to add new site credentials
2. Restart the container: `docker compose restart`
3. Verify: `curl http://localhost:8000/health` — check that tools are loaded
4. The dashboard at http://localhost:8000/dashboard will show the new sites

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

1. **Explore the full tool list**: See the [README](../README.md) for all 596 tools
2. **Set up API keys**: [API Keys Guide](API_KEYS_GUIDE.md) for per-project access control
3. **Configure OAuth**: [OAuth Guide](OAUTH_GUIDE.md) for Claude/ChatGPT auto-registration
4. **Monitor health**: Use `check_all_projects_health` tool or visit the web dashboard
5. **Troubleshoot issues**: [Troubleshooting Guide](troubleshooting.md)

---
