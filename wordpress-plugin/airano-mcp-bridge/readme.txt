=== Airano MCP Bridge ===
Contributors: airano
Tags: mcp, ai, rest-api, seo, media
Requires at least: 5.0
Tested up to: 6.9
Requires PHP: 7.4
Stable tag: 2.18.1
License: GPLv2 or later
License URI: https://www.gnu.org/licenses/gpl-2.0.html

Companion plugin for MCP Hub. REST API routes for SEO meta, raw-binary media uploads that bypass upload_max_filesize, and the WordPress Specialist admin namespace.

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

*WordPress Specialist admin namespace (`airano-mcp/v1/admin/*`, added in 2.11.0–2.18.0)*

All admin routes require `manage_options`. They power the `wordpress_specialist` MCP plugin (companion-backed advanced WordPress management — no Docker socket required).

Read routes (2.11.0–2.14.0):

* `GET /wp-json/airano-mcp/v1/admin/plugins` — Every plugin known to WP with active/network-active/version/author/update flags (2.11.0)
* `GET /wp-json/airano-mcp/v1/admin/themes` — Installed themes with stylesheet/template/parent/block-theme/active flags (2.11.0)
* `GET /wp-json/airano-mcp/v1/admin/users?role=&search=&page=&per_page=` — Paginated user list (cap 200/call) (2.11.0)
* `GET /wp-json/airano-mcp/v1/admin/options/{name}` — Single option fetch with deny-list of credential-shaped keys (`*_secret`, `*_password`, `*_api_key`, `auth_*_key`, etc.) (2.11.0)
* `GET /wp-json/airano-mcp/v1/admin/cron` — Full cron table with epoch + ISO 8601 next_run, schedule slug, interval, args (2.11.0)
* `GET /wp-json/airano-mcp/v1/admin/maintenance` — `.maintenance` sentinel inspection (`enabled` / `started_at` / `stale`) (2.11.0)
* `GET /wp-json/airano-mcp/v1/admin/system-info` — WP/PHP/MySQL/server versions + memory + paths in one envelope (2.12.0)
* `GET /wp-json/airano-mcp/v1/admin/phpinfo` — Sorted extension list + curated ini whitelist + disabled functions + opcache state (2.12.0)
* `GET /wp-json/airano-mcp/v1/admin/disk-usage` — Bytes for uploads/plugins/themes + filesystem `disk_total/free/used` (bounded 200k files/5s per tree) (2.12.0)
* `GET /wp-json/airano-mcp/v1/admin/elementor/status` — Elementor presence + version + Pro flag + supported post types; `installed:false` cleanly when absent (2.13.0)
* `GET /wp-json/airano-mcp/v1/admin/elementor/{post_id}` — Parsed `_elementor_data` (slash-stripped, JSON-decoded) (2.13.0)
* `GET /wp-json/airano-mcp/v1/admin/elementor/templates` — Saved Elementor templates (id/title/type/modified) (2.13.0)
* `GET /wp-json/airano-mcp/v1/admin/themes/files/{slug}?glob=&max_files=` — Theme directory walk (path/size/mime/sha256/modified per file; capped at 1000 files/call) (2.14.0)
* `GET /wp-json/airano-mcp/v1/admin/themes/files/{slug}/{path}` — Single theme file as base64 + sha256 + mime (5 MB cap) (2.14.0)

Page-editing write routes (2.13.0). All require `manage_options` AND `edit_post` on the target post (S-12); block + classic content is sanitised via `wp_kses_post` unless the caller has `unfiltered_html` (S-13); Elementor JSON node count capped at 5,000 per call (S-14).

* `POST /wp-json/airano-mcp/v1/admin/blocks/replace` — Replace post block tree; companion runs `serialize_blocks()` server-side (max 200 blocks)
* `POST /wp-json/airano-mcp/v1/admin/blocks/insert` — Insert one block at index N
* `POST /wp-json/airano-mcp/v1/admin/blocks/remove` — Remove block at index N (returns the removed block for rollback)
* `POST /wp-json/airano-mcp/v1/admin/elementor/{post_id}` — Replace `_elementor_data`; fires `elementor/document/after_save`
* `POST /wp-json/airano-mcp/v1/admin/elementor/{post_id}/regen-css` — Trigger per-post Elementor CSS regeneration
* `POST /wp-json/airano-mcp/v1/admin/elementor/templates/apply` — Copy a saved template into a target post
* `POST /wp-json/airano-mcp/v1/admin/classic/{post_id}/replace` — Pure post_content swap for classic-editor sites

Theme dev write routes (2.14.0). Per-route capability checks layer on top of `manage_options`: `install_themes` for install, `switch_themes` for activate, `delete_themes` for theme delete, `edit_themes` for file CRUD. PHP file writes additionally require `!DISALLOW_FILE_EDIT` (S-17). theme_slug must match `wp_get_themes()` (S-15). File paths canonicalise via `realpath()` and must stay under `wp-content/themes/{slug}` (S-16). Caps: 5 MB/file, 50 MB/install zip (S-18). Optimistic concurrency on `expected_sha256` returns `sha_mismatch` (409) on drift (S-19).

* `POST /wp-json/airano-mcp/v1/admin/themes/install` — Install theme from `zip_url` or inline `zip_base64`; supports `activate` + `overwrite`. Companion runs WP core's `Theme_Upgrader`.
* `POST /wp-json/airano-mcp/v1/admin/themes/{slug}/activate` — Switch the active theme.
* `DELETE /wp-json/airano-mcp/v1/admin/themes/{slug}` — Delete an installed theme (refuses if active or active parent).
* `PUT /wp-json/airano-mcp/v1/admin/themes/files/{slug}/{path}` — Write a theme file (base64 body, optional `expected_sha256`, optional `create_dirs`).
* `DELETE /wp-json/airano-mcp/v1/admin/themes/files/{slug}/{path}` — Delete a theme file (refuses to delete `style.css` of the active theme).

Plugin write management routes (2.15.0). Per-route capability checks layer on `manage_options`: `install_plugins` for install / update, `activate_plugins` for activate / deactivate, `delete_plugins` for delete. New security rules: S-20 refuses to deactivate / delete the Airano MCP Bridge companion itself (would brick the MCP connection); S-21 refuses to deactivate / delete plugins marked `Required: yes` in their header. Reuses S-15 (slug whitelist via `get_plugins()`) + S-18 (50 MB cap on install zip).

* `POST /wp-json/airano-mcp/v1/admin/plugins/install` — Install via wp.org `slug`, OR via `zip_url`, OR via inline `zip_base64` (mutually exclusive). Supports `activate` + `overwrite`. Companion runs WP core's `Plugin_Upgrader`.
* `POST /wp-json/airano-mcp/v1/admin/plugins/{slug}/activate` — Activate an installed plugin. Optional `network_wide` for multisite.
* `POST /wp-json/airano-mcp/v1/admin/plugins/{slug}/deactivate` — Deactivate. Refuses companion (S-20) and `Required` plugins (S-21).
* `POST /wp-json/airano-mcp/v1/admin/plugins/{slug}/update` — Update to latest wp.org version. Returns `up_to_date:true` cleanly when no update available.
* `DELETE /wp-json/airano-mcp/v1/admin/plugins/{slug}` — Delete. Refuses active plugins, the companion, and `Required` plugins.

Site config routes (2.16.0). All gated on `manage_options`. Writes route every option through WP's own `sanitize_option_*` hooks; permalink writes additionally call `flush_rewrite_rules()`.

* `GET /wp-json/airano-mcp/v1/admin/site/identity` — title / tagline / site_icon / custom_logo / charset / WP version / admin_email / language / siteurl
* `POST /wp-json/airano-mcp/v1/admin/site/identity` — Update title / tagline / site_icon_id / custom_logo_id (any subset). Attachment ids are validated against the media library.
* `GET /wp-json/airano-mcp/v1/admin/site/reading` — show_on_front / page_on_front / page_for_posts / posts_per_page / posts_per_rss / blog_public
* `POST /wp-json/airano-mcp/v1/admin/site/reading` — Update reading settings. page_on_front / page_for_posts must reference published Pages.
* `GET /wp-json/airano-mcp/v1/admin/permalinks` — permalink_structure / category_base / tag_base
* `POST /wp-json/airano-mcp/v1/admin/permalinks` — Update permalink structure (empty string = plain). Calls `flush_rewrite_rules()` after the write so the new structure takes effect immediately.

Site layout routes (2.17.0). All gated on `manage_options`. Per-request capability checks layer on top per the new security rules: S-22 dispatches per nav-menu item type (`post_type` checks `read_post`; `taxonomy` allows public taxonomies and otherwise requires `assign_terms`; `custom` URL items skip the object check); S-23 sanitises widget HTML via `wp_kses_post` unless caller has `unfiltered_html`; S-24 customizer apply requires the `customize` cap (not just `manage_options`).

* `GET /wp-json/airano-mcp/v1/admin/menus` — Every nav menu with id / name / slug / theme locations / item count.
* `GET /wp-json/airano-mcp/v1/admin/menus/{menu_id}` — One menu's items: `{id, title, type, object, object_id, parent, order, url, target, classes, xfn}`.
* `PUT /wp-json/airano-mcp/v1/admin/menus/{menu_id}` — Full-replace items + optional rename. Slug stays frozen so theme_location mapping survives. Two-pass: every item validated against S-22 before any mutation.
* `GET /wp-json/airano-mcp/v1/admin/widgets/areas` — Every registered sidebar with id / name / theme_location / widget_count / kind (`block` or `legacy`).
* `GET /wp-json/airano-mcp/v1/admin/widgets/{area_id}` — One area's widgets. Block-kind returns `{id, type:'block', blocks: [...parsed], raw: '<!-- wp:... -->'}`; legacy-kind returns `{id, type, settings: {...}}` keyed by the widget's option store.
* `PUT /wp-json/airano-mcp/v1/admin/widgets/{area_id}` — Full replace. Block areas accept `{raw}` (or `{blocks}` server-serialised); legacy areas accept `text` widget settings only this round (other legacy types remain read-only). Caller-side `kind` is ignored — area kind is determined by the area itself.
* `POST /wp-json/airano-mcp/v1/admin/customizer/changeset` — `{action: get|apply|discard}`. `get` returns the pending changeset; `apply` publishes it; `discard` trashes it. Empty changeset returns `{status: 'empty'}` 200.

Database inspection routes (2.18.0). All gated on `manage_options`. New security rule S-25: db/search wraps `WP_Query` with `s=$query` (NEVER raw SQL); query is sanitised via `sanitize_text_field` and length-capped at 200 chars; `WP_Query`'s own `posts_clauses` filter (the same gate the WP search page uses) keeps non-readable posts out of the result set.

* `GET /wp-json/airano-mcp/v1/admin/db/size` — Aggregate database size. Single `information_schema.TABLES` aggregation scoped to the WP table prefix; returns `{database_bytes, table_count, row_count_estimate, database_name, table_prefix}`. No SQL exposure: caller doesn't pick the query.
* `GET /wp-json/airano-mcp/v1/admin/db/tables` — Per-table breakdown. Same source as `db/size`, one row per WP table; returns `{database_name, table_prefix, tables: [{name, engine, rows, data_bytes, index_bytes, total_bytes, collation}]}` ordered by total_bytes descending.
* `POST /wp-json/airano-mcp/v1/admin/db/search` — Full-text search wrapper around `WP_Query`. Body `{query, post_type?, status?, limit?}` (limit default 20, max 100). Returns `{query, limit, count, hits: [{id, post_type, status, title, snippet, url, modified}]}`.

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

= 2.18.1 =
* WordPress.org review fixes: drop the unused `wp-admin/includes/media.php` include from `/upload-chunk` and `/upload-and-attach` (only helpers from `file.php` and `image.php` are actually used). Split the `/upload-and-attach` permission_callback into its own method (`require_upload_and_attach_capability`) that explicitly checks `current_user_can('edit_post', $attach_to_post)` at the route gate when `attach_to_post` is supplied, and rejects `set_featured` without a target. The per-target check is no longer hidden inside the callback body.

= 2.18.0 =
* F.19.3.2-.3 — Database inspection (read) + bulk fan-out (write). Three new admin routes: `GET /admin/db/size` (single `information_schema.TABLES` aggregation: database_bytes + table_count + row_count_estimate, no SQL exposure), `GET /admin/db/tables` (per-table breakdown: name, engine, rows, data_bytes, index_bytes, total_bytes, collation), `POST /admin/db/search` body `{query, post_type?, status?, limit?}` wraps `WP_Query` with `s=$query` (NEVER raw SQL), `query` sanitised via `sanitize_text_field` and capped at 200 chars server-side, `limit` capped at 100. New security rule S-25 — db/search wraps `WP_Query`, never raw SQL; `posts_clauses` filter (same as the WP search page) keeps non-readable posts (private/draft from other authors) out of the result set. The bulk write tools (`wp_bulk_post_update`, `wp_bulk_term_update` on MCP Hub side) ride stock REST `wp/v2/posts/{id}` and `wp/v2/{taxonomy}/{id}` — no companion routes needed for those, but the cap of 50 items per call is documented under S-26 in the MCP Hub spec. All admin routes gated on `manage_options`. This release is bundled with the wordpress_advanced sunset on the MCP Hub side: the deprecated WP-CLI/Docker-socket plugin is removed in F.19.3.2-.3 (2026-05-04); `wordpress_specialist` is now the only WP-management surface.

= 2.17.0 =
* F.19.6.B — Site layout (menus + widgets + customizer). Adds seven new admin routes: `GET /admin/menus`, `GET /admin/menus/{id}`, `PUT /admin/menus/{id}` (full-replace items + optional rename, slug stays frozen), `GET /admin/widgets/areas`, `GET /admin/widgets/{area_id}`, `PUT /admin/widgets/{area_id}` (block areas accept any block raw HTML; legacy areas accept `text` widget settings only — other legacy types remain read-only this round), and `POST /admin/customizer/changeset` (single-tool wrapper around the changeset queue with `{action: get|apply|discard}`). New security rules: S-22 dispatches per nav-menu item type — `post_type` checks `current_user_can('read_post', id)`, `taxonomy` allows public taxonomies and otherwise requires the taxonomy's `assign_terms` cap (deliberately NOT `manage_categories` which is a write cap), `custom` URL items skip the object validation; refusals surface as `forbidden_object_id` 403/404. S-23 sanitises widget HTML via `wp_kses_post` unless the caller has `unfiltered_html` (mirrors S-13 from F.19.5). S-24 customizer apply requires the `customize` cap (same bar as `/wp-admin/customize.php`); `manage_options` alone is not enough. All routes gated on `manage_options`. Pre-validates every menu item before mutating so a partial S-22 failure leaves the menu untouched. Customizer apply is racy with concurrent edits via the customizer UI — intentional, mirrors WP behaviour.

= 2.16.0 =
* F.19.6.A — Site config surface. Six new admin routes covering Settings → General + Reading + Permalinks: `GET/POST /admin/site/identity` (title / tagline / site_icon / custom_logo), `GET/POST /admin/site/reading` (show_on_front / page_on_front / page_for_posts / posts_per_page / posts_per_rss / blog_public), `GET/POST /admin/permalinks` (permalink_structure / category_base / tag_base). All gated on `manage_options`. POST routes validate attachment ids against the media library, reject non-published page ids for page_on_front / page_for_posts, and route every option write through WP's own `sanitize_option_*` hooks. After a permalink_structure write `flush_rewrite_rules()` runs so the new structure takes effect immediately. First consumer of the `settings` tier introduced by F.19.2.0.

= 2.15.0 =
* F.19.2.1 — Plugin write management. Adds five new admin routes — `POST /admin/plugins/install` (accepts `{slug}` for wp.org install OR `{zip_url|zip_base64}` for arbitrary zip), `POST /admin/plugins/{slug}/activate`, `POST /admin/plugins/{slug}/deactivate`, `POST /admin/plugins/{slug}/update`, `DELETE /admin/plugins/{slug}`. Per-route capability checks: `install_plugins` (install / update), `activate_plugins` (activate / deactivate), `delete_plugins` (delete). New security rules: S-20 refuses to deactivate or delete the Airano MCP Bridge companion itself (would brick the MCP connection — operators must use WP-Admin → Plugins instead); S-21 refuses to deactivate / delete plugins marked `Required: yes` in their header (must-use plugins shipped by some managed hosts). Reuses S-15 (slug whitelist via `get_plugins()`) + S-18 (50 MB cap on install zip). Refuses to delete an active plugin (caller must deactivate first). Update route returns `up_to_date:true` cleanly when no update is available.

= 2.14.0 =
* F.19.7 — Theme dev surface (install + activate + delete + file CRUD). Adds three theme management routes — `POST /admin/themes/install` (accepts either `zip_url` or `zip_base64`; runs WP core's `Theme_Upgrader`), `POST /admin/themes/{slug}/activate`, `DELETE /admin/themes/{slug}` — and four file CRUD routes — `GET /admin/themes/files/{slug}` (glob walk capped at 1000 files), `GET /admin/themes/files/{slug}/{path}` (file read as base64), `PUT /admin/themes/files/{slug}/{path}` (file write with optional `expected_sha256` for optimistic concurrency), `DELETE /admin/themes/files/{slug}/{path}`. New security rules: `theme_slug` must match `wp_get_themes()` (S-15); paths canonicalise via `realpath()` and must stay under `wp-content/themes/{slug}`, blocking `..`, symlinks, absolute paths, null bytes (S-16); PHP file writes additionally require `!DISALLOW_FILE_EDIT` (S-17); per-call caps 5 MB/file, 1000 files/list, 50 MB/zip (S-18); optimistic concurrency via `expected_sha256` returns `sha_mismatch` (409) on drift (S-19). All routes gated on `manage_options` route-side; per-handler capability checks add `install_themes` / `switch_themes` / `delete_themes` / `edit_themes`. Refuses to delete the active theme, the active parent theme, or `style.css` of the active theme.

= 2.13.0 =
* F.19.5 — Page editing surface (Gutenberg + Elementor + Classic). Adds seven write routes — `POST /admin/blocks/{replace,insert,remove}`, `POST /admin/elementor/{post_id}` (set), `POST /admin/elementor/{post_id}/regen-css`, `POST /admin/elementor/templates/apply`, `POST /admin/classic/{post_id}/replace` — and three new read routes — `GET /admin/elementor/status`, `GET /admin/elementor/{post_id}`, `GET /admin/elementor/templates`. Writes require `manage_options` AND `edit_post` on the target post (S-12). Block + classic content is sanitised via `wp_kses_post` unless the caller has `unfiltered_html` (S-13). Elementor JSON node count capped at 5,000 per call; oversized payloads return `elementor_too_large` (S-14). All Elementor writes fire `elementor/document/after_save` so caches and CSS regenerate cleanly.

= 2.12.0 =
* F.19.3.1 — Three more read-only admin routes ported from the legacy `wordpress_advanced` WP-CLI tools so they can run via the companion instead of `docker exec`. `GET /admin/system-info` (PHP/MySQL/WordPress versions + server software + memory limits), `GET /admin/phpinfo` (extension list + curated ini snapshot — never the full `phpinfo()` HTML which would leak server internals), `GET /admin/disk-usage` (uploads/plugins/themes/total bytes + `disk_free_space`, bounded at 200k files / 5s wall clock per tree). All gated on `manage_options`.

= 2.11.0 =
* F.19.1 — New read-only admin namespace `airano-mcp/v1/admin/*` for the WordPress Specialist tool surface. Six new routes — `plugins`, `themes`, `users`, `options/{name}`, `cron`, `maintenance` — all gated on `manage_options`. `options` route uses a deny-list of credential-shaped suffixes (`*_secret`, `*_password`, `*_api_key`, `*_token`, `auth_*_key`, `auth_*_salt`) on top of the cap check. `users` route paginates up to 200/call with optional `role` + `search` filters. No state changes in this version; write operations land in F.19.2.

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

= 2.18.1 =
WordPress.org review fixes only — no behaviour changes. Drops a redundant core file include and tightens the `/upload-and-attach` permission gate so the per-target `edit_post` check runs before the callback (visible to static analysis).

= 2.18.0 =
Adds the F.19.3.2-.3 database inspection surface (3 new admin read routes — db/size / db/tables / db/search) wrapping `information_schema.TABLES` + `WP_Query`. NEVER exposes raw SQL (S-25 — query is sanitised and length-capped). All gated on `manage_options`. No breaking changes; existing routes unchanged.

= 2.17.0 =
Adds the F.19.6.B site layout surface (7 new admin routes — menus / widgets / customizer changeset). New security rules S-22 (per-item caps for nav-menu object refs), S-23 (`wp_kses_post` on widget HTML unless `unfiltered_html`), S-24 (customizer apply requires `customize` cap). No breaking changes; existing routes unchanged.

= 2.16.0 =
Adds the F.19.6.A site config surface (6 new admin routes — identity / reading / permalinks). All gated on `manage_options`. Permalink writes flush rewrite rules automatically. No breaking changes; existing routes unchanged.

= 2.15.0 =
Adds the F.19.2.1 plugin write management surface (5 new admin routes — install / activate / deactivate / update / delete). Per-route checks for `install_plugins` / `activate_plugins` / `delete_plugins`. Refuses to deactivate or delete the companion plugin itself. No breaking changes; existing routes unchanged.

= 2.14.0 =
Adds the F.19.7 theme dev surface (7 new admin routes — install / activate / delete + file CRUD). Per-route checks for `install_themes` / `switch_themes` / `delete_themes` / `edit_themes`; PHP file writes additionally require `!DISALLOW_FILE_EDIT`. No breaking changes; existing routes unchanged.

= 2.13.0 =
Adds the F.19.5 page editing surface (10 new admin routes — Gutenberg blocks, Elementor read/write/template, Classic html replace). Writes require `manage_options` AND `edit_post` on the target post; raw HTML is gated on the caller also holding `unfiltered_html`. No breaking changes; existing routes unchanged.

= 2.12.0 =
Adds three more read-only admin routes (`/admin/system-info`, `/admin/phpinfo`, `/admin/disk-usage`). They replace the legacy WP-CLI / Docker-socket flow used by the `wordpress_advanced` MCP plugin so admins on shared hosting can use those tools too. No breaking changes.

= 2.11.0 =
Adds the `airano-mcp/v1/admin/*` namespace (six read routes) for the new WordPress Specialist MCP tool surface. No breaking changes; existing routes unchanged. Activate the plugin and any admin Application Password gets the new routes.

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
