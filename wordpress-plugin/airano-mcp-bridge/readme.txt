=== Airano MCP Bridge ===
Contributors: airano
Tags: mcp, ai, rest-api, seo, media
Requires at least: 5.0
Tested up to: 6.9
Requires PHP: 7.4
Stable tag: 2.9.0
License: GPLv2 or later
License URI: https://www.gnu.org/licenses/gpl-2.0.html

Companion plugin for MCP Hub. REST API routes for SEO meta and raw-binary media uploads that bypass upload_max_filesize.

== Description ==

**Airano MCP Bridge** is the official companion plugin for [MCP Hub](https://github.com/airano-ir/mcphub) — the AI-native management hub for WordPress, WooCommerce, and self-hosted services. It extends the WordPress REST API with dedicated routes that AI agents (Claude, ChatGPT, Cursor, VS Code Copilot) and the MCP Hub server rely on:

* **SEO meta routes** — read and write Rank Math SEO and Yoast SEO metadata for posts, pages, and WooCommerce products.
* **Media upload helper routes** — accept raw-binary uploads via `php://input`, which bypasses the `upload_max_filesize` PHP limit (still bounded by `post_max_size`). Unlocks reliable hero-image and large-asset uploads for AI-agent workflows.
* **Capability probe** — reports the effective PHP + WordPress upload limits so MCP Hub can pick the right upload path automatically.

**Features:**

* **Rank Math SEO Support** — Full access to all Rank Math meta fields
* **Yoast SEO Support** — Full access to all Yoast SEO meta fields
* **WooCommerce Compatible** — Works with product post types
* **MCP Hub media pipeline** — bypasses `upload_max_filesize` for AI-agent uploads
* **Secure** — Requires WordPress Application Password + capability checks on every route
* **Auto-Detection** — Automatically detects active SEO plugin and advertises capabilities
* **Zero Configuration** — Works out of the box after activation

**REST API Endpoints:**

*SEO meta (namespace `airano-mcp-bridge/v1`)*

* `GET/POST /wp-json/airano-mcp-bridge/v1/posts/{id}/seo` — Post SEO data
* `GET/POST /wp-json/airano-mcp-bridge/v1/pages/{id}/seo` — Page SEO data
* `GET/POST /wp-json/airano-mcp-bridge/v1/products/{id}/seo` — Product SEO data (WooCommerce)
* `GET /wp-json/airano-mcp-bridge/v1/status` — Plugin status + active SEO plugins

*MCP Bridge helpers (namespace `airano-mcp/v1`, added in 2.0.0)*

* `GET /wp-json/airano-mcp/v1/upload-limits` — Effective PHP + WP upload limits
* `POST /wp-json/airano-mcp/v1/upload-chunk` — Raw-body media upload (bypasses `upload_max_filesize`)
* `GET /wp-json/airano-mcp/v1/capabilities` — Effective capabilities + feature flags + available routes (added in 2.1.0)
* `POST /wp-json/airano-mcp/v1/bulk-meta` — Batch post/product meta writes in a single HTTP round-trip (added in 2.2.0)
* `GET /wp-json/airano-mcp/v1/export` — Structured JSON export: posts, pages, products + media + terms + meta, with post_type/status/since/limit/offset paging (added in 2.3.0)
* `POST /wp-json/airano-mcp/v1/cache-purge` — Auto-detects active cache plugins (LiteSpeed, WP Rocket, W3TC, Super Cache, Fastest Cache, SG Optimizer) and invokes their purge API; always flushes object cache (added in 2.4.0)
* `POST /wp-json/airano-mcp/v1/transient-flush` — Native transient cleanup with scope=expired/all/pattern (glob); optional site-transient handling on multisite (added in 2.5.0)
* `GET /wp-json/airano-mcp/v1/site-health` — Unified site-health snapshot: PHP/MySQL/WP versions, extensions, disk free, active plugins + theme, writability checks (added in 2.6.0)
* `GET|POST|DELETE /wp-json/airano-mcp/v1/audit-hook` — Configure + query a webhook that forwards WordPress action events to MCP Hub (HMAC-SHA256 signed, non-blocking) (added in 2.7.0)
* `POST /wp-json/airano-mcp/v1/regenerate-thumbnails` — Regenerate attachment sub-sizes via `wp_generate_attachment_metadata` for a list of IDs or in paged batch mode (added in 2.8.0)
* `POST /wp-json/airano-mcp/v1/upload-and-attach` — Raw-body upload + metadata + attach-to-post + set-featured in a single REST call (added in 2.9.0). Query params: `attach_to_post`, `set_featured`, `title`, `alt_text`, `caption`, `description`. Permission: `upload_files` + `edit_post` on the target post.

**Designed for [MCP Hub](https://github.com/airano-ir/mcphub)** — the AI-native management hub for WordPress and self-hosted services.

== Installation ==

1. Upload the `airano-mcp-bridge` folder to `/wp-content/plugins/`
2. Activate the plugin through the 'Plugins' menu in WordPress
3. For SEO meta routes: ensure either Rank Math SEO or Yoast SEO is active
4. The REST API endpoints are now available

== Frequently Asked Questions ==

= Which SEO plugins are supported? =

Rank Math SEO and Yoast SEO. The plugin auto-detects which one is active.

= Does it work with WooCommerce? =

Yes. Product SEO endpoints are available when WooCommerce is active.

= How is authentication handled? =

All endpoints require WordPress Application Password authentication. SEO routes require `edit_posts`. Upload helper routes require `upload_files` or `manage_options`.

= Do I need MCP Hub to use the upload helper routes? =

No. The `/airano-mcp/v1/upload-chunk` route is a standard authenticated REST endpoint and can be used from any client that can send a raw-binary `POST` with `Content-Disposition` and `Content-Type` headers.

= Is there a size cap on the upload helper? =

The helper reads the request body via `php://input`, which is **not** subject to PHP's `upload_max_filesize` limit — but it is still bounded by `post_max_size` and `memory_limit`. For files larger than `post_max_size`, MCP Hub falls back to its own server-side chunked session pipeline.

= Why keep the folder name "airano-mcp-bridge" even though the plugin now does more than SEO? =

Plugin slugs on wordpress.org are permanent. Existing installs keep working; the display name and feature set are updated in 2.0.0.

= Can I use this without MCP Hub? =

Yes. All REST API endpoints work with any application that can make authenticated HTTP requests.

== Changelog ==

= 2.9.0 =
* Added `POST /wp-json/airano-mcp/v1/upload-and-attach` — same raw-body semantics as `/upload-chunk`, but accepts query params (`attach_to_post`, `set_featured`, `title`, `alt_text`, `caption`, `description`) and applies them in one PHP round-trip. Saves 2-3 REST calls per upload. Per-target permission enforced via `current_user_can('edit_post', attach_to_post)`.
* `status` + `capabilities` routes now advertise `upload_and_attach: true` alongside the existing capability flags.

= 2.8.0 =
* Added `POST /wp-json/airano-mcp/v1/regenerate-thumbnails` — rebuild attachment sub-sizes via `wp_generate_attachment_metadata()` after an upload or format conversion changes source pixels. Supports two modes: `{ "ids": [...] }` for targeted regeneration (up to 50 per call) and `{ "all": true, "offset": N, "limit": M }` for paged batches (max 50 per page, with `has_more` + `next_offset` for pagination). Non-image attachments are skipped; per-item permission check via `current_user_can('edit_post', $attachment_id)`. Permission: `upload_files` or `manage_options`.

= 2.7.0 =
* Added `GET|POST|DELETE /wp-json/airano-mcp/v1/audit-hook` — configure a webhook that forwards WordPress action events (post transitions, deletions, user events, plugin activations, theme switches) to MCP Hub for unified auditing. Each event is signed with HMAC-SHA256 using a shared secret and posted non-blocking via `wp_remote_post` so the admin UI stays snappy. Secret is stored in `wp_options` and never echoed back in GET responses (only the last 4 characters are returned). Permission: `manage_options`.

= 2.6.0 =
* Added `GET /wp-json/airano-mcp/v1/site-health` — single-envelope health snapshot: WordPress version/multisite/locale, PHP version + critical extensions, server software + disk free, MySQL/MariaDB version + charset, active plugins list (with versions), active + parent theme, writability checks (wp-content, uploads) and SSL status. Replaces 5+ separate REST calls with a single request. Permission: `manage_options`.

= 2.5.0 =
* Added `POST /wp-json/airano-mcp/v1/transient-flush` — native PHP transient cleanup. Scopes: `expired` (default, calls `delete_expired_transients()`), `all` (delete every `_transient_%` row), or `pattern` (glob match, e.g. `rank_math_*`). Optional `include_site_transients` for multisite. Response includes `deleted_count` + capped `deleted_sample` for observability. Permission: `manage_options`.

= 2.4.0 =
* Added `POST /wp-json/airano-mcp/v1/cache-purge` — auto-detects active page-cache plugins (LiteSpeed Cache, WP Rocket, W3 Total Cache, WP Super Cache, WP Fastest Cache, SiteGround Optimizer) and triggers their purge API. Always calls `wp_cache_flush()` for object caches. Permission: `manage_options`. Removes the need for Docker-socket + WP-CLI to flush caches on managed hosts.

= 2.3.0 =
* Added `GET /wp-json/airano-mcp/v1/export` — structured JSON export of posts, pages, and WooCommerce products (not WXR). Query params: `post_type`, `status`, `since`, `limit` (max 500), `offset`, `include_media`, `include_terms`, `include_meta`. Response includes posts + referenced media + taxonomy terms + post meta in a single envelope, plus `has_more` / `next_offset` for pagination. Permission: `edit_posts`.

= 2.2.0 =
* Added `POST /wp-json/airano-mcp/v1/bulk-meta` — writes many `post_meta` / `product_meta` entries in a single REST request. Capped at 500 items per call; each item is permission-checked via `current_user_can('edit_post', $post_id)`. Null meta values delete the key. Status endpoint now advertises `capabilities.bulk_meta = true` and the capabilities probe reports `routes.bulk_meta = true`.

= 2.1.0 =
* Added `GET /wp-json/airano-mcp/v1/capabilities` — reports the effective capabilities of the calling application password, plus feature flags (Rank Math / Yoast / WooCommerce / multisite) and the list of companion routes this version actually ships. Consumed by MCP Hub's capability probe so per-user clients only see tools they're actually authorised to use.
* Status endpoint now advertises `capabilities.capabilities = true`.

= 2.0.0 =
* **Rebrand**: "Airano MCP SEO Meta Bridge" → "Airano MCP Bridge". The companion plugin is no longer SEO-only.
* Added `GET /wp-json/airano-mcp/v1/upload-limits` — returns effective PHP + WP upload limits for MCP Hub probes.
* Added `POST /wp-json/airano-mcp/v1/upload-chunk` — raw-body upload route that bypasses `upload_max_filesize`.
* Status endpoint now includes `capabilities: { seo_meta, upload_limits, upload_chunk }`.
* Plugin folder / slug unchanged: `airano-mcp-bridge` (permanent on wordpress.org).

= 1.3.0 =
* Added REST API endpoints for posts, pages, and products (GET/POST operations)
* Added authentication requirement for all endpoints
* Fixed rank_math_title meta key registration

= 1.2.0 =
* Enhanced WooCommerce product support
* Improved MariaDB compatibility

= 1.1.0 =
* Added status endpoint for plugin detection
* Improved error handling

= 1.0.0 =
* Initial release with Rank Math and Yoast SEO support

== Upgrade Notice ==

= 2.9.0 =
Adds `POST /airano-mcp/v1/upload-and-attach` — upload + metadata + attach + featured in one REST round-trip. No breaking changes.

= 2.8.0 =
Adds `POST /airano-mcp/v1/regenerate-thumbnails` for rebuilding attachment sub-sizes after uploads or format changes. No breaking changes.

= 2.7.0 =
Adds `GET|POST|DELETE /airano-mcp/v1/audit-hook` to forward WordPress action events to MCP Hub. Disabled until configured. No breaking changes.

= 2.6.0 =
Adds `GET /airano-mcp/v1/site-health` for a unified site-health snapshot. No breaking changes.

= 2.5.0 =
Adds `POST /airano-mcp/v1/transient-flush` for native transient cleanup. No breaking changes.

= 2.4.0 =
Adds `POST /airano-mcp/v1/cache-purge` for native cache flushing. No breaking changes.

= 2.3.0 =
Adds `GET /airano-mcp/v1/export` for offline backups and migrations. No breaking changes.

= 2.2.0 =
Adds `POST /airano-mcp/v1/bulk-meta` so MCP Hub can write many post meta values in one request. No breaking changes.

= 2.1.0 =
Adds `GET /airano-mcp/v1/capabilities` so MCP Hub can probe which tools the current application password can actually use. No breaking changes; existing routes unchanged.

= 2.0.0 =
Rebranded to "Airano MCP Bridge". Adds new `airano-mcp/v1` namespace with upload-helper routes. All existing 1.x REST endpoints keep working unchanged.

= 1.3.0 =
GET endpoints now require authentication (edit_posts capability). Update your API clients if needed.
