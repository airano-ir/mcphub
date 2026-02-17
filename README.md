# MCP Hub

<div align="center">

**The AI-native management hub for WordPress, WooCommerce, and self-hosted services.**

Connect your sites, stores, repos, and databases — manage them all through Claude, ChatGPT, Cursor, or any MCP client.

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-3776ab.svg)](https://www.python.org/)
[![PyPI](https://img.shields.io/pypi/v/mcphub-server.svg)](https://pypi.org/project/mcphub-server/)
[![Docker](https://img.shields.io/docker/v/airano/mcphub?label=docker)](https://hub.docker.com/r/airano/mcphub)
[![Tests: 289 passing](https://img.shields.io/badge/tests-289%20passing-brightgreen.svg)]()
[![Tools: 596](https://img.shields.io/badge/tools-596-orange.svg)]()
[![CI](https://github.com/airano-ir/mcphub/actions/workflows/ci.yml/badge.svg)](https://github.com/airano-ir/mcphub/actions/workflows/ci.yml)

</div>

---

## Why MCP Hub?

WordPress powers 43% of the web. WooCommerce runs 36% of online stores. Yet **no MCP server existed** for managing them through AI — until now.

MCP Hub is the first MCP server that lets you manage WordPress, WooCommerce, and 7 other self-hosted services through any AI assistant. Instead of clicking through dashboards, just tell your AI what to do:

> *"Update the SEO meta description for all WooCommerce products that don't have one"*
>
> *"Create a new blog post about our Black Friday sale and schedule it for next Monday"*
>
> *"Check the health of all 12 WordPress sites and report any with slow response times"*

### What Makes MCP Hub Different

| Feature | ManageWP | MainWP | AI Content Plugins | **MCP Hub** |
|---------|----------|--------|---------------------|-------------|
| Multi-site management | Yes | Yes | No | **Yes** |
| AI agent integration | No | No | No | **Native (MCP)** |
| Full WordPress API | Dashboard | Dashboard | Content only | **67 tools** |
| WooCommerce management | No | Limited | No | **28 tools** |
| Git/CI management | No | No | No | **56 tools (Gitea)** |
| Automation workflows | No | No | No | **56 tools (n8n)** |
| Self-hosted | No | Yes | N/A | **Yes** |
| Open source | No | Core only | Varies | **Fully open** |
| Price | $0.70-8/site/mo | $29-79/yr | $19-79/mo | **Free** |

---

## 596 Tools Across 9 Plugins

| Plugin | Tools | What You Can Do |
|--------|-------|-----------------|
| **WordPress** | 67 | Posts, pages, media, users, menus, taxonomies, SEO (Rank Math/Yoast) |
| **WooCommerce** | 28 | Products, orders, customers, coupons, reports, shipping |
| **WordPress Advanced** | 22 | Database ops, bulk operations, WP-CLI, system management |
| **Gitea** | 56 | Repos, issues, pull requests, releases, webhooks, organizations |
| **n8n** | 56 | Workflows, executions, credentials, variables, audit |
| **Supabase** | 70 | Database, auth, storage, edge functions, realtime |
| **OpenPanel** | 73 | Events, funnels, profiles, dashboards, projects |
| **Appwrite** | 100 | Databases, auth, storage, functions, teams, messaging |
| **Directus** | 100 | Collections, items, users, files, flows, permissions |
| **System** | 24 | Health monitoring, API keys, OAuth management, audit |
| **Total** | **596** | Constant count — scales to unlimited sites |

---

## Quick Start

### Option 1: Docker (Recommended)

```bash
git clone https://github.com/airano-ir/mcphub.git
cd mcphub
cp env.example .env
# Edit .env — set MASTER_API_KEY and add your site credentials
docker compose up -d
```

### Option 2: Docker Hub (No Clone)

```bash
# Create a .env file with your credentials (see "Configure Your Sites" below)
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

### Verify It Works

After starting the server, wait ~30 seconds then:

```bash
# Check server health
curl http://localhost:8000/health
```

Open the **web dashboard** in your browser: **http://localhost:8000/dashboard**

You should see the login page. Use your `MASTER_API_KEY` to log in.

### Configure Your Sites

Add site credentials to `.env`:

```bash
# Master API Key (required)
MASTER_API_KEY=your-secure-key-here

# WordPress Site
WORDPRESS_SITE1_URL=https://myblog.com
WORDPRESS_SITE1_USERNAME=admin
WORDPRESS_SITE1_APP_PASSWORD=xxxx xxxx xxxx xxxx
WORDPRESS_SITE1_ALIAS=myblog

# WooCommerce Store
WOOCOMMERCE_STORE1_URL=https://mystore.com
WOOCOMMERCE_STORE1_CONSUMER_KEY=ck_xxxxx
WOOCOMMERCE_STORE1_CONSUMER_SECRET=cs_xxxxx
WOOCOMMERCE_STORE1_ALIAS=mystore

# Gitea Instance
GITEA_REPO1_URL=https://git.example.com
GITEA_REPO1_TOKEN=your_gitea_token
GITEA_REPO1_ALIAS=mygitea
```

### Connect Your AI Client

<details>
<summary><b>Claude Desktop</b></summary>

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

</details>

<details>
<summary><b>Claude Code</b></summary>

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

</details>

<details>
<summary><b>Cursor</b></summary>

Go to **Settings > MCP Servers > Add Server**:

- **Name**: MCP Hub
- **URL**: `https://your-server:8000/mcp`
- **Headers**: `Authorization: Bearer YOUR_MASTER_API_KEY`

</details>

<details>
<summary><b>VS Code + Copilot</b></summary>

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

</details>

<details>
<summary><b>ChatGPT (Remote MCP)</b></summary>

MCP Hub supports **Open Dynamic Client Registration** (RFC 7591). ChatGPT can auto-register as an OAuth client:

1. Deploy MCP Hub with `OAUTH_BASE_URL` set
2. In ChatGPT, add MCP server: `https://your-server:8000/mcp`
3. ChatGPT auto-discovers OAuth metadata and registers

</details>

---

## Architecture

```
/mcp                        → Admin endpoint (all 596 tools)
/system/mcp                 → System tools only (24 tools)
/wordpress/mcp              → WordPress tools (67 tools)
/woocommerce/mcp            → WooCommerce tools (28 tools)
/gitea/mcp                  → Gitea tools (56 tools)
/n8n/mcp                    → n8n tools (56 tools)
/supabase/mcp               → Supabase tools (70 tools)
/openpanel/mcp              → OpenPanel tools (73 tools)
/appwrite/mcp               → Appwrite tools (100 tools)
/directus/mcp               → Directus tools (100 tools)
/project/{alias}/mcp        → Per-project endpoint (auto-injects site)
```

**Multi-endpoint architecture**: Give each team member or AI agent access to only the tools they need.

### Security

- **OAuth 2.1 + PKCE** (RFC 8414, 7591, 7636) with auto-registration for Claude/ChatGPT
- **Per-project API keys** with scoped permissions (read/write/admin)
- **Rate limiting**: 60/min, 1,000/hr, 10,000/day per client
- **GDPR-compliant audit logging** with automatic sensitive data filtering
- **Web dashboard** with real-time health monitoring (8 pages, EN/FA i18n)

> **Compatibility Note**: MCP Hub requires FastMCP 2.x (`>=2.14.0,<3.0.0`). FastMCP 3.0 introduced breaking changes and is not yet supported. If you install dependencies manually, ensure you don't upgrade to FastMCP 3.x.

---

## Documentation

| Guide | Description |
|-------|-------------|
| [Getting Started](docs/getting-started.md) | Full setup walkthrough |
| [Architecture](docs/ARCHITECTURE.md) | System design and module reference |
| [API Keys Guide](docs/API_KEYS_GUIDE.md) | Per-project API key management |
| [OAuth Guide](docs/OAUTH_GUIDE.md) | OAuth 2.1 setup for Claude/ChatGPT |
| [Gitea Guide](docs/GITEA_GUIDE.md) | Gitea plugin configuration |
| [Deployment Guide](docs/DEPLOYMENT_GUIDE.md) | Docker and Coolify deployment |
| [Troubleshooting](docs/troubleshooting.md) | Common issues and solutions |
| [Plugin Development](docs/PLUGIN_DEVELOPMENT.md) | Build your own plugin |

---

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests (289 tests)
pytest

# Format and lint
black . && ruff check --fix .

# Run server locally
python server.py --transport sse --port 8000
```

---

## Support This Project

MCP Hub is free and open-source. Development is funded by community donations.

[**Donate with Crypto (NOWPayments)**](https://nowpayments.io/donation/airano) — Global, no geographic restrictions.

| Goal | Monthly | Enables |
|------|---------|---------|
| Infrastructure | $50/mo | Demo hosting, CI/CD, domain |
| Part-time maintenance | $500/mo | Updates, security patches, issue triage |
| Active development | $2,000/mo | New plugins, features, community support |

---

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

**Priority areas:**
- New plugin development
- Client setup guides
- Workflow templates and examples
- Test coverage expansion
- Translations (i18n)

---

## License

MIT License. See [LICENSE](LICENSE).

---
