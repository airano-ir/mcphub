# Airano MCP Bridge

**Version:** 2.21.1
**Requires WordPress:** 5.6+
**Tested up to:** 7.1
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
- **Theme file patching** for small line-range edits without full-file base64 uploads
- **Transient cleanup and inventory** (expired / all / pattern cleanup, metadata-only listing)
- **Bulk post-meta writes** in a single REST round-trip
- **Generic multilingual adapter** (v2.19.0–2.20.2) — `POST /post-language` and `POST /term-language` routes for language + translation linking, auto-detecting WPML or Polylang while MCPHub keeps plugin-agnostic `language` / `translation_of` fields.
- **Unified site-health snapshot** (5+ stock calls → 1)
- **Structured JSON export** (posts / pages / products + media + terms + meta)
- **Capability probe** — tells MCP Hub what the calling application password can actually do
- **Audit hook** — forwards WordPress action events to MCP Hub with HMAC-signed webhooks
- **SEO meta routes** for Rank Math and Yoast
- **WordPress Specialist admin namespace** (v2.11.0+) — read-only inventory of plugins, themes, users, options, cron, maintenance status. Powers the `wordpress_specialist` MCP plugin so admins on shared hosting can use the same tools that previously required Docker socket + WP-CLI.
- **System diagnostics** (v2.12.0) — `system-info`, `phpinfo` (curated, not the full HTML dump), `disk-usage` (bounded directory walks).
- **Page editing** (v2.13.0) — Gutenberg block read/replace/insert/remove, Elementor detect/get/set/regen-css/template-list/template-apply, Classic-editor html replace. Writes are double-gated: `manage_options` route-level + per-post `edit_post` enforcement; raw HTML requires `unfiltered_html`; Elementor JSON capped at 5,000 nodes per call.
- **Theme dev surface** (v2.14.0) — install (from URL or base64 zip) / activate / delete + theme file CRUD (list, read, write, delete). All theme paths canonicalise via `realpath()` and reject any escape from the slug directory. PHP file writes additionally require `!DISALLOW_FILE_EDIT`. Optimistic concurrency via `expected_sha256` on writes. Per-call caps 5 MB/file, 1000 files/list, 50 MB/install zip. Refuses to delete the active theme (or its parent) and `style.css` of the active theme.
- **Plugin write management** (v2.15.0) — install (from wp.org slug, URL, or base64 zip) / activate / deactivate / update / delete. Per-route capability checks (`install_plugins`, `activate_plugins`, `delete_plugins`). Refuses to deactivate or delete the companion plugin itself (would brick the MCP connection) and refuses to delete active plugins. Update route returns `up_to_date:true` cleanly when no update is available.
- **Site config** (v2.16.0) — Settings → General + Reading + Permalinks panels via typed REST. `GET/POST /admin/site/identity` (title / tagline / site_icon / custom_logo), `GET/POST /admin/site/reading` (show_on_front / page_on_front / page_for_posts / posts_per_page / blog_public), `GET/POST /admin/permalinks` (structure + category_base + tag_base, with `flush_rewrite_rules()` after each write).
- **Site layout** (v2.17.0) — Settings → Menus + Appearance → Widgets + Customizer surfaces. Menus: `GET /admin/menus`, `GET /admin/menus/{id}`, `PUT /admin/menus/{id}` (full-replace items + optional rename, slug stays frozen, S-22 per-item cap dispatch). Widgets: `GET /admin/widgets/areas`, `GET /admin/widgets/{area_id}`, `PUT /admin/widgets/{area_id}` (block-kind areas accept any block raw HTML; legacy areas accept `text` widget settings only this round). Customizer: `POST /admin/customizer/changeset` with `{action: get|apply|discard}` — single-tool wrapper around the changeset queue; `apply` requires the `customize` cap (S-24).
- **Database inspection and bounded maintenance** (v2.18.0 / v2.18.5) — read-only DB introspection via typed routes that NEVER expose raw SQL, plus prefix-scoped `CHECK TABLE` / `OPTIMIZE TABLE` maintenance. `GET /admin/db/size`, `GET /admin/db/tables`, `POST /admin/db/search`, `GET /admin/db/check`, `POST /admin/db/optimize`.

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
| `/post-language` | POST | 2.19.0 | Generic language + translation linking for posts/pages through the active WPML or Polylang adapter. Requires `edit_post` on the target and readable access to `translation_of` when supplied. |
| `/term-language` | POST | 2.20.0 | Generic language + translation linking for taxonomy terms through the active WPML or Polylang adapter. Accepts taxonomy slug or REST base and requires the taxonomy edit-terms capability. |
| `/term-update` | POST | 2.20.0 | Narrow fallback for translated-term slug duplicate failures in stock REST. Accepts taxonomy slug or REST base and updates supported term fields through WordPress core APIs. |
| `/export` | GET | 2.3.0 | Structured JSON export of posts / pages / products + media + terms + meta, with `post_type` / `status` / `since` / `limit` / `offset` paging |
| `/cache-purge` | POST | 2.4.0 | Auto-detects LiteSpeed, WP Rocket, W3 Total Cache, WP Super Cache, WP Fastest Cache, SiteGround Optimizer and triggers each one's purge API; always flushes object cache |
| `/opcache-reset` | POST | 2.18.4 | Calls PHP `opcache_reset()` so public companion deployments can drop bytecode cache after theme/plugin deploys without Cloudflare credentials or app restarts |
| `/transient-flush` | POST | 2.5.0 | Native transient cleanup with `expired` / `all` / `pattern` scopes; optional site-transient handling for multisite |
| `/transients` | GET | 2.18.5 | Metadata-only transient inventory: key, type, and expiration. Values are never returned. |
| `/site-health` | GET | 2.6.0 | Single-envelope health snapshot: WP/PHP/MySQL versions, disk free, active plugins, theme, writability, SSL — replaces 5+ stock calls |
| `/audit-hook` | GET / POST / DELETE | 2.7.0 | Configure a webhook that forwards WP action events to MCP Hub. HMAC-SHA256-signed, non-blocking |
| `/regenerate-thumbnails` | POST | 2.8.0 | Rebuild attachment sub-sizes via `wp_generate_attachment_metadata()` for a list of IDs or in paged batch mode |

### WordPress Specialist admin namespace (`airano-mcp/v1/admin/*`)

All routes require `manage_options`. They power the `wordpress_specialist` MCP plugin (companion-backed advanced WordPress management — no Docker socket required).

| Route | Method | Introduced | Purpose |
|---|---|---|---|
| `/admin/plugins` | GET | 2.11.0 | Every plugin known to WP with active/network-active/version/author/update flags |
| `/admin/themes` | GET | 2.11.0 | Installed themes with stylesheet/template/parent/block-theme/active flags |
| `/admin/users` | GET | 2.11.0 | Paginated user list (cap 200/call) with optional `role` and `search` filters |
| `/admin/options/{name}` | GET | 2.11.0 | Single option fetch with deny-list of credential-shaped keys (`*_secret`, `*_password`, `*_api_key`, `*_token`, `auth_*_key`, `auth_*_salt`) |
| `/admin/cron` | GET | 2.11.0 | Full cron table with epoch + ISO 8601 next_run, schedule slug, interval, args |
| `/admin/maintenance` | GET | 2.11.0 | `.maintenance` sentinel inspection (`enabled` / `started_at` / `stale`, 10-min stale threshold matches WP) |
| `/admin/system-info` | GET | 2.12.0 | WP/PHP/MySQL/server versions + memory + paths in one envelope |
| `/admin/phpinfo` | GET | 2.12.0 | Sorted extension list + curated ini whitelist + disabled functions + opcache state (structured JSON, not the full HTML dump) |
| `/admin/disk-usage` | GET | 2.12.0 | Bytes for uploads/plugins/themes + filesystem `disk_total/free/used` (bounded 200k files / 5s per tree, with `truncated:true` flag) |
| `/admin/blocks/replace` | POST | 2.13.0 | Replace post block tree (companion runs `serialize_blocks()`; max 200 blocks; `wp_kses_post` unless caller has `unfiltered_html`) |
| `/admin/blocks/insert` | POST | 2.13.0 | Insert one block at index N |
| `/admin/blocks/remove` | POST | 2.13.0 | Remove block at index N (returns the removed block for rollback) |
| `/admin/elementor/status` | GET | 2.13.0 | Elementor presence + version + Pro flag + supported post types; `installed:false` cleanly when absent |
| `/admin/elementor/{post_id}` | GET | 2.13.0 | Parsed `_elementor_data` (slash-stripped, JSON-decoded) |
| `/admin/elementor/{post_id}` | POST | 2.13.0 | Replace `_elementor_data`; validates id/elType/settings; capped at 5,000 nodes; fires `elementor/document/after_save` |
| `/admin/elementor/{post_id}/regen-css` | POST | 2.13.0 | Trigger per-post Elementor CSS regeneration |
| `/admin/elementor/templates` | GET | 2.13.0 | Saved Elementor templates (id/title/type/modified) |
| `/admin/elementor/templates/apply` | POST | 2.13.0 | Copy a saved template's `_elementor_data` into a target post |
| `/admin/classic/{post_id}/replace` | POST | 2.13.0 | Pure post_content swap for classic-editor sites (`wp_kses_post` unless caller has `unfiltered_html`) |
| `/admin/themes/install` | POST | 2.14.0 | Install theme from `zip_url` or base64 `zip_base64`; supports `activate`, `overwrite`. Runs WP core's `Theme_Upgrader`. Requires `install_themes` (+ `switch_themes` if `activate`). 50 MB cap. |
| `/admin/themes/{slug}/activate` | POST | 2.14.0 | Switch the active theme. Requires `switch_themes`. |
| `/admin/themes/{slug}` | DELETE | 2.14.0 | Delete an installed theme. Refuses if active or active parent. Requires `delete_themes`. |
| `/admin/themes/files/{slug}` | GET | 2.14.0 | Theme directory walk: each file's relative path, size, mime, sha256, modified_at. Optional `glob` + `max_files` (cap 1000). |
| `/admin/themes/files/{slug}/{path}` | GET | 2.14.0 | Read a theme file as base64 + sha256 + mime + modified_at. 5 MB cap. |
| `/admin/themes/files/{slug}/{path}` | PUT | 2.14.0 | Write a theme file (base64). Optional `expected_sha256` for optimistic concurrency. PHP writes require `!DISALLOW_FILE_EDIT`. Requires `edit_themes`. 5 MB cap. |
| `/admin/themes/files/{slug}/{path}` | PATCH | 2.18.3 | Small line-range text patch: `{from_line,to_line,content,expected_sha256?}`. Avoids full-file base64 uploads for CSS/template edits. |
| `/admin/themes/files/{slug}/{path}` | DELETE | 2.14.0 | Delete a theme file. Refuses to delete `style.css` of the active theme. Requires `edit_themes`. |
| `/admin/plugins/install` | POST | 2.15.0 | Install via wp.org `slug`, OR via `zip_url`, OR via inline `zip_base64`. Supports `activate` + `overwrite`. Runs WP core's `Plugin_Upgrader`. Requires `install_plugins`. 50 MB zip cap. |
| `/admin/plugins/{slug}/activate` | POST | 2.15.0 | Activate an installed plugin. Optional `network_wide` for multisite. Requires `activate_plugins`. |
| `/admin/plugins/{slug}/deactivate` | POST | 2.15.0 | Deactivate. Refuses companion (S-20) and `Required` plugins (S-21). Requires `activate_plugins`. |
| `/admin/plugins/{slug}/update` | POST | 2.15.0 | Update to latest wp.org version. Returns `up_to_date:true` cleanly when no update available. Requires `update_plugins`. |
| `/admin/plugins/{slug}` | DELETE | 2.15.0 | Delete an installed plugin. Refuses active plugins, the companion, and `Required` plugins. Requires `delete_plugins`. |
| `/admin/site/identity` | GET | 2.16.0 | Site title / tagline / site_icon / custom_logo / charset / WP version / admin_email / language / siteurl. |
| `/admin/site/identity` | POST | 2.16.0 | Update title / tagline / site_icon_id / custom_logo_id (any subset). Attachment ids validated against the media library. |
| `/admin/site/reading` | GET | 2.16.0 | show_on_front / page_on_front / page_for_posts / posts_per_page / posts_per_rss / blog_public. |
| `/admin/site/reading` | POST | 2.16.0 | Update reading settings; page_on_front + page_for_posts must reference published Pages. |
| `/admin/permalinks` | GET | 2.16.0 | permalink_structure + category_base + tag_base. |
| `/admin/permalinks` | POST | 2.16.0 | Update permalink structure (empty string = plain). Calls `flush_rewrite_rules()` after the write. |
| `/admin/menus` | GET | 2.17.0 | Every nav menu with id / name / slug / theme locations / item count. |
| `/admin/menus/{menu_id}` | GET | 2.17.0 | One menu's items: `{id, title, type, object, object_id, parent, order, url, target, classes, xfn}`. |
| `/admin/menus/{menu_id}` | PUT | 2.17.0 | Full-replace items + optional rename. Slug frozen. Two-pass: every item validated against S-22 before any mutation; refusals return `forbidden_object_id` 403/404 and leave the menu untouched. |
| `/admin/widgets/areas` | GET | 2.17.0 | Every registered sidebar with id / name / theme_location / widget_count / kind (`block` or `legacy`). |
| `/admin/widgets/{area_id}` | GET | 2.17.0 | One area's widgets. Block-kind: `{id, type:'block', blocks:[parsed], raw}`. Legacy-kind: `{id, type, settings}`. |
| `/admin/widgets/{area_id}` | PUT | 2.17.0 | Full replace. Block areas accept any block raw HTML; legacy areas accept `text` widget settings only this round (other legacy types remain read-only). HTML sanitised via `wp_kses_post` unless caller has `unfiltered_html` (S-23). |
| `/admin/customizer/changeset` | POST | 2.17.0 | `{action: get|apply|discard}`. `apply` requires the `customize` cap on top of `manage_options` (S-24). Empty changeset returns `{status:'empty'}` 200. |
| `/admin/db/size` | GET | 2.18.0 | Aggregate database size from `information_schema.TABLES`: `{database_bytes, table_count, row_count_estimate, database_name, table_prefix}`. No SQL exposure. |
| `/admin/db/tables` | GET | 2.18.0 | Per-table breakdown: `{name, engine, rows, data_bytes, index_bytes, total_bytes, collation}` ordered by total_bytes desc. |
| `/admin/db/search` | POST | 2.18.0 | `WP_Query` wrapper. Body `{query, post_type?, status?, limit?}` (limit default 20, max 100). Sanitises + length-caps query at 200 chars (S-25). Non-readable posts filtered out via WP's own `posts_clauses`. Never raw SQL. |
| `/admin/db/check` | GET | 2.18.5 | Runs `CHECK TABLE` on current-prefix WordPress tables only; caller cannot choose arbitrary tables. |
| `/admin/db/optimize` | POST | 2.18.5 | Runs `OPTIMIZE TABLE` on current-prefix WordPress tables only; caller cannot choose arbitrary tables. |

Writes added in 2.13.0 require **two** capabilities: route-level `manage_options` AND per-post `edit_post` on the target (S-12 in MCP Hub's security ruleset). Raw-HTML pass-through requires the calling user to also hold `unfiltered_html`. Elementor JSON node count is capped at 5,000 per call (S-14); oversized payloads return `elementor_too_large` — switch to `/admin/elementor/templates/apply` instead.

Theme dev routes added in 2.14.0 layer per-route capability checks on top of `manage_options`: `install_themes`, `switch_themes`, `delete_themes`, `edit_themes`. PHP file writes additionally require `!DISALLOW_FILE_EDIT` (S-17). All file paths canonicalise via `realpath()` and must resolve under `wp-content/themes/{slug}` (S-16); attempts to escape return `path_invalid`. Optimistic concurrency via `expected_sha256` returns `sha_mismatch` (409) if the on-disk sha256 differs (S-19).

Plugin write routes added in 2.15.0 layer per-route capability checks on `manage_options`: `install_plugins` (install / update), `activate_plugins` (activate / deactivate), `delete_plugins` (delete). New rules: S-20 refuses to deactivate / delete the Airano MCP Bridge companion itself (returns `companion_self` 409 — would brick the MCP connection); S-21 refuses to deactivate / delete plugins whose header sets `Required: yes`. The single `POST /admin/plugins/install` route accepts three mutually-exclusive body shapes — `{slug}` for wp.org install, `{zip_url}` for download, `{zip_base64}` for inline — with the same 50 MB cap (S-18) on zip payloads. Delete refuses any plugin currently active (`plugin_active` 409 — caller must deactivate first).

### Authentication

All routes require **HTTP Basic** authentication with a WordPress **Application Password** (Users → Profile → Application Passwords). Per-route capability requirements:

| Route family | Required capability |
|---|---|
| SEO meta (read/write) | `edit_posts` |
| Upload helpers | `upload_files` or `manage_options` |
| Capabilities probe | `read` (any logged-in user) |
| Bulk meta, Export | `edit_posts` (per-item `edit_post` check) |
| Post language | `edit_post` on target; `read_post` on `translation_of` source when supplied |
| Cache purge, Transient flush, Site health, Audit hook, Regenerate thumbnails | `manage_options` |
| Admin namespace (`/admin/*`) | `manage_options` |

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

### 2.20.2 — 2026-06-11

- Makes taxonomy translation creation idempotent for WPML and Polylang. `POST /airano-mcp/v1/term-language` now supports lookup-only checks so MCPHub can return an existing target-language term before creating duplicate `translation_of` entries.

### 2.20.1 — 2026-06-11

- Internal package refresh for MCPHub media-intake compatibility. No new companion REST routes were added; MCPHub now handles large chat-attached media through its authenticated per-user HTTP intake before forwarding to existing companion upload routes when available.

### 2.20.0 — 2026-06-04

- Extends the plugin-agnostic multilingual adapter to taxonomy terms: `POST /airano-mcp/v1/term-language` applies generic `language` + `translation_of` metadata through WPML or Polylang adapters, `/capabilities` advertises `features.multilingual.terms.can_link`, and `POST /airano-mcp/v1/term-update` provides a narrow fallback for translated-term slug duplicate failures in stock REST.

### 2.19.0 — 2026-06-03

- Adds plugin-agnostic content primitives for MCPHub: `POST /airano-mcp/v1/post-language` applies generic `language` + `translation_of` metadata through WPML or Polylang adapters, and `/capabilities` now advertises `features.multilingual` plus `features.meta_passthrough` for stock REST create/update flows.

### 2.18.5 — 2026-06-03

- Adds companion REST replacements for low-risk legacy MCPHub WordPress maintenance tools: `GET /transients`, `GET /admin/db/check`, and `POST /admin/db/optimize`. Transient listing is metadata-only and DB maintenance is scoped to the current WordPress table prefix.

### 2.18.4 — 2026-06-01

- **F.18.8: OPcache reset for companion-only deploy loops.** Adds `POST /airano-mcp/v1/opcache-reset`, gated on `manage_options`, which calls PHP `opcache_reset()` and returns a compact before/after OPcache status snapshot. This replaces the Cloudflare-purge idea for public MCPHub: no CDN token, zone id, or infra credential is stored in the WordPress companion, while agents can still avoid app restarts on hosts with `opcache.validate_timestamps=0`.

### 2.18.0 — 2026-05-04

- **F.19.3.2-.3: Database inspection (read) + bulk fan-out (write) + wordpress_advanced sunset.** Three new admin routes — `GET /admin/db/size` (single `information_schema.TABLES` aggregation, returns `{database_bytes, table_count, row_count_estimate, database_name, table_prefix}` — no SQL exposure), `GET /admin/db/tables` (per-table breakdown with name / engine / rows / data_bytes / index_bytes / total_bytes / collation, ordered by total_bytes desc), `POST /admin/db/search` (body `{query, post_type?, status?, limit?}` — wraps `WP_Query` with `s=$query`, sanitises via `sanitize_text_field` and length-caps at 200 chars server-side, `limit` capped at 100; returns `{query, limit, count, hits}`). New security rule **S-25**: db/search wraps `WP_Query`, NEVER raw SQL; `WP_Query`'s own `posts_clauses` filter (the same gate the WP search page uses) keeps non-readable posts (private/draft from other authors) out of the result set. Bulk write tools on the MCP Hub side (`wp_bulk_post_update`, `wp_bulk_term_update`) ride stock REST `wp/v2/posts/{id}` and `wp/v2/{taxonomy}/{id}` — no companion routes needed for those, but the cap of 50 items per call is documented under **S-26** in the MCP Hub spec. All admin routes gated on `manage_options` route-level. **Bundled with the wordpress_advanced sunset on the MCP Hub side**: the deprecated WP-CLI/Docker-socket plugin was removed in F.19.3.2-.3 (2026-05-04); `wordpress_specialist` is now the only WP-management surface and has no Docker socket dependency.

### 2.17.0 — 2026-05-03

- **F.19.6.B: Site layout (menus + widgets + customizer).** Seven new admin routes — three for menus, three for widgets, one for the customizer changeset queue. Menus: `GET /admin/menus`, `GET /admin/menus/{id}`, `PUT /admin/menus/{id}` (body `{items:[...], name?}` — full replace, items not in the array are deleted, slug stays frozen so `theme_location` mapping survives). Widgets: `GET /admin/widgets/areas` (each area carries `kind: 'block'|'legacy'`), `GET /admin/widgets/{area_id}` (block-kind returns parsed block tree + roundtrip-safe `raw`; legacy-kind returns option-keyed settings), `PUT /admin/widgets/{area_id}` (block areas accept any block raw HTML; legacy areas accept `text` widget settings only this round — other legacy types remain read-only and return `unsupported_legacy_widget`; caller-side `kind` is ignored, area kind is determined by the area itself). Customizer: `POST /admin/customizer/changeset` with `{action: get|apply|discard}` — single-tool wrapper around the changeset queue, intentionally limited because most modern themes use FSE/site-editor instead of the customizer. New security rules: **S-22** dispatches per nav-menu item type — `post_type` checks `current_user_can('read_post', id)`; `taxonomy` allows public taxonomies and otherwise requires the taxonomy's `assign_terms` cap (deliberately NOT `manage_categories` which is a write cap and would refuse routine "add public Category X to footer" flows for editors who don't manage taxonomies); `custom` URL items skip the object validation. Refusals surface as `forbidden_object_id` 403/404. **S-23** sanitises widget HTML via `wp_kses_post` unless the caller has `unfiltered_html` (mirrors S-13 from F.19.5). **S-24** customizer apply requires the `customize` cap on top of `manage_options` — same bar as `/wp-admin/customize.php`. All routes gated on `manage_options` route-level. Pre-validates every menu item before mutating so a partial S-22 failure leaves the menu untouched. Customizer apply is racy with concurrent edits via the customizer UI — intentional, mirrors WP behaviour.

### 2.16.0 — 2026-05-03

- **F.19.6.A: Site config surface.** Six new admin routes covering Settings → General + Reading + Permalinks: `GET/POST /admin/site/identity` (title / tagline / site_icon / custom_logo), `GET/POST /admin/site/reading` (show_on_front / page_on_front / page_for_posts / posts_per_page / posts_per_rss / blog_public), `GET/POST /admin/permalinks` (permalink_structure + category_base + tag_base). All gated on `manage_options`. POST routes validate attachment ids against the media library, reject non-published page ids for page_on_front / page_for_posts, and route every option write through WP's own `sanitize_option_*` hooks. After a permalink_structure write `flush_rewrite_rules()` runs so the new structure takes effect immediately. First consumer of the `settings` tier introduced by F.19.2.0.

### 2.15.0 — 2026-05-02

- **F.19.2.1: Plugin write management.** Five new admin routes — `POST /admin/plugins/install` (accepts `{slug}` for wp.org install OR `{zip_url|zip_base64}` for arbitrary zip; supports `activate` + `overwrite`), `POST /admin/plugins/{slug}/activate`, `POST /admin/plugins/{slug}/deactivate`, `POST /admin/plugins/{slug}/update`, `DELETE /admin/plugins/{slug}`. Per-route capability checks: `install_plugins` (install / update), `activate_plugins` (activate / deactivate), `delete_plugins` (delete). New security rules: S-20 refuses to deactivate / delete the Airano MCP Bridge companion itself (returns `companion_self` 409 — operator must use WP-Admin → Plugins instead); S-21 refuses to deactivate / delete plugins marked `Required: yes` in their header. Reuses S-15 (slug whitelist via `get_plugins()`) + S-18 (50 MB cap on install zip). Refuses to delete an active plugin (caller must deactivate first). Update route returns `up_to_date:true` cleanly when no update is available. Multisite supports `network_wide` activation/deactivation (requires `manage_network_plugins` for activate).

### 2.14.0 — 2026-05-02

- **F.19.7: Theme dev surface (install + activate + delete + file CRUD).** Three theme management routes — `POST /admin/themes/install` (accepts either `zip_url` or inline `zip_base64`; runs WP core's `Theme_Upgrader`; supports `activate` + `overwrite`), `POST /admin/themes/{slug}/activate`, `DELETE /admin/themes/{slug}` — and four file CRUD routes — `GET /admin/themes/files/{slug}` (glob walk capped at 1000 files, returns `path/size/mime/sha256/modified_at` per entry), `GET /admin/themes/files/{slug}/{path}` (read as base64), `PUT /admin/themes/files/{slug}/{path}` (write with optional `expected_sha256` for optimistic concurrency and `create_dirs`), `DELETE /admin/themes/files/{slug}/{path}`. Per-route capability checks: `install_themes`, `switch_themes`, `delete_themes`, `edit_themes`. PHP file writes additionally require `!DISALLOW_FILE_EDIT` (S-17). All file paths canonicalise via `realpath()` and must stay under `wp-content/themes/{slug}` (S-16). Per-call caps: 5 MB/file, 1000 files/list, 50 MB/install zip (S-18). Optimistic concurrency on `expected_sha256` returns `sha_mismatch` (409) on drift (S-19). Refuses to delete the active theme, the active parent theme, or `style.css` of the active theme.

### 2.13.0 — 2026-05-01

- **F.19.5: Page editing surface (Gutenberg + Elementor + Classic).** Seven new write routes — `POST /admin/blocks/{replace,insert,remove}`, `POST /admin/elementor/{post_id}` (set), `POST /admin/elementor/{post_id}/regen-css`, `POST /admin/elementor/templates/apply`, `POST /admin/classic/{post_id}/replace` — and three new read routes — `GET /admin/elementor/status`, `GET /admin/elementor/{post_id}`, `GET /admin/elementor/templates`. Writes require `manage_options` AND per-post `edit_post` (S-12); block + classic content sanitised via `wp_kses_post` unless caller has `unfiltered_html` (S-13); Elementor JSON node count capped at 5,000 per call (S-14). All Elementor writes fire `elementor/document/after_save` so caches and CSS regenerate cleanly.

### 2.12.0 — 2026-05-01

- **F.19.3.1: System diagnostic ports from `wordpress_advanced`.** Three more read-only admin routes — `GET /admin/system-info`, `GET /admin/phpinfo`, `GET /admin/disk-usage` — replace the legacy WP-CLI / Docker-socket flow so admins on shared hosting can use those tools too. All gated on `manage_options`. `phpinfo` returns curated structured JSON (extension list + ini whitelist + opcache state), never the full `phpinfo()` HTML dump (which would leak server internals). `disk-usage` walks bounded at 200k files / 5s per tree.

### 2.11.0 — 2026-05-01

- **F.19.1: Read-only admin namespace.** Six new routes under `airano-mcp/v1/admin/*` — `plugins`, `themes`, `users`, `options/{name}`, `cron`, `maintenance` — gated on `manage_options`. `options` route uses a deny-list of credential-shaped suffixes on top of the cap check. `users` route paginates up to 200/call with optional `role` + `search` filters. No state changes; write operations land in F.19.2.

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

### 2.16.0

Adds the F.19.6.A site config surface (6 new admin routes — identity / reading / permalinks). All gated on `manage_options`. Permalink writes flush rewrite rules automatically. No breaking changes; existing routes unchanged.

### 2.15.0

Adds the F.19.2.1 plugin write management surface (5 new admin routes — install / activate / deactivate / update / delete). Per-route checks for `install_plugins` / `activate_plugins` / `delete_plugins`. Refuses to deactivate or delete the companion plugin itself. No breaking changes; existing routes unchanged.

### 2.14.0

Adds the F.19.7 theme dev surface (7 new admin routes — install / activate / delete + file CRUD). Per-route checks for `install_themes` / `switch_themes` / `delete_themes` / `edit_themes`; PHP file writes additionally require `!DISALLOW_FILE_EDIT`. No breaking changes; existing routes unchanged.

### 2.13.0

Adds the F.19.5 page editing surface (10 new admin routes — Gutenberg blocks, Elementor read/write/template, Classic html replace). Writes require `manage_options` AND per-post `edit_post`; raw-HTML pass-through is gated on `unfiltered_html`. No breaking changes; existing routes unchanged.

### 2.9.0

Adds `POST /airano-mcp/v1/upload-and-attach` — upload + metadata + attach + featured in one REST round-trip. No breaking changes to existing routes.

## Credits

Built by the [MCP Hub](https://github.com/airano-ir/mcphub) project. Contributions welcome — see the parent repository for contribution guidelines.
