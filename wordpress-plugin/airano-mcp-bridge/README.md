# Airano MCP Bridge

**Version:** 2.9.0
**Requires WordPress:** 5.0+
**Tested up to:** 6.9
**Requires PHP:** 7.4+
**License:** GPLv2 or later
**Plugin slug:** `airano-mcp-bridge` (permanent)

> Companion plugin for [MCP Hub](https://github.com/airano-ir/mcphub) — the AI-native management hub for WordPress, WooCommerce, and self-hosted services.

## What this plugin does

MCP Hub lets AI assistants (Claude, ChatGPT, Cursor, VS Code Copilot, …) manage your WordPress site through the Model Context Protocol. The core features work against the stock `/wp-json/wp/v2/` REST endpoints — **you do not need this plugin to use MCP Hub**.

Installing **Airano MCP Bridge** unlocks a second tier of capabilities that WordPress's built-in REST API can't reach on its own:

- **Large-file uploads** that bypass `upload_max_filesize`
- **One-round-trip upload + metadata + attach + set-featured** (v2.9.0)
- **Thumbnail regeneration** (no WP-CLI / SSH)
- **Cache purge** for 6 major cache plugins (LiteSpeed, WP Rocket, W3TC, WP Super Cache, WP Fastest Cache, SG Optimizer)
- **Transient cleanup** (expired / all / pattern)
- **Bulk post-meta writes** in a single REST round-trip
- **Unified site-health snapshot** (5+ stock calls → 1)
- **Structured JSON export** (posts / pages / products + media + terms + meta)
- **Capability probe** — tells MCP Hub what the calling application password can actually do
- **Audit hook** — forwards WordPress action events to MCP Hub with HMAC-signed webhooks
- **SEO meta routes** for Rank Math and Yoast

All operations remain guarded by WordPress's own capability system — this plugin never bypasses auth.

## Installation

1. Download `airano-mcp-bridge.zip` from the MCP Hub release page.
2. In WP Admin → **Plugins → Add New → Upload Plugin**, choose the zip and **Activate**.
3. Generate an **Application Password** under Users → Profile (scroll to bottom).
4. In MCP Hub dashboard → **My Sites**, add your WordPress site using that Application Password.

The plugin works out of the box. There are no settings pages to configure; behavior is controlled entirely through the REST API.

## REST API endpoints

### SEO meta (namespace `airano-mcp-bridge/v1`)

- `GET / POST /posts/{id}/seo` — Post SEO data (Rank Math or Yoast, auto-detected)
- `GET / POST /pages/{id}/seo` — Page SEO data
- `GET / POST /products/{id}/seo` — WooCommerce product SEO data
- `GET /status` — Plugin status + active SEO plugins list

### MCP Bridge helpers (namespace `airano-mcp/v1`)

| Route | Method | Introduced | Purpose |
|---|---|---|---|
| `/upload-limits` | GET | 2.0.0 | Returns effective PHP + WP upload limits so MCP Hub can pick the right upload path |
| `/upload-chunk` | POST | 2.0.0 | Raw-body upload that bypasses `upload_max_filesize` (still bounded by `post_max_size`) |
| `/upload-and-attach` | POST | 2.9.0 | Same as `/upload-chunk` plus query-param metadata (`attach_to_post`, `set_featured`, `title`, `alt_text`, `caption`, `description`) — collapses 3 REST round-trips into 1 |
| `/capabilities` | GET | 2.1.0 | Effective capabilities of the calling Application Password + feature flags + available routes |
| `/bulk-meta` | POST | 2.2.0 | Batch `post_meta` writes in one request (max 500 items, per-item permission check) |
| `/export` | GET | 2.3.0 | Structured JSON export of posts / pages / products + media + terms + meta, with `post_type` / `status` / `since` / `limit` / `offset` paging |
| `/cache-purge` | POST | 2.4.0 | Auto-detects LiteSpeed, WP Rocket, W3 Total Cache, WP Super Cache, WP Fastest Cache, SiteGround Optimizer and triggers each one's purge API; always flushes object cache |
| `/transient-flush` | POST | 2.5.0 | Native transient cleanup with `expired` / `all` / `pattern` scopes; optional site-transient handling for multisite |
| `/site-health` | GET | 2.6.0 | Single-envelope health snapshot: WP/PHP/MySQL versions, disk free, active plugins, theme, writability, SSL — replaces 5+ stock calls |
| `/audit-hook` | GET / POST / DELETE | 2.7.0 | Configure a webhook that forwards WP action events to MCP Hub. HMAC-SHA256-signed, non-blocking |
| `/regenerate-thumbnails` | POST | 2.8.0 | Rebuild attachment sub-sizes via `wp_generate_attachment_metadata()` for a list of IDs or in paged batch mode |

### Authentication

All routes require **HTTP Basic** authentication with a WordPress **Application Password** (Users → Profile → Application Passwords). Per-route capability requirements:

| Route family | Required capability |
|---|---|
| SEO meta (read/write) | `edit_posts` |
| Upload helpers | `upload_files` or `manage_options` |
| Capabilities probe | `read` (any logged-in user) |
| Bulk meta, Export | `edit_posts` (per-item `edit_post` check) |
| Cache purge, Transient flush, Site health, Audit hook, Regenerate thumbnails | `manage_options` |

## Privacy

This plugin makes **no outbound network calls** on its own. It exposes authenticated REST API endpoints that your MCP Hub instance calls into. The audit-hook route **only** sends webhooks when you explicitly configure it (POST to `/audit-hook` with an endpoint URL + secret); without that configuration, zero telemetry leaves your WordPress.

No analytics, no phone-home, no cloud relay.

## Security notes

- All write routes enforce capability checks.
- Raw-body uploads go through `wp_handle_sideload()` which respects WordPress's allowed-MIME list.
- Bulk meta writes check `current_user_can('edit_post', $post_id)` per item, not just per batch.
- Audit-hook secrets are stored in `wp_options` and never echoed in responses (only the last 4 characters are returned on read).
- Audit-hook webhooks are signed with HMAC-SHA256 so MCP Hub can verify the message came from your site and hasn't been tampered with.

If you find a security issue, please report it privately to the maintainers at the [GitHub issues page](https://github.com/airano-ir/mcphub/issues) rather than filing a public issue.

## Frequently asked questions

### Do I need MCP Hub to use this plugin?

No. Every route is a standard authenticated WordPress REST endpoint and can be called from any HTTP client (curl, Postman, a custom integration). MCP Hub is the reference consumer but not a requirement.

### Which SEO plugins are supported?

**Rank Math SEO** and **Yoast SEO**. The plugin auto-detects which is active and routes SEO-meta calls accordingly.

### Does this plugin work on multisite?

Yes. Route registration, capability checks, and transient flushing all respect multisite boundaries. The optional `include_site_transients` flag on `/transient-flush` handles site transients on multisite setups.

### Why keep the folder name `airano-mcp-bridge` even though the plugin now does much more than SEO?

Plugin slugs on WordPress.org are permanent once registered. Existing installs keep working; display name, description, and feature surface are what we can update.

### What happens if I uninstall?

Uninstall removes plugin options including the audit-hook secret and endpoint. Media uploaded via the plugin stays in your media library (it's regular WordPress attachments — the plugin just provides the upload pipeline).

### How large a file can I upload?

The `/upload-chunk` route bypasses PHP's `upload_max_filesize` (typically 2–64 MB on shared hosting), but is still bounded by `post_max_size` and `memory_limit`. For files larger than `post_max_size`, MCP Hub falls back to its own server-side chunked session pipeline that reassembles chunks before handing the full file to this route.

## Changelog

### 2.9.0 — 2026-04-16

- New: `POST /airano-mcp/v1/upload-and-attach` — raw-body upload + metadata (title / alt / caption / description) + attach-to-post + set-featured in a single REST round-trip. Saves 2–3 calls for every hero-image or product-image workflow. Per-target permission enforced via `current_user_can('edit_post', attach_to_post)`.
- Status + capabilities payloads now advertise `upload_and_attach: true` + `regenerate_thumbnails: true`.

### 2.8.0 — 2026-04-15

- New: `POST /airano-mcp/v1/regenerate-thumbnails` — rebuild attachment sub-sizes via `wp_generate_attachment_metadata()` after uploads, theme switches, or format conversions. Two modes: `{ "ids": [...] }` for targeted regeneration (max 50/call) or `{ "all": true, "offset": N, "limit": M }` for paged batches.

### 2.7.0

- New: `GET|POST|DELETE /airano-mcp/v1/audit-hook` — configure a webhook that forwards WP action events (`transition_post_status`, `deleted_post`, `user_register`, `profile_update`, `deleted_user`, `activated_plugin`, `deactivated_plugin`, `switch_theme`) to MCP Hub. HMAC-SHA256-signed, non-blocking `wp_remote_post`. Permission: `manage_options`.

### 2.6.0

- New: `GET /airano-mcp/v1/site-health` — single-envelope snapshot: WP version / multisite / locale, PHP version + extensions, server software + disk free, MySQL/MariaDB version + charset, active plugins + theme, writability checks (wp-content, uploads) + SSL.

### 2.5.0

- New: `POST /airano-mcp/v1/transient-flush` — native transient cleanup. Scopes: `expired` (default), `all`, or `pattern` (glob match, e.g. `rank_math_*`). Optional `include_site_transients` for multisite.

### 2.4.0

- New: `POST /airano-mcp/v1/cache-purge` — auto-detects active page-cache plugins (LiteSpeed, WP Rocket, W3 Total Cache, WP Super Cache, WP Fastest Cache, SiteGround Optimizer) and invokes each one's purge API. Always calls `wp_cache_flush()` for object caches.

### 2.3.0

- New: `GET /airano-mcp/v1/export` — structured JSON export (not WXR). Query params: `post_type`, `status`, `since`, `limit` (max 500), `offset`, `include_media`, `include_terms`, `include_meta`.

### 2.2.0

- New: `POST /airano-mcp/v1/bulk-meta` — batch post-meta writes (max 500 items per call). Per-item permission check via `current_user_can('edit_post', $post_id)`. Null meta values delete the key.

### 2.1.0

- New: `GET /airano-mcp/v1/capabilities` — reports the effective capabilities of the calling Application Password plus feature flags (Rank Math / Yoast / WooCommerce / multisite) and the list of companion routes this version ships. Consumed by MCP Hub's F.7e capability probe.

### 2.0.0

- **Rebrand**: "Airano MCP SEO Meta Bridge" → "Airano MCP Bridge". No longer SEO-only.
- New: `GET /airano-mcp/v1/upload-limits` — returns effective PHP + WP upload limits.
- New: `POST /airano-mcp/v1/upload-chunk` — raw-body upload route that bypasses `upload_max_filesize`.

### 1.3.0

- Added REST API endpoints for posts, pages, and products (GET/POST operations).
- Added authentication requirement for all endpoints (edit_posts).
- Fixed `rank_math_title` meta key registration.

### 1.2.0

- Enhanced WooCommerce product support.
- Improved MariaDB compatibility.

### 1.1.0

- Added status endpoint for plugin detection.
- Improved error handling.

### 1.0.0

- Initial release with Rank Math and Yoast SEO support.

## Upgrade notice

### 2.9.0

Adds `POST /airano-mcp/v1/upload-and-attach` — upload + metadata + attach + featured in one REST round-trip. No breaking changes to existing routes.

## Credits

Built by the [MCP Hub](https://github.com/airano-ir/mcphub) project. Contributions welcome — see the parent repository for contribution guidelines.
