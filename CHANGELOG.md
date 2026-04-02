# 📝 Changelog

All notable changes to MCP Hub will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.6.0] — 2026-04-02

### Gitea Plugin — Public Release (Track F.16)

Gitea plugin fully reviewed, tested, and published for public use. Two missing tools added, comprehensive test suite created.

#### Added
- **`update_webhook` tool**: Update existing webhook configuration, events, and active status (admin scope)
- **`delete_label` tool**: Delete labels from repositories (write scope)
- **`tests/test_gitea_plugin.py`**: Comprehensive test suite — 85+ tests covering client init, headers, tool specs, all 5 handler groups, health check, and plugin delegation

#### Changed
- **Gitea plugin now public**: Added `gitea` to `DEFAULT_PUBLIC_PLUGINS` — available to all OAuth users
- **Tool count**: 565 → 567 (added update_webhook + delete_label)
- **env.example**: Updated default `ENABLED_PLUGINS` to include `gitea`

---

## [3.5.0] — 2026-04-02

### FastMCP Upgrade & Legacy Cleanup (Track F.15)

Major cleanup release: upgraded to FastMCP 3.x, removed all legacy modules, and simplified the architecture.

#### Changed
- **FastMCP 3.x**: Upgraded from `fastmcp>=2.14.0,<3.0.0` to `fastmcp>=3.0.0,<4.0.0`
- **HealthMonitor refactored**: Removed `ProjectManager` dependency — now uses `SiteManager` exclusively for site discovery and health checks
- **Endpoint introspection**: Replaced internal `_tool_manager._tools` access with tracked `_tool_counts` dict in `MCPEndpointFactory`

#### Removed
- **`server_multi.py`**: Legacy multi-endpoint server entry point (replaced by unified `server.py` since v3.0)
- **`core/project_manager.py`**: Legacy project manager shell — HealthMonitor no longer depends on it
- **Legacy exports**: Removed `ProjectManager` and `get_project_manager` from `core/__init__.py`
- References from `pyproject.toml` (py-modules, ruff per-file-ignores), community build script, and documentation

---

## [3.4.0] — 2026-03-31

### OpenPanel Plugin — Public Release (Track F.10)

OpenPanel product analytics plugin fully reviewed, tested, and published for public use. Works with both self-hosted and cloud (openpanel.dev) instances.

#### Added
- **OpenPanel Plugin** (42 tools): Complete rewrite using public REST APIs — no tRPC/session dependency
  - **Track API** (11 tools): track_event, page_view, screen_view, identify_user, set_user_properties, increment/decrement_property, create_group, assign_group, track_revenue, track_batch
  - **Export API** (10 tools): export_events, export_events_csv, export_chart_data, get_event_count, get_unique_users, get_page_views, get_top_pages, get_top_referrers, get_geo_data, get_device_data
  - **Insights API** (2 tools): get_overview_report, get_realtime_stats
  - **Profile API** (3 tools): get_profile_events, get_profile_sessions, export_profile_data
  - **Manage API** (10 tools): list/get/create/update/delete projects and clients
  - **System** (6 tools): health_check, get_instance_info, get_usage_stats, get_storage_stats, test_connection, get_rate_limit_status
- **Service Page descriptions**: Per-plugin description and notes section on service detail pages
- **Dynamic URL hints**: Add Site form shows per-plugin URL guidance (e.g., OpenPanel API URL vs dashboard URL)
- **WordPress plugin download**: OpenPanel WordPress plugin bundled at `/static/plugins/openpanel-self-hosted.zip`
- **62 unit tests** for OpenPanel plugin (`tests/test_openpanel_plugin.py`)

#### Changed
- `ENABLED_PLUGINS` default: `wordpress,woocommerce,supabase,openpanel` (was: `wordpress,woocommerce,supabase`)
- OpenPanel health check uses `GET /healthcheck` (was: non-existent `/api/v1/oauth/token`)
- OpenPanel credential fields: added Project ID and Organization ID (optional)

#### Removed
- OpenPanel `alias_user` tool (explicitly unsupported by OpenPanel API)
- OpenPanel dashboard handler (18 tools) — no public API available, was placeholder stubs
- OpenPanel funnel handler (8 tools) — no public API available, was placeholder stubs
- tRPC client dependency — all tools now use public REST APIs

---

## [3.3.0] — 2026-03-31

### Platform Hardening & Admin Unification (Track F.1–F.8)

Major quality release: plugin visibility control, UI/UX polish, unified admin panel, database-backed settings, and security hardening. No breaking API changes.

#### Added
- **Plugin Visibility Control** (F.1): `ENABLED_PLUGINS` env var controls which plugins public users see. Default: `wordpress,woocommerce,supabase`. Admin sees all. New module: `core/plugin_visibility.py`
- **MCP Service Pages** (F.3): Dedicated `/dashboard/services/{type}` pages showing plugin capabilities, tool list, and setup requirements. Services list page with grid of plugin cards
- **Admin by Email** (F.4a): `ADMIN_EMAILS` env var for designating OAuth users as admin (supports multiple emails). OAuth admin users see full admin sidebar
- **Master Key Scope Control** (F.4b): `DISABLE_MASTER_KEY_LOGIN` to block dashboard login via master key. `MASTER_KEY_SCOPE` (`all`/`admin`) to restrict master key to admin endpoints only
- **Panel Unification** (F.4c): OAuth admin sees both "My Tools" and "Administration" sidebar sections. Master key admin auto-creates user record on first login for unified site management
- **Settings from UI** (F.4c.3): Database-backed settings with DB > ENV > Default priority. Admin can edit `ENABLED_PLUGINS`, `MAX_SITES_PER_USER`, rate limits, registration toggle from dashboard. New module: `core/settings.py`
- **Dashboard Stats** (F.3): Admin home page shows Total Users and User Sites stat cards
- **Pre-configured OAuth** (F.2): Default OAuth redirect URIs for Claude.ai; green tip about optional OAuth

#### Fixed
- **Connect Page** (F.2): WordPress/SEO amber info box shown only for WordPress/WooCommerce sites (was shown for all plugin types)
- **Sidebar Version** (F.2): Fixed "v" displaying when version string is empty
- **Auth Page Language** (F.2): Auth page defaults to English regardless of Accept-Language header
- **Donation Link** (F.2): Moved from home page to sidebar for consistent visibility
- **Test Connection** (F.3): Fixed 504/HTML error handling; status badge auto-updates without page refresh; added `last_tested_at` timestamp (DB schema v4)
- **Admin Auth** (F.4): Fixed `_require_admin_session()` to recognize OAuth admin sessions; hide "Admin Login with API Key" button when `DISABLE_MASTER_KEY_LOGIN=true`
- **Starlette API** (F.2): Updated `TemplateResponse` to new API (request as first arg)

#### Security
- **exec() Removal** (F.8): Replaced `exec()` in `core/tool_generator.py` with closure-based tool generation
- **Shell Injection Fix** (F.8): Replaced `create_subprocess_shell` with `create_subprocess_exec` in WP-CLI handler
- **bcrypt Migration** (F.8): Admin API key hashing upgraded from unsalted SHA-256 to bcrypt

#### Tests
- New test suites: `test_plugin_visibility.py`, `test_admin_system.py`, `test_f3_admin_stats.py`, `test_f3_last_tested.py`, `test_f3_service_pages.py`

---

## [3.2.0] — 2026-02-25

### Fixed
- **Bug A**: OAuth consent redirect loop — after GitHub/Google login, page now returns to consent screen instead of `/dashboard`
- **Bug B**: `/u/{user_id}/{alias}/mcp` endpoint now accepts OAuth JWT tokens (issued after social login) in addition to `mhu_` API keys
- **Bug C**: OAuth users can now create, list, and delete their own OAuth clients via the new `/dashboard/connect/oauth-clients` page
- **D-1**: Dashboard sidebar border uses Tailwind class instead of inline style; version shown in footer
- **D-2**: Removed broken `setInterval` in dashboard that targeted non-existent `#stats-container`
- **D-3**: 404 page uses purple primary colors and respects system dark mode preference
- **D-4**: Fixed invisible buttons (`bg-gray-200` + `text-white` in light mode) across api-keys, health, projects pages
- **D-5**: Pinned Alpine.js to 3.14.8; removed duplicate CSRF meta tag from `head_assets.html`
- **D-6**: Fixed invisible language toggle button in settings (dark mode)

### Added
- `OAuthClient.owner_user_id` field for per-user OAuth client isolation
- `dashboard_connect_page` now includes Claude.ai connection guide with endpoint URL and link to OAuth Clients
- New route: `GET /dashboard/connect/oauth-clients` — user's OAuth clients list
- New API: `POST /api/dashboard/user-oauth-clients/create` — create OAuth client for logged-in user
- New API: `DELETE /api/dashboard/user-oauth-clients/{client_id}` — delete own OAuth client

---

## [3.1.0] - 2026-02-23

### Live Platform Foundation (Track E.1 - E.3)

Major release introducing the Live Platform architecture — SQLite database, OAuth social login, site management, and per-user MCP endpoints. All features are included in the Community Edition.

#### Added
- **SQLite Database Backend** (E.1): Async SQLite via aiosqlite, WAL mode, schema versioning with migrations framework, CRUD for users/sites/API keys/connection tokens
- **Credential Encryption** (E.1): AES-256-GCM with HKDF per-site key derivation, versioned wire format for future migration support
- **OAuth Social Login** (E.2): GitHub + Google OAuth 2.0, CSRF state tokens, JWT session management, dual session types (admin + oauth_user)
- **Site Management API** (E.3): Plugin credential definitions for all 9 plugins, connection validation, encrypted site CRUD, MAX_SITES_PER_USER=10
- **User API Keys** (E.3): bcrypt-hashed keys with `mhu_` prefix, 8-char prefix for indexed lookup, 5-minute validation cache
- **Per-User MCP Endpoints** (E.3): Direct JSON-RPC handler at `/u/{user_id}/{alias}/mcp`, per-user rate limiting (30/min, 500/hr)
- **Config Snippets** (E.3): Auto-generated config for Claude Desktop, Claude Code, Cursor, VS Code, and ChatGPT
- **Dashboard Pages**: My Sites (list/add/test/delete), Connect (API keys + config snippets), Profile, OAuth Login
- **Dark/Light Mode Toggle**: Theme switcher across all dashboard pages
- **RBAC**: Role-based access control for dashboard
- **Active Health Checks**: Background health monitoring for connected services

#### Fixed
- CSRF middleware body consumption bug
- OAuth log noise and DCR crash on startup
- WordPress site connection validation (uses aiohttp to match plugin client)
- Tenant isolation enforced on all site queries

#### Security
- All bare `except:` replaced with `except Exception:` across 12 files
- Network error differentiation (DNS, SSL, timeout, connection refused)
- Retry with exponential backoff for transient errors only
- Auth/config errors never retried

#### Tests
- 452 total tests (up from 303), all passing
- New test suites: database (37), encryption (27), user_auth (32), site_api (17), user_keys (14), user_endpoints (12), config_snippets (10)

---

## [2.9.0] - 2026-02-14

### Project Revival - Dependency Updates & Documentation Sync

After 2-month hiatus (Dec 2025 - Feb 2026), updated all dependencies and verified compatibility.

#### Updated
- FastMCP: 2.12.4 → 2.14.5 (zero breaking changes for our codebase)
- MCP Protocol: 1.16.0 → 1.26.0
- cryptography: 46.0.2 → 46.0.5 (security patches)
- starlette: 0.48.0 → 0.52.1
- authlib: 1.6.5 → 1.6.7
- pydantic: 2.12.0 → 2.12.5
- PyJWT: installed (was missing from environment)

#### Fixed
- OAuth token timestamps: replaced `datetime.utcnow()` with `datetime.now(timezone.utc)` and `time.time()` for correct UTC timestamps in non-UTC timezones
- OAuth schemas: `is_expired()` now handles both naive and timezone-aware datetimes
- OAuth token reuse detection: `get_refresh_token()` now supports `include_revoked` parameter for proper reuse detection
- OAuth audit logging: fixed `AuditLogger.log_event()` call to use existing `log_system_event()` method
- All 54 tests now pass (previously 5 were failing)

#### Verified
- All 596 tools generate correctly
- Middleware API stable (Middleware, MiddlewareContext, get_http_headers)
- 30+ custom routes operational (dashboard + OAuth)
- Multi-endpoint architecture functional

#### Documentation
- Aligned version to 2.9.0 across all files (pyproject.toml was 1.3.0)
- Synchronized pyproject.toml dependencies with requirements.txt
- Updated ROADMAP.md and MASTER_CONTEXT.md dates

---

## [1.3.0] - 2025-11-21

### 🎉 Phase E: Custom OAuth Authorization Page with Multi-language Support

**Major Feature**: Beautiful web-based OAuth authorization with English & Farsi support!

#### ✨ Added

**Web-Based Authorization UI:**
- Beautiful HTML templates with Tailwind CSS and dark mode support
- Responsive design (mobile-friendly)
- User-friendly API Key input form with validation
- Smooth animations and transitions

**Multi-language Support (i18n):**
- Complete English (EN) & Persian/Farsi (FA) translations
- Automatic language detection from Accept-Language header
- RTL (Right-to-Left) layout support for Farsi
- 30+ translation keys covering all UI elements

**Security Enhancements:**
- CSRF Protection (`core/oauth/csrf.py`):
  - Cryptographically secure token generation (64 chars)
  - 10-minute token lifetime with automatic cleanup
  - One-time use tokens (consumed after validation)
- API Key validation at authorization time
- Permission inheritance from API Key to OAuth token
- Rate limiting infrastructure ready

**Files Added:**
- `core/i18n.py` - Internationalization utilities (200+ lines)
- `core/oauth/csrf.py` - CSRF token manager (150+ lines)
- `templates/base.html` - Base template with Tailwind CSS
- `templates/oauth/authorize.html` - Authorization form (170 lines)
- `templates/oauth/error.html` - Error page (90 lines)

**Commits**: c851c78, 7ec3b9d, b9b7dda, c60dd43

---

## [1.2.0] - 2025-11-18

### 🎉 Phase D: WordPress Advanced Plugin Split

**Plugin Separation**: Advanced WordPress features moved to dedicated plugin!

#### Changed

**Plugin Structure:**
- Split WordPress plugin into two modules:
  - `plugins/wordpress/` - Core features (92 tools)
  - `plugins/wordpress_advanced/` - Advanced features (22 tools)

**WordPress Advanced Plugin** (`plugins/wordpress_advanced/`):
- Database Operations (7 tools): export, import, size, tables, search, query, repair
- Bulk Operations (8 tools): parallel batch processing with semaphore control
- System Operations (7 tools): system info, cron, cache, error logs

**Benefits:**
- Better tool visibility (basic users see only 92 tools)
- Improved security (sensitive features in separate plugin)
- Granular access control (separate API keys per plugin)
- Reduced complexity for regular users

**Documentation:**
- Complete README.md in `plugins/wordpress_advanced/`
- Environment configuration examples
- Conditional initialization guide

**Tool Count**: Remains 114 total (92 core + 22 advanced split)

**Commits**: 2df7f31, fc97c85, 475dd73

---

## [1.1.0] - 2025-11-19

### 🎉 Phase C: Gitea Plugin Implementation

**New Plugin**: Complete Gitea repository management with 55 tools!

#### ✨ Added

**Gitea Plugin** (`plugins/gitea/`):

**Features:**
- Repository Management (15 tools): CRUD, branches, tags, files
- Issue Tracking (12 tools): issues, labels, milestones, comments
- Pull Requests (15 tools): PRs, reviews, merges, comments
- User & Organization (8 tools): users, orgs, teams, search
- Webhooks (5 tools): webhook management

**Architecture (Option B Clean Architecture):**
- Pydantic Schemas (6 files, ~1,100 lines):
  - `common.py` - Site, Pagination, User models
  - `repository.py` - Repository, Branch, Tag, File models
  - `issue.py` - Issue, Label, Milestone, Comment models
  - `pull_request.py` - PR, Review, Commit, File models
  - `user.py` - User, Organization, Team models
  - `webhook.py` - Webhook configuration models
- Gitea API Client (`client.py` - 406 lines):
  - OAuth 2.1 integration
  - Full REST API methods
  - Error handling and logging
- Handler Modules (5 files, ~2,900 lines):
  - `repositories.py`, `issues.py`, `pull_requests.py`
  - `users.py`, `webhooks.py`
- Main Plugin (`plugin.py` - 177 lines):
  - Dynamic method delegation with `__getattr__`
  - `get_tool_specifications()` static method
  - Health check integration

**Bug Fixes:**
- Plugin registration integration (a30b444)
- Tool registration enabled (61b8280)
- Dynamic method delegation fix (bb251c0)
- Pydantic V2 compatibility (8bc4eb6)
- Schema validation - JSON strings (dbd3234)

**Documentation:**
- Complete usage guide (`docs/GITEA_GUIDE.md` - 724 lines)
- Environment configuration in `.env.example`

**Tool Count**: 136 → 191 tools (+55 Gitea tools)

**Commits**: a30b444, 61b8280, bb251c0, 8bc4eb6, dbd3234

---

## [1.0.0] - 2025-11-18

### 🎉 Phase B: OAuth 2.1 Infrastructure

**Major Feature**: Production-ready OAuth 2.1 server with RFC compliance!

#### ✨ Added

**OAuth 2.1 Server** (`core/oauth/server.py` - ~450 lines):
- RFC 8414: Authorization Server Metadata
- RFC 7591: Dynamic Client Registration (Protected)
- RFC 7636: PKCE (S256 mandatory)
- RFC 8705: Protected Resource Metadata

**Core Components:**
- `core/oauth/schemas.py` - Pydantic models (OAuthClient, tokens)
- `core/oauth/pkce.py` - PKCE implementation (S256)
- `core/oauth/storage.py` - JSON-based token storage with auto-cleanup
- `core/oauth/client_registry.py` - OAuth client management
- `core/oauth/token_manager.py` - JWT generation/validation

**OAuth Endpoints (4 endpoints):**
- `GET /.well-known/oauth-authorization-server` (discovery)
- `GET /.well-known/oauth-protected-resource` (RFC 8705)
- `POST /oauth/register` (protected - Master API Key required)
- `GET /oauth/authorize` - Authorization endpoint (API Key required)
- `POST /oauth/token` - Token exchange (all grant types)

**Security Features:**
- Protected client registration (Master API Key required)
- API Key authorization mode (OAUTH_AUTH_MODE=required)
- Refresh token rotation (prevents reuse)
- Authorization code single-use (prevents replay)
- PKCE mandatory (prevents CSRF)
- API Key permission inheritance

**OAuth Tools (3 new tools):**
- `oauth_register_client` - Register new OAuth clients
- `oauth_list_clients` - List all registered clients
- `oauth_revoke_client` - Revoke client access

**ChatGPT Integration:**
- OAuth (manual) mode support
- Admin registers client with Master API Key
- Users authorize with their own API Keys
- Enhanced security - no open registration

**Documentation:**
- Complete OAuth guide (`docs/OAUTH_GUIDE.md` - ~650 lines)
- Environment configuration examples
- Security model documentation

**Tool Count**: 133 → 136 tools (+3 OAuth tools)

**Commits**: Multiple commits (2025-11-18, updated 2025-11-19)

---

## [Unreleased] - 2025-11-11

### 🔄 Architecture Refactoring (Option A)

**BREAKING CHANGE**: Removed per-site tools to prevent tool explosion.

#### Changed
- **Architecture**: Migrated from Hybrid to Unified-Only architecture
- **Tool Count**: Reduced from 390 to ~105 tools (constant regardless of site count)
- **Scalability**: Now supports unlimited sites without tool explosion
  - 1 site: 105 tools (was 200)
  - 10 sites: 105 tools (was 1055)
  - 100 sites: 105 tools (was 9600+)

#### Technical Details
- Per-site tools (e.g., `wordpress_site1_get_post`) are no longer registered
- Only unified tools (e.g., `wordpress_get_post(site="site1")`) are exposed
- Plugin infrastructure remains intact for internal use
- Site aliases continue to work seamlessly

#### Migration
- **Non-breaking for new users**: Use unified tools from the start
- **For existing integrations**: Update tool calls to use `site` parameter
  - Before: `wordpress_site1_get_post(post_id=123)`
  - After: `wordpress_get_post(site="site1", post_id=123)`

**Files Modified**:
- `server.py`: Removed per-site tool registration
- `MASTER_CONTEXT.md`: Updated architecture documentation
- `README.md`: Updated tool count and features

**Next Steps**: Option B (complete architectural cleanup) planned for separate branch.

---

## [1.0.0] - 2025-11-11 (Planned)

### 🎉 Initial Public Release

This will be the first stable release of MCP Hub, featuring comprehensive WordPress and WooCommerce management through MCP protocol.

### ✨ Added

#### Core Features
- **~105 MCP Tools** with unified architecture (constant tool count!)
- **Unified Architecture**: Context-based tools for efficient scaling
- **Site Registry**: Friendly aliases for projects (e.g., "plantup" → site2)
- **Multi-language Support**: Full bilingual documentation (English/Persian)

#### WordPress Management (Phase 1-3)
- **Posts Management**: Create, read, update, delete posts
- **Pages Management**: Full CRUD operations for pages
- **Media Library**: Upload, manage, and delete media files
- **Comments**: Moderate and manage comments
- **Categories & Tags**: Taxonomy management
- **Users**: User information and authentication
- **Plugins & Themes**: List and inspect installed plugins/themes
- **Site Settings**: Read WordPress configuration
- **Site Health**: Check WordPress accessibility

**Commits**:
- `9881838`: feat(wordpress): implement core WordPress tools (Phase 1)
- `ad26cdc`: feat(wordpress): add media, comments, and taxonomy tools (Phase 2)
- `e7ac72d`: feat(wordpress): complete users, plugins, themes, and settings (Phase 3)

#### WooCommerce Integration (Phase 4-5)
- **Products**: Full product lifecycle management
- **Product Variations**: Variable product support
- **Product Categories & Tags**: Product taxonomy management
- **Product Attributes**: Global attributes for variations
- **Coupons**: Discount code management
- **Orders**: Order processing and status updates
- **Customers**: Customer data management
- **Reports**: Sales, top sellers, and customer analytics

**Commits**:
- `cda10fb`: feat(woocommerce): implement products, categories, and coupons (Phase 4)
- `0ffe5ad`: feat(woocommerce): add orders, customers, and reports (Phase 5)

#### WP-CLI & SEO Tools (Phase 6)
- **Cache Management**: Flush object cache, check cache type
- **Transients**: List and delete transients
- **Database**: Health checks, optimization, export
- **Plugin Management**: List, verify checksums, update plugins
- **Theme Management**: List, verify, update themes
- **Core Management**: Verify and update WordPress core
- **Search & Replace**: Dry-run database migrations
- **SEO Metadata**: Rank Math & Yoast SEO integration
- **Navigation Menus**: Menu and menu item management
- **Custom Post Types**: List and manage custom post types
- **Custom Taxonomies**: Taxonomy term management

**Commits**:
- `e5aaa97`: feat(wp-cli): implement WP-CLI integration (Phase 6)
- `e5aaa97`: feat(seo): add SEO metadata management tools (Phase 6)

#### Hybrid Architecture (Phase 7.0)
- **Site Registry System**: Central site configuration management
- **Unified Tool Generator**: Context-based tools with site parameter
- **Per-Site Tools**: Backward-compatible legacy tools
- **Tool Aliases**: Support for friendly project names
- **Plugin Architecture**: Extensible plugin system

**Commit**: `b638d4a`: feat(architecture): implement hybrid dual-tool architecture (Phase 7.0)

#### Security & Monitoring (Phase 7.1-7.3)
- **Audit Logging** (Phase 7.1):
  - GDPR-compliant structured logging
  - Sensitive data filtering (passwords, API keys)
  - JSON format for easy parsing
  - Automatic log rotation

- **Health Monitoring** (Phase 7.2):
  - Real-time system metrics
  - Response time tracking
  - Error rate monitoring
  - Historical metrics (1-24 hours)
  - Alert thresholds
  - Export functionality

- **Rate Limiting** (Phase 7.3):
  - Token bucket algorithm
  - 60 req/min, 1000 req/hour, 10000 req/day
  - Per-client tracking
  - Automatic throttling
  - Statistics and monitoring

**Commits**:
- `003ee0f`: feat(audit): implement GDPR-compliant audit logging (Phase 7.1)
- `796c8e0`: feat(health): implement enhanced health monitoring (Phase 7.2)
- `9297f20`: feat(rate-limiting): implement rate limiting & throttling (Phase 7.3)

#### Documentation
- **README.md**: Bilingual project introduction
- **CONTRIBUTING.md**: Simplified contribution guide
- **SECURITY.md**: Security policy with OWASP compliance
- **MASTER_CONTEXT.md**: Comprehensive project reference
- **Development Documentation**: Architecture and deployment guides

### 🔒 Security
- API key authentication for WordPress and WooCommerce
- Password filtering in logs
- Input validation and schema checking
- Docker security hardening
- OWASP Top 10 2025 compliance
- Regular dependency updates

### 🏗️ Infrastructure
- **Docker Support**: Production-ready Docker Compose setup
- **Coolify Integration**: One-click deployment support
- **Environment Variables**: Secure configuration management
- **Health Checks**: Automated container health monitoring
- **Log Management**: Structured logging with rotation

### 🧪 Testing
- **40 Tests**: Comprehensive test suite
- **75%+ Coverage**: Unit, integration, and E2E tests
- **pytest Framework**: Modern Python testing
- **Mock Support**: Isolated testing with pytest-mock
- **Async Testing**: Full async/await test support

### 📊 Statistics
- **390 Total Tools**: 285 per-site + 95 unified + 10 system
- **3 WordPress Sites**: Configured and tested
- **8 Development Phases**: From inception to production
- **19 Commits**: Clean development history

### 🔧 Technical Details
- **Python 3.11+**: Modern async/await support
- **FastMCP Framework**: MCP protocol implementation
- **httpx**: Async HTTP client
- **Docker Compose**: Container orchestration
- **pytest**: Testing framework

---

## Development History

### Phase 7.3 - Rate Limiting & Throttling
**Date**: 2025-11-11
**Status**: ✅ Complete

Added rate limiting system with token bucket algorithm to prevent API abuse.

**Changes**:
- Implemented `RateLimiter` class with token bucket algorithm
- Added per-client request tracking
- Configurable limits (per-minute, per-hour, per-day)
- Rate limit statistics endpoint
- Rate limit reset functionality
- Integration with all tool handlers
- Comprehensive testing

**Tools Added**: 2 (get_rate_limit_stats, reset_rate_limit)

### Phase 7.2 - Enhanced Health Monitoring
**Date**: 2025-11-10
**Status**: ✅ Complete

Enhanced health monitoring system with detailed metrics and historical tracking.

**Changes**:
- Response time tracking per project
- Error rate calculation
- Historical metrics storage (up to 24 hours)
- Alert threshold system
- Health metrics export
- System-wide statistics
- Project-specific health endpoints

**Tools Added**: 5 (check_all_projects_health, get_project_health, get_system_metrics, get_system_uptime, get_project_metrics, export_health_metrics)

### Phase 7.1 - Audit Logging
**Date**: 2025-11-09
**Status**: ✅ Complete

Implemented GDPR-compliant audit logging system with sensitive data filtering.

**Changes**:
- Structured JSON logging
- GDPR compliance (PII filtering)
- Password and API key filtering
- Log rotation configuration
- User action tracking
- Security event logging
- Timezone-aware timestamps

### Phase 7.0 - Hybrid Architecture
**Date**: 2025-11-08
**Status**: ✅ Complete

Major architectural refactor introducing dual tool system.

**Changes**:
- Site Registry system
- Unified tool generator
- Plugin architecture
- Per-site tool preservation (backward compatibility)
- Site alias support
- Dynamic tool registration

**Tools Added**: 95 unified tools (matching per-site tools)

### Phase 6 - WP-CLI & Advanced Features
**Date**: 2025-11-05
**Status**: ✅ Complete

Added WP-CLI integration and advanced WordPress features.

**Changes**:
- Cache management (flush, type)
- Transient management
- Database operations (check, optimize, export)
- Plugin checksums verification
- Core file verification
- Search & replace (dry-run only)
- Plugin/theme/core updates (with dry-run mode)
- SEO metadata management (Rank Math & Yoast)
- Navigation menu management
- Custom post types support
- Custom taxonomies support

**Tools Added per Site**: 19

### Phase 5 - WooCommerce Orders & Customers
**Date**: 2025-11-03
**Status**: ✅ Complete

Extended WooCommerce support with order and customer management.

**Changes**:
- Order listing with filters
- Order details retrieval
- Order status updates
- Order creation
- Order deletion
- Customer listing
- Customer details
- Customer creation/updates

**Tools Added per Site**: 8

### Phase 4 - WooCommerce Products & Reports
**Date**: 2025-11-02
**Status**: ✅ Complete

Added comprehensive WooCommerce product management and reporting.

**Changes**:
- Product CRUD operations
- Product categories and tags
- Product attributes
- Product variations
- Coupon management
- Sales reports
- Top sellers analytics
- Customer statistics

**Tools Added per Site**: 20

### Phase 3 - WordPress Extended Features
**Date**: 2025-11-01
**Status**: ✅ Complete

Completed core WordPress functionality.

**Changes**:
- User management
- Plugin listing
- Theme management
- Site settings access
- Site health checks

**Tools Added per Site**: 5

### Phase 2 - WordPress Media & Taxonomy
**Date**: 2025-10-31
**Status**: ✅ Complete

Extended WordPress tools with media and taxonomy support.

**Changes**:
- Media library management
- Media upload from URL
- Media metadata updates
- Comment moderation
- Category management
- Tag management

**Tools Added per Site**: 6

### Phase 1 - Core WordPress Tools
**Date**: 2025-10-30
**Status**: ✅ Complete

Initial implementation of WordPress management tools.

**Changes**:
- Post management (CRUD)
- Page management (CRUD)
- Basic MCP server setup
- Environment configuration
- Docker Compose setup

**Tools Added per Site**: 6

---

---

## [Unreleased]

### 🔮 Planned for Phase 2

#### Gitea Integration (Priority)
- Repository management
- Issue tracking
- Pull request operations
- Webhook management
- User and team management

#### Supabase Integration
- Database operations
- Authentication management
- Storage management
- Real-time subscriptions
- Edge functions

#### Migration Tools
- WordPress to Supabase migration
- Data export/import utilities
- Schema generation

---

[1.0.0]: https://github.com/airano-ir/mcphub/releases/tag/v1.0.0
[Unreleased]: https://github.com/airano-ir/mcphub/compare/v1.0.0...HEAD
