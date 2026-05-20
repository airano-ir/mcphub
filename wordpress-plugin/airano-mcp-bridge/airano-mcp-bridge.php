<?php
/**
 * Plugin Name: Airano MCP Bridge
 * Plugin URI: https://mcp.palebluedot.live
 * Description: Companion plugin for MCP Hub. Exposes SEO meta (Rank Math / Yoast), media upload helpers (bypass upload_max_filesize), and site capabilities via the WordPress REST API for AI agents and MCP servers. Supports posts, pages, and WooCommerce products.
 * Version: 2.18.1
 * Author: MCP Hub
 * Author URI: https://github.com/airano-ir
 * License: GPL-2.0-or-later
 * Requires at least: 5.0
 * Requires PHP: 7.4
 * Text Domain: airano-mcp-bridge
 *
 * Changelog:
 * 2.18.1 - wp.org review fixes: (a) drop unused `wp-admin/includes/media.php` requires from /upload-chunk + /upload-and-attach (the code only calls helpers from file.php and image.php); (b) split /upload-and-attach permission_callback into a dedicated method that explicitly checks `edit_post` on `attach_to_post` and rejects `set_featured` without a target — the per-target check is now enforced at the route gate (visible to static analysis), not just inside the callback.
 * 2.18.0 - F.19.3.2-.3: Database inspection (read) + bulk fan-out (write). Three new admin routes — `GET /admin/db/size` (single `information_schema.TABLES` aggregation: database_bytes + table_count + row_count_estimate, no SQL exposure), `GET /admin/db/tables` (per-table breakdown: name, engine, rows, data_bytes, index_bytes, total_bytes, collation), `POST /admin/db/search` body `{query, post_type?, status?, limit?}` wraps `WP_Query` with `s=$query` (NOT raw SQL), `query` sanitised via `sanitize_text_field` and capped at 200 chars server-side, `limit` capped at 100. New security rule S-25 — db/search wraps `WP_Query`, never raw SQL; `posts_clauses` filter (same as the WP search page) keeps non-readable posts (private/draft from other authors) out of the result set. Bulk write tools (`wp_bulk_post_update`, `wp_bulk_term_update`) ride stock REST `wp/v2/posts/{id}` and `wp/v2/{taxonomy}/{id}` — no companion routes needed for those. Companion-side cap: 50 items per call, mirror of S-26 (client-side caps at the same number; server is the binding gate). All admin routes gated on `manage_options`. Bundled with the wordpress_advanced sunset (the deprecated WP-CLI/Docker-socket plugin is removed in this round of MCPHub).
 * 2.17.0 - F.19.6.B: Site layout — menus + widgets + customizer (7 new routes). Menus: `GET /admin/menus`, `GET /admin/menus/{id}`, `PUT /admin/menus/{id}` (full-replace items + optional rename; slug stays frozen). Widgets: `GET /admin/widgets/areas`, `GET /admin/widgets/{area_id}`, `PUT /admin/widgets/{area_id}` (block-kind areas accept any block raw HTML; legacy areas accept `text` widget settings only — other legacy types are read-only this round). Customizer: `POST /admin/customizer/changeset` with `{action: get|apply|discard}` — single-tool wrapper around the changeset queue, lower priority since FSE themes don't use customizer. New security rules: S-22 dispatches per nav-menu item type — `post_type` checks `current_user_can('read_post', id)`, `taxonomy` checks public taxonomy OR `assign_terms` cap (deliberately NOT `manage_categories` which is a write cap), `custom` URL items skip object validation; S-23 sanitises widget HTML via `wp_kses_post` unless caller has `unfiltered_html` (mirrors S-13); S-24 customizer apply requires `customize` cap (not just `manage_options` — same bar as `/wp-admin/customize.php`). All routes gated on `manage_options`. Pre-validates every menu item before mutating so a partial failure leaves the menu untouched.
 * 2.16.0 - F.19.6.A: Site config surface. Six new routes — `GET/POST /admin/site/identity` (title / tagline / site_icon / custom_logo), `GET/POST /admin/site/reading` (show_on_front / page_on_front / page_for_posts / posts_per_page / posts_per_rss / blog_public), `GET/POST /admin/permalinks` (permalink_structure + category_base + tag_base, with `flush_rewrite_rules()` after write). All gated on `manage_options`. POST routes validate attachment ids against the media library, reject non-published page ids for page_on_front/page_for_posts, and route every option write through WP's own `sanitize_option_*` hooks. After a permalink_structure write the rewrite rules are flushed so the change takes effect immediately.
 * 2.15.0 - F.19.2.1: Plugin write management. Six new routes — `POST /admin/plugins/install` (accepts {slug} for wp.org install OR {zip_url|zip_base64} for arbitrary zip), `POST /admin/plugins/{slug}/activate`, `POST /admin/plugins/{slug}/deactivate`, `POST /admin/plugins/{slug}/update`, `DELETE /admin/plugins/{slug}`. Per-route capability checks: `install_plugins` (install / update), `activate_plugins` (activate / deactivate), `delete_plugins` (delete). New security rules: S-20 refuses to deactivate or delete the Airano MCP Bridge companion itself (would brick the MCP connection); S-21 refuses to deactivate / delete plugins marked `Required: yes` in their header. Reuses S-15 (slug whitelist via `get_plugins()`) + S-18 (50 MB cap on install zip). All routes gated on `manage_options`.
 * 2.14.0 - F.19.7: Theme dev surface (install + activate + delete + file CRUD). Seven new routes — `POST /admin/themes/install` (zip_url or zip_base64), `POST /admin/themes/{slug}/activate`, `DELETE /admin/themes/{slug}`, `GET /admin/themes/files/{slug}` (list with glob + max_files), `GET /admin/themes/files/{slug}/{path}` (read), `PUT /admin/themes/files/{slug}/{path}` (write with optional expected_sha256), `DELETE /admin/themes/files/{slug}/{path}`. New security rules: theme_slug whitelist via `wp_get_themes()` (S-15), path canonicalisation via `realpath()` (S-16), PHP write gate via `DISALLOW_FILE_EDIT` (S-17), per-call caps 5 MB/file, 1000 files/list, 50 MB/zip (S-18), optimistic concurrency on `expected_sha256` (S-19). All routes gated on `manage_options`; per-route handlers add `install_themes` / `switch_themes` / `delete_themes` / `edit_themes` checks.
 * 2.13.0 - F.19.5: Page editing surface (Gutenberg + Elementor + Classic). Seven new write routes — /admin/blocks/{replace,insert,remove}, /admin/elementor/{post_id} (POST + GET), /admin/elementor/{post_id}/regen-css, /admin/elementor/templates/apply, /admin/classic/{post_id}/replace — and three new read routes — /admin/elementor/status, /admin/elementor/{post_id} (GET), /admin/elementor/templates. Writes require `manage_options` AND `edit_post` on the target post (S-12). Block content is sanitised via `wp_kses_post` by default; `raw_html=true` only when the caller passes `manage_options + unfiltered_html` (S-13). Elementor JSON node count capped at 5,000 per call; oversized payloads return `elementor_too_large` (S-14). All Elementor writes fire `elementor/document/after_save` so caches and CSS regenerate cleanly.
 * 2.12.0 - F.19.3.1: Three more read-only admin routes ported from the legacy wordpress_advanced WP-CLI tools so they can run via the companion instead of `docker exec`. /admin/system-info (PHP/MySQL/WordPress versions + server software + memory limits), /admin/phpinfo (extension list + curated ini snapshot), /admin/disk-usage (uploads/plugins/themes/total bytes + disk_free_space). All gated on `manage_options`.
 * 2.11.0 - F.19.1: Read-only admin namespace ``airano-mcp/v1/admin/*`` for the WordPress Specialist tool surface. Six new routes — plugins, themes, users, options, cron, maintenance — all gated on ``manage_options``. No state changes in this version; write operations land in F.19.2 once user-supplied security rules are folded in.
 * 2.10.1 - F.X.fix #10: single-source the ``routes`` bitmap via SEO_API_Bridge::get_route_map(). capabilities and site_health previously duplicated the map with conflicting values (audit_hook=true vs false, missing upload_and_attach entries). Both now read from the shared constant.
 * 2.10.0 - F.X.fix #7: /upload-and-attach honours an ``Idempotency-Key`` header. A retry within 24h with the same key returns the already-created attachment (``_idempotent_replay: true``) rather than creating an "-2.webp" orphan. Protects against the orphan-on-client-timeout regression.
 * 2.9.0 - Added /airano-mcp/v1/upload-and-attach route for F.5a.8.5 (single-call raw-body upload + metadata + attach-to-post + set-featured; saves 2-3 REST round-trips per upload).
 * 2.8.0 - Added /airano-mcp/v1/regenerate-thumbnails route for F.5a.8.2 (rebuild attachment sub-sizes via wp_generate_attachment_metadata after uploads or format conversions; single-attachment or batch with offset/limit paging).
 * 2.7.0 - Added /airano-mcp/v1/audit-hook routes for F.18.7 (plugin pushes its own action log — post/user/plugin/theme events — to MCPHub with per-site HMAC-SHA256-signed webhooks; configured via GET/POST/DELETE on the same route; non-blocking wp_remote_post to keep the WP admin snappy).
 * 2.6.0 - Added /airano-mcp/v1/site-health route for F.18.6 (unified health snapshot: PHP/MySQL/WP versions, REST availability, disk free, active plugins, multisite flag, app-password policy).
 * 2.5.0 - Added /airano-mcp/v1/transient-flush route for F.18.5 (native PHP transient cleanup with expired/all/pattern scopes; optional site-transient handling on multisite).
 * 2.4.0 - Added /airano-mcp/v1/cache-purge route for F.18.4 (auto-detects active cache plugins — LiteSpeed, WP Rocket, W3 Total Cache, WP Super Cache, WP Fastest Cache, SG Optimizer — and triggers their purge API; always flushes object cache).
 * 2.3.0 - Added /airano-mcp/v1/export route for F.18.3 (structured JSON export of posts/pages/products with optional media, terms, and meta; supports post_type/status/since/limit/offset paging).
 * 2.2.0 - Added /airano-mcp/v1/bulk-meta route for F.18.2 (batch post/product meta writes in a single REST round-trip; backs wordpress_bulk_update_meta tool).
 * 2.1.0 - Added /airano-mcp/v1/capabilities route for F.18.1 (reports the effective capabilities of the calling application password so MCPHub's F.7e probe can decide which tools to expose).
 * 2.0.0 - Rebrand to Airano MCP Bridge. Added /airano-mcp/v1/upload-limits and /airano-mcp/v1/upload-chunk routes for F.5a.7 (media upload via raw body; bypasses PHP upload_max_filesize). SEO routes unchanged.
 * 1.3.0 - Added REST API endpoints for posts, pages, and products (GET/POST operations)
 * 1.2.0 - Enhanced WooCommerce product support, improved MariaDB compatibility
 * 1.1.0 - Added status endpoint and improved plugin detection
 * 1.0.0 - Initial release
 */

// Prevent direct access
if (!defined('ABSPATH')) {
    exit;
}

/**
 * Airano MCP Bridge Main Class
 *
 * Class name kept as `SEO_API_Bridge` for backwards compatibility with
 * existing installs — the plugin slug on wp.org is permanent.
 */
class SEO_API_Bridge {

    /**
     * Plugin version
     */
    const VERSION = '2.18.1';

    /**
     * Single source of truth for the ``routes`` bitmap exposed to
     * MCPHub. Advertises every /airano-mcp/v1/* endpoint this plugin
     * version actually registers. Mirror of register_rest_routes().
     *
     * F.X.fix #10 — capabilities and site_health previously duplicated
     * this map inline with subtly different values (audit_hook=true vs
     * false, missing upload_and_attach). Anything that reports route
     * availability to MCPHub must now read from here.
     */
    private static function get_route_map() {
        return [
            'seo_meta'              => true,
            'upload_limits'         => true,
            'upload_chunk'          => true,
            'upload_and_attach'     => true,
            'capabilities'          => true,
            'bulk_meta'             => true,
            'export'                => true,
            'cache_purge'           => true,
            'transient_flush'       => true,
            'site_health'           => true,
            'audit_hook'            => true,
            'regenerate_thumbnails' => true,
            // F.19.1 read-only admin namespace
            'admin_plugins'         => true,
            'admin_themes'          => true,
            'admin_users'           => true,
            'admin_options'         => true,
            'admin_cron'            => true,
            'admin_maintenance'     => true,
            // F.19.3.1 ports from wordpress_advanced (read-only)
            'admin_system_info'     => true,
            'admin_phpinfo'         => true,
            'admin_disk_usage'      => true,
            // F.19.5 page editing (Gutenberg + Elementor + Classic)
            'admin_blocks_replace'         => true,
            'admin_blocks_insert'          => true,
            'admin_blocks_remove'          => true,
            'admin_elementor_status'       => true,
            'admin_elementor_get'          => true,
            'admin_elementor_set'          => true,
            'admin_elementor_render_css'   => true,
            'admin_elementor_template_list'=> true,
            'admin_elementor_template_apply'=> true,
            'admin_classic_html_replace'   => true,
            // F.19.7 theme dev surface
            'admin_theme_install'          => true,
            'admin_theme_activate'         => true,
            'admin_theme_delete'           => true,
            'admin_theme_file_list'        => true,
            'admin_theme_file_read'        => true,
            'admin_theme_file_write'       => true,
            'admin_theme_file_delete'      => true,
            // F.19.2.1 plugin write management
            'admin_plugin_install'         => true,
            'admin_plugin_activate'        => true,
            'admin_plugin_deactivate'      => true,
            'admin_plugin_update'          => true,
            'admin_plugin_delete'          => true,
            // F.19.6.A site config (identity + reading + permalinks)
            'admin_site_identity_get'      => true,
            'admin_site_identity_set'      => true,
            'admin_site_reading_get'       => true,
            'admin_site_reading_set'       => true,
            'admin_permalinks_get'         => true,
            'admin_permalinks_set'         => true,
            // F.19.6.B site layout (menus + widgets + customizer)
            'admin_menus_list'             => true,
            'admin_menu_get'               => true,
            'admin_menu_set'               => true,
            'admin_widget_areas_list'      => true,
            'admin_widget_get'             => true,
            'admin_widget_set'             => true,
            'admin_customizer_changeset'   => true,
            // F.19.3.2-.3 database inspection (read-only)
            'admin_db_size'                => true,
            'admin_db_tables'              => true,
            'admin_db_search'              => true,
        ];
    }

    /**
     * Option keys that admin_option_get refuses to return — they
     * commonly hold credentials or per-install secrets. The whitelist
     * approach used by the rest of the plugin is wrong for this route
     * (the universe of safe option keys is too large), so we use a
     * deny-list of *suffix patterns* instead. F.19.1.
     */
    const ADMIN_OPTION_BLOCKED_PATTERNS = [
        '/(_|^)(secret|password|passwd|api[_-]?key|token|nonce_salt|auth_salt|secret_key)$/i',
        '/^(auth|secure_auth|logged_in|nonce)_(key|salt)$/i',
    ];

    /**
     * Option keys used by F.18.7 audit-hook persistence.
     */
    const AUDIT_OPT_ENABLED       = 'airano_mcp_audit_enabled';
    const AUDIT_OPT_ENDPOINT      = 'airano_mcp_audit_endpoint';
    const AUDIT_OPT_SECRET        = 'airano_mcp_audit_secret';
    const AUDIT_OPT_EVENTS        = 'airano_mcp_audit_events';
    const AUDIT_OPT_LAST_PUSH_GMT = 'airano_mcp_audit_last_push_gmt';
    const AUDIT_OPT_FAILURE_COUNT = 'airano_mcp_audit_failure_count';
    const AUDIT_OPT_LAST_ERROR    = 'airano_mcp_audit_last_error';

    /**
     * Default event list if the caller doesn't specify.
     */
    const AUDIT_DEFAULT_EVENTS = [
        'transition_post_status',
        'deleted_post',
        'user_register',
        'profile_update',
        'deleted_user',
        'activated_plugin',
        'deactivated_plugin',
        'switch_theme',
    ];

    /**
     * Supported post types
     */
    private $supported_post_types = ['post', 'page', 'product'];

    /**
     * Constructor
     */
    public function __construct() {
        add_action('rest_api_init', [$this, 'register_meta_fields']);
        add_action('rest_api_init', [$this, 'register_rest_routes']);
        add_action('admin_notices', [$this, 'admin_notices']);

        // Add product support message if WooCommerce is active
        if ($this->is_woocommerce_active()) {
            $this->supported_post_types[] = 'product_variation';  // Also support variations
        }

        // F.18.7: register audit hooks if the operator has configured a
        // MCPHub webhook endpoint. Hooks are idempotent when disabled.
        $this->audit_register_hooks();
    }

    /**
     * Register REST API routes
     */
    public function register_rest_routes() {
        // Status endpoint
        register_rest_route('airano-mcp-bridge/v1', '/status', [
            'methods' => 'GET',
            'callback' => [$this, 'get_status'],
            'permission_callback' => function() {
                return is_user_logged_in();
            }
        ]);

        // Post SEO endpoints
        register_rest_route('airano-mcp-bridge/v1', '/posts/(?P<id>\d+)/seo', [
            [
                'methods' => 'GET',
                'callback' => [$this, 'get_post_seo'],
                'permission_callback' => function() {
                    return current_user_can('edit_posts');
                },
                'args' => [
                    'id' => [
                        'validate_callback' => function($param) {
                            return is_numeric($param);
                        }
                    ]
                ]
            ],
            [
                'methods' => 'POST',
                'callback' => [$this, 'update_post_seo'],
                'permission_callback' => function() {
                    return current_user_can('edit_posts');
                },
                'args' => [
                    'id' => [
                        'validate_callback' => function($param) {
                            return is_numeric($param);
                        }
                    ]
                ]
            ]
        ]);

        // Page SEO endpoints
        register_rest_route('airano-mcp-bridge/v1', '/pages/(?P<id>\d+)/seo', [
            [
                'methods' => 'GET',
                'callback' => [$this, 'get_page_seo'],
                'permission_callback' => function() {
                    return current_user_can('edit_posts');
                },
                'args' => [
                    'id' => [
                        'validate_callback' => function($param) {
                            return is_numeric($param);
                        }
                    ]
                ]
            ],
            [
                'methods' => 'POST',
                'callback' => [$this, 'update_page_seo'],
                'permission_callback' => function() {
                    return current_user_can('edit_pages');
                },
                'args' => [
                    'id' => [
                        'validate_callback' => function($param) {
                            return is_numeric($param);
                        }
                    ]
                ]
            ]
        ]);

        // Product SEO endpoints (WooCommerce)
        register_rest_route('airano-mcp-bridge/v1', '/products/(?P<id>\d+)/seo', [
            [
                'methods' => 'GET',
                'callback' => [$this, 'get_product_seo'],
                'permission_callback' => function() {
                    return current_user_can('edit_posts');
                },
                'args' => [
                    'id' => [
                        'validate_callback' => function($param) {
                            return is_numeric($param);
                        }
                    ]
                ]
            ],
            [
                'methods' => 'POST',
                'callback' => [$this, 'update_product_seo'],
                'permission_callback' => function() {
                    return current_user_can('edit_posts');
                },
                'args' => [
                    'id' => [
                        'validate_callback' => function($param) {
                            return is_numeric($param);
                        }
                    ]
                ]
            ]
        ]);

        // --- F.5a.7: MCP Bridge upload helper routes -----------------------
        // Namespace: airano-mcp/v1 (separate from airano-mcp-bridge/v1 so
        // the SEO namespace stays focused and MCPHub probes a short URL).

        // GET /wp-json/airano-mcp/v1/upload-limits
        register_rest_route('airano-mcp/v1', '/upload-limits', [
            'methods' => 'GET',
            'callback' => [$this, 'get_upload_limits'],
            'permission_callback' => [$this, 'require_upload_capability'],
        ]);

        // POST /wp-json/airano-mcp/v1/upload-chunk
        // Accepts raw body (php://input) + Content-Type + Content-Disposition.
        // Bypasses PHP upload_max_filesize (still bounded by post_max_size).
        register_rest_route('airano-mcp/v1', '/upload-chunk', [
            'methods' => 'POST',
            'callback' => [$this, 'handle_upload_chunk'],
            'permission_callback' => [$this, 'require_upload_capability'],
        ]);

        // --- F.5a.8.5: single-call upload + metadata + attach + featured -
        // POST /wp-json/airano-mcp/v1/upload-and-attach
        // Same raw-body semantics as /upload-chunk, plus query params:
        //   ?attach_to_post=42
        //   ?set_featured=true|false
        //   ?title=...  ?alt_text=...  ?caption=...
        // All metadata application happens in-process so the caller saves
        // 2-3 round-trips compared to the upload → PATCH /media/{id} →
        // PATCH /posts/{id} sequence.
        register_rest_route('airano-mcp/v1', '/upload-and-attach', [
            'methods' => 'POST',
            'callback' => [$this, 'handle_upload_and_attach'],
            'permission_callback' => [$this, 'require_upload_and_attach_capability'],
        ]);

        // --- F.18.1: Capability probe ------------------------------------
        // GET /wp-json/airano-mcp/v1/capabilities
        // Reports the exact capability set of the calling application password
        // plus feature flags + available routes. Consumed by MCPHub's F.7e
        // probe to decide which tools to expose to the user.
        register_rest_route('airano-mcp/v1', '/capabilities', [
            'methods' => 'GET',
            'callback' => [$this, 'get_capabilities'],
            'permission_callback' => function () {
                return is_user_logged_in();
            },
        ]);

        // --- F.18.2: Bulk meta writes ------------------------------------
        // POST /wp-json/airano-mcp/v1/bulk-meta
        // Body: {"updates": [{"post_id": 123, "meta": {"k": "v", ...}}, ...]}
        // Loops in PHP: one HTTP round-trip for many post_meta writes.
        register_rest_route('airano-mcp/v1', '/bulk-meta', [
            'methods' => 'POST',
            'callback' => [$this, 'handle_bulk_meta'],
            'permission_callback' => function () {
                return current_user_can('edit_posts');
            },
        ]);

        // --- F.18.3: Structured JSON export ------------------------------
        // GET /wp-json/airano-mcp/v1/export
        // Query: post_type, status, since, limit, offset,
        //        include_media, include_terms, include_meta
        register_rest_route('airano-mcp/v1', '/export', [
            'methods' => 'GET',
            'callback' => [$this, 'handle_export'],
            'permission_callback' => function () {
                return current_user_can('edit_posts');
            },
        ]);

        // --- F.18.4: Cache purge (auto-detects active cache plugin) ------
        // POST /wp-json/airano-mcp/v1/cache-purge
        // Body (optional): {}  — currently always purges "all" + object cache.
        register_rest_route('airano-mcp/v1', '/cache-purge', [
            'methods' => 'POST',
            'callback' => [$this, 'handle_cache_purge'],
            'permission_callback' => function () {
                return current_user_can('manage_options');
            },
        ]);

        // --- F.18.5: Transient flush ------------------------------------
        // POST /wp-json/airano-mcp/v1/transient-flush
        // Body (optional): {"scope": "expired|all|pattern", "pattern": "foo_*",
        //                   "include_site_transients": true}
        register_rest_route('airano-mcp/v1', '/transient-flush', [
            'methods' => 'POST',
            'callback' => [$this, 'handle_transient_flush'],
            'permission_callback' => function () {
                return current_user_can('manage_options');
            },
        ]);

        // --- F.18.6: Unified site-health snapshot -----------------------
        // GET /wp-json/airano-mcp/v1/site-health
        register_rest_route('airano-mcp/v1', '/site-health', [
            'methods' => 'GET',
            'callback' => [$this, 'handle_site_health'],
            'permission_callback' => function () {
                return current_user_can('manage_options');
            },
        ]);

        // --- F.18.7: Audit hook configuration / status ------------------
        // GET    → current config (secret masked)
        // POST   → set endpoint_url / secret / enabled / events
        // DELETE → clear config (disables pushing)
        register_rest_route('airano-mcp/v1', '/audit-hook', [
            [
                'methods'             => 'GET',
                'callback'            => [$this, 'handle_audit_hook_get'],
                'permission_callback' => function () {
                    return current_user_can('manage_options');
                },
            ],
            [
                'methods'             => 'POST',
                'callback'            => [$this, 'handle_audit_hook_set'],
                'permission_callback' => function () {
                    return current_user_can('manage_options');
                },
            ],
            [
                'methods'             => 'DELETE',
                'callback'            => [$this, 'handle_audit_hook_clear'],
                'permission_callback' => function () {
                    return current_user_can('manage_options');
                },
            ],
        ]);

        // --- F.5a.8.2: Regenerate attachment thumbnails -----------------
        // POST /wp-json/airano-mcp/v1/regenerate-thumbnails
        // Body: { "ids": [int, ...] }   → regenerate sub-sizes for those
        //        attachments only.
        //      { "all": true, "offset": N, "limit": M }
        //        → batch mode; caps limit at 50 per request, returns
        //          { "processed": int, "errors": [...], "has_more": bool,
        //            "next_offset": int }.
        register_rest_route('airano-mcp/v1', '/regenerate-thumbnails', [
            'methods' => 'POST',
            'callback' => [$this, 'handle_regenerate_thumbnails'],
            'permission_callback' => function () {
                return current_user_can('upload_files') || current_user_can('manage_options');
            },
        ]);

        // ============================================================
        // F.19.1 — Read-only admin namespace (manage_options gated)
        // ============================================================
        register_rest_route('airano-mcp/v1', '/admin/plugins', [
            'methods' => 'GET',
            'callback' => [$this, 'handle_admin_plugins'],
            'permission_callback' => [$this, 'require_admin_capability'],
        ]);
        register_rest_route('airano-mcp/v1', '/admin/themes', [
            'methods' => 'GET',
            'callback' => [$this, 'handle_admin_themes'],
            'permission_callback' => [$this, 'require_admin_capability'],
        ]);
        register_rest_route('airano-mcp/v1', '/admin/users', [
            'methods' => 'GET',
            'callback' => [$this, 'handle_admin_users'],
            'permission_callback' => [$this, 'require_admin_capability'],
        ]);
        register_rest_route('airano-mcp/v1', '/admin/options/(?P<name>[A-Za-z0-9_\-]+)', [
            'methods' => 'GET',
            'callback' => [$this, 'handle_admin_option_get'],
            'permission_callback' => [$this, 'require_admin_capability'],
        ]);
        register_rest_route('airano-mcp/v1', '/admin/cron', [
            'methods' => 'GET',
            'callback' => [$this, 'handle_admin_cron'],
            'permission_callback' => [$this, 'require_admin_capability'],
        ]);
        register_rest_route('airano-mcp/v1', '/admin/maintenance', [
            'methods' => 'GET',
            'callback' => [$this, 'handle_admin_maintenance'],
            'permission_callback' => [$this, 'require_admin_capability'],
        ]);

        // ============================================================
        // F.19.3.1 — Ports from wordpress_advanced (read-only)
        // ============================================================
        register_rest_route('airano-mcp/v1', '/admin/system-info', [
            'methods' => 'GET',
            'callback' => [$this, 'handle_admin_system_info'],
            'permission_callback' => [$this, 'require_admin_capability'],
        ]);
        register_rest_route('airano-mcp/v1', '/admin/phpinfo', [
            'methods' => 'GET',
            'callback' => [$this, 'handle_admin_phpinfo'],
            'permission_callback' => [$this, 'require_admin_capability'],
        ]);
        register_rest_route('airano-mcp/v1', '/admin/disk-usage', [
            'methods' => 'GET',
            'callback' => [$this, 'handle_admin_disk_usage'],
            'permission_callback' => [$this, 'require_admin_capability'],
        ]);

        // ============================================================
        // F.19.5 — Page editing (Gutenberg blocks + Elementor + Classic)
        // ============================================================
        // Writes use a shared permission callback that enforces
        // `manage_options` AND `edit_post` on the target post (S-12).
        // The per-post check happens inside the handler because the
        // post id arrives in the JSON body for blocks, but in the URL
        // for elementor/classic. The base `manage_options` check is
        // still done at the route layer so non-admins are rejected
        // before any payload parsing.

        // Gutenberg block writes (S-12 + S-13).
        register_rest_route('airano-mcp/v1', '/admin/blocks/replace', [
            'methods' => 'POST',
            'callback' => [$this, 'handle_admin_blocks_replace'],
            'permission_callback' => [$this, 'require_admin_capability'],
        ]);
        register_rest_route('airano-mcp/v1', '/admin/blocks/insert', [
            'methods' => 'POST',
            'callback' => [$this, 'handle_admin_blocks_insert'],
            'permission_callback' => [$this, 'require_admin_capability'],
        ]);
        register_rest_route('airano-mcp/v1', '/admin/blocks/remove', [
            'methods' => 'POST',
            'callback' => [$this, 'handle_admin_blocks_remove'],
            'permission_callback' => [$this, 'require_admin_capability'],
        ]);

        // Elementor read.
        register_rest_route('airano-mcp/v1', '/admin/elementor/status', [
            'methods' => 'GET',
            'callback' => [$this, 'handle_admin_elementor_status'],
            'permission_callback' => [$this, 'require_admin_capability'],
        ]);
        register_rest_route('airano-mcp/v1', '/admin/elementor/templates', [
            'methods' => 'GET',
            'callback' => [$this, 'handle_admin_elementor_template_list'],
            'permission_callback' => [$this, 'require_admin_capability'],
        ]);
        register_rest_route('airano-mcp/v1', '/admin/elementor/(?P<post_id>\d+)', [
            'methods' => 'GET',
            'callback' => [$this, 'handle_admin_elementor_get'],
            'permission_callback' => [$this, 'require_admin_capability'],
        ]);

        // Elementor writes (S-12 + S-14).
        register_rest_route('airano-mcp/v1', '/admin/elementor/(?P<post_id>\d+)', [
            'methods' => 'POST',
            'callback' => [$this, 'handle_admin_elementor_set'],
            'permission_callback' => [$this, 'require_admin_capability'],
        ]);
        register_rest_route('airano-mcp/v1', '/admin/elementor/(?P<post_id>\d+)/regen-css', [
            'methods' => 'POST',
            'callback' => [$this, 'handle_admin_elementor_render_css'],
            'permission_callback' => [$this, 'require_admin_capability'],
        ]);
        register_rest_route('airano-mcp/v1', '/admin/elementor/templates/apply', [
            'methods' => 'POST',
            'callback' => [$this, 'handle_admin_elementor_template_apply'],
            'permission_callback' => [$this, 'require_admin_capability'],
        ]);

        // Classic editor fallback (S-12 + S-13).
        register_rest_route('airano-mcp/v1', '/admin/classic/(?P<post_id>\d+)/replace', [
            'methods' => 'POST',
            'callback' => [$this, 'handle_admin_classic_html_replace'],
            'permission_callback' => [$this, 'require_admin_capability'],
        ]);

        // ============================================================
        // F.19.7 — Theme dev surface (install + activate + delete +
        //          file CRUD). All gated on `manage_options` route-side;
        //          per-handler checks for install_themes / switch_themes /
        //          delete_themes / edit_themes (+ DISALLOW_FILE_EDIT for
        //          PHP writes — S-17).
        // ============================================================
        register_rest_route('airano-mcp/v1', '/admin/themes/install', [
            'methods' => 'POST',
            'callback' => [$this, 'handle_admin_theme_install'],
            'permission_callback' => [$this, 'require_admin_capability'],
        ]);
        register_rest_route('airano-mcp/v1', '/admin/themes/(?P<slug>[A-Za-z0-9][A-Za-z0-9_\-]{0,63})/activate', [
            'methods' => 'POST',
            'callback' => [$this, 'handle_admin_theme_activate'],
            'permission_callback' => [$this, 'require_admin_capability'],
        ]);
        register_rest_route('airano-mcp/v1', '/admin/themes/(?P<slug>[A-Za-z0-9][A-Za-z0-9_\-]{0,63})', [
            'methods' => 'DELETE',
            'callback' => [$this, 'handle_admin_theme_delete'],
            'permission_callback' => [$this, 'require_admin_capability'],
        ]);
        register_rest_route('airano-mcp/v1', '/admin/themes/files/(?P<slug>[A-Za-z0-9][A-Za-z0-9_\-]{0,63})', [
            'methods' => 'GET',
            'callback' => [$this, 'handle_admin_theme_file_list'],
            'permission_callback' => [$this, 'require_admin_capability'],
        ]);
        register_rest_route('airano-mcp/v1', '/admin/themes/files/(?P<slug>[A-Za-z0-9][A-Za-z0-9_\-]{0,63})/(?P<path>.+)', [
            'methods' => 'GET',
            'callback' => [$this, 'handle_admin_theme_file_read'],
            'permission_callback' => [$this, 'require_admin_capability'],
        ]);
        register_rest_route('airano-mcp/v1', '/admin/themes/files/(?P<slug>[A-Za-z0-9][A-Za-z0-9_\-]{0,63})/(?P<path>.+)', [
            'methods' => 'PUT',
            'callback' => [$this, 'handle_admin_theme_file_write'],
            'permission_callback' => [$this, 'require_admin_capability'],
        ]);
        register_rest_route('airano-mcp/v1', '/admin/themes/files/(?P<slug>[A-Za-z0-9][A-Za-z0-9_\-]{0,63})/(?P<path>.+)', [
            'methods' => 'DELETE',
            'callback' => [$this, 'handle_admin_theme_file_delete'],
            'permission_callback' => [$this, 'require_admin_capability'],
        ]);

        // ============================================================
        // F.19.2.1 — Plugin write management. Per-handler caps:
        //   install/update → install_plugins
        //   activate/deactivate → activate_plugins
        //   delete → delete_plugins
        // S-20: refuses to deactivate/delete the airano-mcp-bridge
        //       companion itself (would brick the MCP connection).
        // S-21: refuses to deactivate/delete plugins marked Required.
        // ============================================================
        register_rest_route('airano-mcp/v1', '/admin/plugins/install', [
            'methods' => 'POST',
            'callback' => [$this, 'handle_admin_plugin_install'],
            'permission_callback' => [$this, 'require_admin_capability'],
        ]);
        register_rest_route('airano-mcp/v1', '/admin/plugins/(?P<slug>[A-Za-z0-9][A-Za-z0-9_\-]{0,63})/activate', [
            'methods' => 'POST',
            'callback' => [$this, 'handle_admin_plugin_activate'],
            'permission_callback' => [$this, 'require_admin_capability'],
        ]);
        register_rest_route('airano-mcp/v1', '/admin/plugins/(?P<slug>[A-Za-z0-9][A-Za-z0-9_\-]{0,63})/deactivate', [
            'methods' => 'POST',
            'callback' => [$this, 'handle_admin_plugin_deactivate'],
            'permission_callback' => [$this, 'require_admin_capability'],
        ]);
        register_rest_route('airano-mcp/v1', '/admin/plugins/(?P<slug>[A-Za-z0-9][A-Za-z0-9_\-]{0,63})/update', [
            'methods' => 'POST',
            'callback' => [$this, 'handle_admin_plugin_update'],
            'permission_callback' => [$this, 'require_admin_capability'],
        ]);
        register_rest_route('airano-mcp/v1', '/admin/plugins/(?P<slug>[A-Za-z0-9][A-Za-z0-9_\-]{0,63})', [
            'methods' => 'DELETE',
            'callback' => [$this, 'handle_admin_plugin_delete'],
            'permission_callback' => [$this, 'require_admin_capability'],
        ]);

        // ============================================================
        // F.19.6.A — Site config (identity + reading + permalinks).
        // All routes gated on manage_options. Writes route every
        // option through WP's own sanitize_option_* hooks; permalink
        // writes additionally call flush_rewrite_rules().
        // ============================================================
        register_rest_route('airano-mcp/v1', '/admin/site/identity', [
            'methods' => 'GET',
            'callback' => [$this, 'handle_admin_site_identity_get'],
            'permission_callback' => [$this, 'require_admin_capability'],
        ]);
        register_rest_route('airano-mcp/v1', '/admin/site/identity', [
            'methods' => 'POST',
            'callback' => [$this, 'handle_admin_site_identity_set'],
            'permission_callback' => [$this, 'require_admin_capability'],
        ]);
        register_rest_route('airano-mcp/v1', '/admin/site/reading', [
            'methods' => 'GET',
            'callback' => [$this, 'handle_admin_site_reading_get'],
            'permission_callback' => [$this, 'require_admin_capability'],
        ]);
        register_rest_route('airano-mcp/v1', '/admin/site/reading', [
            'methods' => 'POST',
            'callback' => [$this, 'handle_admin_site_reading_set'],
            'permission_callback' => [$this, 'require_admin_capability'],
        ]);
        register_rest_route('airano-mcp/v1', '/admin/permalinks', [
            'methods' => 'GET',
            'callback' => [$this, 'handle_admin_permalinks_get'],
            'permission_callback' => [$this, 'require_admin_capability'],
        ]);
        register_rest_route('airano-mcp/v1', '/admin/permalinks', [
            'methods' => 'POST',
            'callback' => [$this, 'handle_admin_permalinks_set'],
            'permission_callback' => [$this, 'require_admin_capability'],
        ]);

        // ============================================================
        // F.19.6.B — Site layout (menus + widgets + customizer).
        // All routes gated on manage_options at the route level.
        // Per-request capability checks (S-22 / S-24) and content
        // sanitisation (S-23) live inside the handlers.
        // ============================================================
        register_rest_route('airano-mcp/v1', '/admin/menus', [
            'methods' => 'GET',
            'callback' => [$this, 'handle_admin_menus_list'],
            'permission_callback' => [$this, 'require_admin_capability'],
        ]);
        register_rest_route('airano-mcp/v1', '/admin/menus/(?P<menu_id>\d+)', [
            'methods' => 'GET',
            'callback' => [$this, 'handle_admin_menu_get'],
            'permission_callback' => [$this, 'require_admin_capability'],
        ]);
        register_rest_route('airano-mcp/v1', '/admin/menus/(?P<menu_id>\d+)', [
            'methods' => 'PUT',
            'callback' => [$this, 'handle_admin_menu_set'],
            'permission_callback' => [$this, 'require_admin_capability'],
        ]);
        register_rest_route('airano-mcp/v1', '/admin/widgets/areas', [
            'methods' => 'GET',
            'callback' => [$this, 'handle_admin_widget_areas_list'],
            'permission_callback' => [$this, 'require_admin_capability'],
        ]);
        register_rest_route('airano-mcp/v1', '/admin/widgets/(?P<area_id>[A-Za-z0-9_\-]+)', [
            'methods' => 'GET',
            'callback' => [$this, 'handle_admin_widget_get'],
            'permission_callback' => [$this, 'require_admin_capability'],
        ]);
        register_rest_route('airano-mcp/v1', '/admin/widgets/(?P<area_id>[A-Za-z0-9_\-]+)', [
            'methods' => 'PUT',
            'callback' => [$this, 'handle_admin_widget_set'],
            'permission_callback' => [$this, 'require_admin_capability'],
        ]);
        register_rest_route('airano-mcp/v1', '/admin/customizer/changeset', [
            'methods' => 'POST',
            'callback' => [$this, 'handle_admin_customizer_changeset'],
            'permission_callback' => [$this, 'require_admin_capability'],
        ]);

        // ============================================================
        // F.19.3.2-.3 — Database inspection (read-only).
        // No SQL exposure: db/size + db/tables aggregate
        // information_schema.TABLES server-side; db/search wraps
        // WP_Query with s=$query (S-25). All gated on manage_options.
        // ============================================================
        register_rest_route('airano-mcp/v1', '/admin/db/size', [
            'methods' => 'GET',
            'callback' => [$this, 'handle_admin_db_size'],
            'permission_callback' => [$this, 'require_admin_capability'],
        ]);
        register_rest_route('airano-mcp/v1', '/admin/db/tables', [
            'methods' => 'GET',
            'callback' => [$this, 'handle_admin_db_tables'],
            'permission_callback' => [$this, 'require_admin_capability'],
        ]);
        register_rest_route('airano-mcp/v1', '/admin/db/search', [
            'methods' => 'POST',
            'callback' => [$this, 'handle_admin_db_search'],
            'permission_callback' => [$this, 'require_admin_capability'],
        ]);
    }

    /**
     * Permission callback for upload helper routes.
     *
     * Allows users with either `upload_files` or `manage_options` capability.
     * `upload_files` is granted to Author+ roles by default.
     */
    public function require_upload_capability() {
        return current_user_can('upload_files') || current_user_can('manage_options');
    }

    /**
     * Permission callback for `/upload-and-attach`.
     *
     * Two-layer gate, enforced BEFORE the callback runs (per wp.org review
     * guidance — a capability check inside the callback is not visible to
     * static analysis):
     *   1. Caller must have `upload_files` (or `manage_options`).
     *   2. If `attach_to_post` is supplied, caller must also have
     *      `edit_post` on that specific target.
     *   3. If `set_featured` is supplied without an `attach_to_post`,
     *      reject — featured-image needs a target post.
     */
    public function require_upload_and_attach_capability( $request ) {
        if ( ! current_user_can('upload_files') && ! current_user_can('manage_options') ) {
            return new WP_Error(
                'rest_forbidden',
                __( 'Sorry, you are not allowed to upload files.', 'airano-mcp-bridge' ),
                ['status' => rest_authorization_required_code()]
            );
        }

        $attach_to_post = (int) $request->get_param('attach_to_post');
        $set_featured_raw = $request->get_param('set_featured');
        $set_featured = in_array(
            strtolower((string) $set_featured_raw),
            ['1', 'true', 'yes', 'on'],
            true
        );

        if ( $set_featured && $attach_to_post <= 0 ) {
            return new WP_Error(
                'rest_invalid_param',
                __( 'set_featured requires a valid attach_to_post target.', 'airano-mcp-bridge' ),
                ['status' => 400]
            );
        }

        if ( $attach_to_post > 0 && ! current_user_can('edit_post', $attach_to_post) ) {
            return new WP_Error(
                'rest_cannot_edit',
                __( 'Sorry, you are not allowed to attach media to this post.', 'airano-mcp-bridge' ),
                ['status' => rest_authorization_required_code(), 'attach_to_post' => $attach_to_post]
            );
        }

        return true;
    }

    /**
     * Permission callback for the F.19.1 admin namespace.
     *
     * Strict ``manage_options`` check — same bar as the WP Settings page.
     * Subscriber/Author/Editor roles are intentionally rejected here.
     */
    public function require_admin_capability() {
        return current_user_can('manage_options');
    }

    /**
     * Get plugin status endpoint
     */
    public function get_status() {
        $rank_math_active = $this->is_rank_math_active();
        $yoast_active = $this->is_yoast_active();

        $response = [
            'plugin' => 'Airano MCP Bridge',
            'version' => self::VERSION,
            'active' => true,
            'capabilities' => [
                'seo_meta'        => true,
                'upload_limits'   => true,
                'upload_chunk'    => true,
                'capabilities'    => true,
                'bulk_meta'       => true,
                'export'          => true,
                'cache_purge'     => true,
                'transient_flush' => true,
                'site_health'     => true,
                'audit_hook'      => true,
                'regenerate_thumbnails' => true,
                'upload_and_attach'     => true,
            ],
            'seo_plugins' => [
                'rank_math' => [
                    'active' => $rank_math_active,
                    'version' => $rank_math_active && defined('RANK_MATH_VERSION') ? RANK_MATH_VERSION : null
                ],
                'yoast' => [
                    'active' => $yoast_active,
                    'version' => $yoast_active && defined('WPSEO_VERSION') ? WPSEO_VERSION : null
                ]
            ],
            'supported_post_types' => $this->supported_post_types,
            'message' => $this->get_status_message($rank_math_active, $yoast_active)
        ];

        return rest_ensure_response($response);
    }

    /**
     * Get status message based on active plugins
     */
    private function get_status_message($rank_math_active, $yoast_active) {
        if (!$rank_math_active && !$yoast_active) {
            return 'No SEO plugin detected. Please install and activate Rank Math SEO or Yoast SEO.';
        }

        $active_plugins = [];
        if ($rank_math_active) $active_plugins[] = 'Rank Math SEO';
        if ($yoast_active) $active_plugins[] = 'Yoast SEO';

        return 'Airano MCP SEO Meta Bridge is active and working with ' . implode(' and ', $active_plugins) . '.';
    }

    /**
     * Register all meta fields for REST API
     */
    public function register_meta_fields() {
        // Register Rank Math fields if plugin is active
        if ($this->is_rank_math_active()) {
            $this->register_rank_math_fields();
        }

        // Register Yoast SEO fields if plugin is active
        if ($this->is_yoast_active()) {
            $this->register_yoast_fields();
        }
    }

    /**
     * Check if Rank Math is active
     */
    private function is_rank_math_active() {
        return defined('RANK_MATH_VERSION') || class_exists('RankMath');
    }

    /**
     * Check if Yoast SEO is active
     */
    private function is_yoast_active() {
        return defined('WPSEO_VERSION') || class_exists('WPSEO_Options');
    }

    /**
     * Check if WooCommerce is active
     */
    private function is_woocommerce_active() {
        return class_exists('WooCommerce') || defined('WC_VERSION');
    }

    /**
     * Register Rank Math meta fields
     */
    private function register_rank_math_fields() {
        $rank_math_fields = [
            // Core SEO Fields
            'rank_math_focus_keyword' => [
                'type' => 'string',
                'description' => 'Rank Math focus keyword',
                'single' => true,
            ],
            'rank_math_title' => [
                'type' => 'string',
                'description' => 'Rank Math SEO title (meta title)',
                'single' => true,
            ],
            'rank_math_description' => [
                'type' => 'string',
                'description' => 'Rank Math meta description',
                'single' => true,
            ],

            // Additional Keywords
            'rank_math_additional_keywords' => [
                'type' => 'string',
                'description' => 'Rank Math additional keywords (comma-separated)',
                'single' => true,
            ],

            // Advanced Fields
            'rank_math_canonical_url' => [
                'type' => 'string',
                'description' => 'Rank Math canonical URL',
                'single' => true,
            ],
            'rank_math_robots' => [
                'type' => 'array',
                'description' => 'Rank Math robots meta (noindex, nofollow, etc.)',
                'single' => true,
            ],
            'rank_math_breadcrumb_title' => [
                'type' => 'string',
                'description' => 'Rank Math breadcrumb title',
                'single' => true,
            ],

            // Open Graph Fields
            'rank_math_facebook_title' => [
                'type' => 'string',
                'description' => 'Rank Math Facebook Open Graph title',
                'single' => true,
            ],
            'rank_math_facebook_description' => [
                'type' => 'string',
                'description' => 'Rank Math Facebook Open Graph description',
                'single' => true,
            ],
            'rank_math_facebook_image' => [
                'type' => 'string',
                'description' => 'Rank Math Facebook Open Graph image URL',
                'single' => true,
            ],
            'rank_math_facebook_image_id' => [
                'type' => 'integer',
                'description' => 'Rank Math Facebook Open Graph image ID',
                'single' => true,
            ],

            // Twitter Card Fields
            'rank_math_twitter_title' => [
                'type' => 'string',
                'description' => 'Rank Math Twitter Card title',
                'single' => true,
            ],
            'rank_math_twitter_description' => [
                'type' => 'string',
                'description' => 'Rank Math Twitter Card description',
                'single' => true,
            ],
            'rank_math_twitter_image' => [
                'type' => 'string',
                'description' => 'Rank Math Twitter Card image URL',
                'single' => true,
            ],
            'rank_math_twitter_image_id' => [
                'type' => 'integer',
                'description' => 'Rank Math Twitter Card image ID',
                'single' => true,
            ],
            'rank_math_twitter_card_type' => [
                'type' => 'string',
                'description' => 'Rank Math Twitter Card type (summary, summary_large_image)',
                'single' => true,
            ],
        ];

        $this->register_fields($rank_math_fields);
    }

    /**
     * Register Yoast SEO meta fields
     */
    private function register_yoast_fields() {
        $yoast_fields = [
            // Core SEO Fields
            '_yoast_wpseo_focuskw' => [
                'type' => 'string',
                'description' => 'Yoast SEO focus keyword',
                'single' => true,
            ],
            '_yoast_wpseo_title' => [
                'type' => 'string',
                'description' => 'Yoast SEO title (meta title)',
                'single' => true,
            ],
            '_yoast_wpseo_metadesc' => [
                'type' => 'string',
                'description' => 'Yoast SEO meta description',
                'single' => true,
            ],

            // Advanced Fields
            '_yoast_wpseo_canonical' => [
                'type' => 'string',
                'description' => 'Yoast SEO canonical URL',
                'single' => true,
            ],
            '_yoast_wpseo_meta-robots-noindex' => [
                'type' => 'string',
                'description' => 'Yoast SEO noindex setting (0 = index, 1 = noindex)',
                'single' => true,
            ],
            '_yoast_wpseo_meta-robots-nofollow' => [
                'type' => 'string',
                'description' => 'Yoast SEO nofollow setting (0 = follow, 1 = nofollow)',
                'single' => true,
            ],
            '_yoast_wpseo_bctitle' => [
                'type' => 'string',
                'description' => 'Yoast SEO breadcrumb title',
                'single' => true,
            ],

            // Open Graph Fields
            '_yoast_wpseo_opengraph-title' => [
                'type' => 'string',
                'description' => 'Yoast SEO Open Graph title',
                'single' => true,
            ],
            '_yoast_wpseo_opengraph-description' => [
                'type' => 'string',
                'description' => 'Yoast SEO Open Graph description',
                'single' => true,
            ],
            '_yoast_wpseo_opengraph-image' => [
                'type' => 'string',
                'description' => 'Yoast SEO Open Graph image URL',
                'single' => true,
            ],
            '_yoast_wpseo_opengraph-image-id' => [
                'type' => 'integer',
                'description' => 'Yoast SEO Open Graph image ID',
                'single' => true,
            ],

            // Twitter Card Fields
            '_yoast_wpseo_twitter-title' => [
                'type' => 'string',
                'description' => 'Yoast SEO Twitter title',
                'single' => true,
            ],
            '_yoast_wpseo_twitter-description' => [
                'type' => 'string',
                'description' => 'Yoast SEO Twitter description',
                'single' => true,
            ],
            '_yoast_wpseo_twitter-image' => [
                'type' => 'string',
                'description' => 'Yoast SEO Twitter image URL',
                'single' => true,
            ],
            '_yoast_wpseo_twitter-image-id' => [
                'type' => 'integer',
                'description' => 'Yoast SEO Twitter image ID',
                'single' => true,
            ],
        ];

        $this->register_fields($yoast_fields);
    }

    /**
     * Register fields for all supported post types
     */
    private function register_fields($fields) {
        foreach ($this->supported_post_types as $post_type) {
            foreach ($fields as $meta_key => $args) {
                $show_in_rest = $args['type'] === 'array'
                    ? [ 'schema' => [ 'type' => 'array', 'items' => [ 'type' => 'string' ] ] ]
                    : true;

                register_post_meta($post_type, $meta_key, [
                    'show_in_rest' => $show_in_rest,
                    'single' => $args['single'],
                    'type' => $args['type'],
                    'description' => $args['description'],
                    'auth_callback' => function() {
                        return current_user_can('edit_posts');
                    }
                ]);
            }
        }
    }

    /**
     * Get SEO data for a post
     */
    public function get_post_seo($request) {
        $post_id = $request['id'];
        return $this->get_seo_data($post_id, 'post');
    }

    /**
     * Update SEO data for a post
     */
    public function update_post_seo($request) {
        $post_id = $request['id'];
        return $this->update_seo_data($post_id, $request->get_json_params(), 'post');
    }

    /**
     * Get SEO data for a page
     */
    public function get_page_seo($request) {
        $post_id = $request['id'];
        return $this->get_seo_data($post_id, 'page');
    }

    /**
     * Update SEO data for a page
     */
    public function update_page_seo($request) {
        $post_id = $request['id'];
        return $this->update_seo_data($post_id, $request->get_json_params(), 'page');
    }

    /**
     * Get SEO data for a product
     */
    public function get_product_seo($request) {
        $post_id = $request['id'];
        return $this->get_seo_data($post_id, 'product');
    }

    /**
     * Update SEO data for a product
     */
    public function update_product_seo($request) {
        $post_id = $request['id'];
        return $this->update_seo_data($post_id, $request->get_json_params(), 'product');
    }

    /**
     * Generic method to get SEO data
     */
    private function get_seo_data($post_id, $post_type) {
        // Verify post exists and is correct type
        $post = get_post($post_id);
        if (!$post || $post->post_type !== $post_type) {
            return new WP_Error(
                'invalid_post',
                /* translators: %s: post type label (e.g. Post, Page, Product). */
                sprintf( __( '%s not found', 'airano-mcp-bridge' ), ucfirst( $post_type ) ),
                ['status' => 404]
            );
        }

        $seo_data = [
            'post_id' => $post_id,
            'post_type' => $post_type,
            'post_title' => $post->post_title,
        ];

        // Detect which SEO plugin is active and get data
        if ($this->is_rank_math_active()) {
            $seo_data['plugin'] = 'rank_math';
            $seo_data = array_merge($seo_data, $this->get_rank_math_data($post_id));
        } elseif ($this->is_yoast_active()) {
            $seo_data['plugin'] = 'yoast';
            $seo_data = array_merge($seo_data, $this->get_yoast_data($post_id));
        } else {
            return new WP_Error(
                'no_seo_plugin',
                __( 'No supported SEO plugin found (Rank Math or Yoast required).', 'airano-mcp-bridge' ),
                ['status' => 500]
            );
        }

        return rest_ensure_response($seo_data);
    }

    /**
     * Get Rank Math SEO data
     */
    private function get_rank_math_data($post_id) {
        return [
            'focus_keyword' => get_post_meta($post_id, 'rank_math_focus_keyword', true),
            'seo_title' => get_post_meta($post_id, 'rank_math_title', true),
            'meta_description' => get_post_meta($post_id, 'rank_math_description', true),
            'canonical_url' => get_post_meta($post_id, 'rank_math_canonical_url', true),
            'robots' => get_post_meta($post_id, 'rank_math_robots', true),
            'og_title' => get_post_meta($post_id, 'rank_math_facebook_title', true),
            'og_description' => get_post_meta($post_id, 'rank_math_facebook_description', true),
            'og_image' => get_post_meta($post_id, 'rank_math_facebook_image', true),
            'twitter_title' => get_post_meta($post_id, 'rank_math_twitter_title', true),
            'twitter_description' => get_post_meta($post_id, 'rank_math_twitter_description', true),
            'twitter_image' => get_post_meta($post_id, 'rank_math_twitter_image', true),
        ];
    }

    /**
     * Get Yoast SEO data
     */
    private function get_yoast_data($post_id) {
        return [
            'focus_keyword' => get_post_meta($post_id, '_yoast_wpseo_focuskw', true),
            'seo_title' => get_post_meta($post_id, '_yoast_wpseo_title', true),
            'meta_description' => get_post_meta($post_id, '_yoast_wpseo_metadesc', true),
            'canonical_url' => get_post_meta($post_id, '_yoast_wpseo_canonical', true),
            'noindex' => get_post_meta($post_id, '_yoast_wpseo_meta-robots-noindex', true),
            'nofollow' => get_post_meta($post_id, '_yoast_wpseo_meta-robots-nofollow', true),
            'og_title' => get_post_meta($post_id, '_yoast_wpseo_opengraph-title', true),
            'og_description' => get_post_meta($post_id, '_yoast_wpseo_opengraph-description', true),
            'og_image' => get_post_meta($post_id, '_yoast_wpseo_opengraph-image', true),
            'twitter_title' => get_post_meta($post_id, '_yoast_wpseo_twitter-title', true),
            'twitter_description' => get_post_meta($post_id, '_yoast_wpseo_twitter-description', true),
            'twitter_image' => get_post_meta($post_id, '_yoast_wpseo_twitter-image', true),
        ];
    }

    /**
     * Generic method to update SEO data
     */
    private function update_seo_data($post_id, $params, $post_type) {
        // Verify post exists and is correct type
        $post = get_post($post_id);
        if (!$post || $post->post_type !== $post_type) {
            return new WP_Error(
                'invalid_post',
                /* translators: %s: post type label (e.g. Post, Page, Product). */
                sprintf( __( '%s not found', 'airano-mcp-bridge' ), ucfirst( $post_type ) ),
                ['status' => 404]
            );
        }

        $updated_fields = [];

        // Update based on active SEO plugin
        if ($this->is_rank_math_active()) {
            $updated_fields = $this->update_rank_math_data($post_id, $params);
        } elseif ($this->is_yoast_active()) {
            $updated_fields = $this->update_yoast_data($post_id, $params);
        } else {
            return new WP_Error(
                'no_seo_plugin',
                __( 'No supported SEO plugin found.', 'airano-mcp-bridge' ),
                ['status' => 500]
            );
        }

        return rest_ensure_response([
            'post_id' => $post_id,
            'post_type' => $post_type,
            'updated_fields' => $updated_fields,
            'message' => __( 'SEO metadata updated successfully.', 'airano-mcp-bridge' ),
        ]);
    }

    /**
     * Update Rank Math data
     */
    private function update_rank_math_data($post_id, $params) {
        $updated = [];
        $field_map = [
            'focus_keyword' => 'rank_math_focus_keyword',
            'seo_title' => 'rank_math_title',
            'meta_description' => 'rank_math_description',
            'canonical_url' => 'rank_math_canonical_url',
            'robots' => 'rank_math_robots',
            'og_title' => 'rank_math_facebook_title',
            'og_description' => 'rank_math_facebook_description',
            'og_image' => 'rank_math_facebook_image',
            'twitter_title' => 'rank_math_twitter_title',
            'twitter_description' => 'rank_math_twitter_description',
            'twitter_image' => 'rank_math_twitter_image',
        ];

        foreach ($field_map as $param_key => $meta_key) {
            if (isset($params[$param_key])) {
                update_post_meta($post_id, $meta_key, $params[$param_key]);
                $updated[] = $meta_key;
            }
        }

        return $updated;
    }

    /**
     * Update Yoast data
     */
    private function update_yoast_data($post_id, $params) {
        $updated = [];
        $field_map = [
            'focus_keyword' => '_yoast_wpseo_focuskw',
            'seo_title' => '_yoast_wpseo_title',
            'meta_description' => '_yoast_wpseo_metadesc',
            'canonical_url' => '_yoast_wpseo_canonical',
            'og_title' => '_yoast_wpseo_opengraph-title',
            'og_description' => '_yoast_wpseo_opengraph-description',
            'og_image' => '_yoast_wpseo_opengraph-image',
            'twitter_title' => '_yoast_wpseo_twitter-title',
            'twitter_description' => '_yoast_wpseo_twitter-description',
            'twitter_image' => '_yoast_wpseo_twitter-image',
        ];

        foreach ($field_map as $param_key => $meta_key) {
            if (isset($params[$param_key])) {
                update_post_meta($post_id, $meta_key, $params[$param_key]);
                $updated[] = $meta_key;
            }
        }

        return $updated;
    }

    // ------------------------------------------------------------------
    //  F.5a.7 — Upload helper routes (airano-mcp/v1 namespace)
    // ------------------------------------------------------------------

    /**
     * GET /airano-mcp/v1/upload-limits
     *
     * Returns the effective PHP + WordPress upload limits so MCPHub can
     * decide which upload path to use (REST /wp/v2/media vs companion
     * upload-chunk). Shape matches plugins/wordpress/handlers/media_probe.py.
     */
    public function get_upload_limits() {
        $wp_max = function_exists('wp_max_upload_size') ? (int) wp_max_upload_size() : null;

        $response = [
            'upload_max_filesize' => (string) ini_get('upload_max_filesize'),
            'post_max_size'       => (string) ini_get('post_max_size'),
            'memory_limit'        => (string) ini_get('memory_limit'),
            'max_input_time'      => (string) ini_get('max_input_time'),
            'wp_max_upload_size'  => $wp_max,
            'plugin_version'      => self::VERSION,
            'companion'           => true,
        ];

        return rest_ensure_response($response);
    }

    /**
     * POST /airano-mcp/v1/upload-chunk
     *
     * Accepts a raw binary body (via php://input) plus Content-Type and
     * Content-Disposition headers, writes it to the media library via
     * wp_handle_sideload() + wp_insert_attachment() + wp_update_attachment_metadata().
     *
     * Returns a JSON attachment shape matching /wp/v2/media so MCPHub can
     * reuse the same parser.
     *
     * Security:
     *  - Auth: application password + upload_files or manage_options capability
     *  - MIME: validated against WP's allowed list via wp_check_filetype()
     *  - Filename: sanitized via sanitize_file_name()
     */
    public function handle_upload_chunk($request) {
        // Read raw body. Note: php://input is not affected by upload_max_filesize,
        // but IS still bounded by post_max_size and memory_limit.
        $body = $request->get_body();
        if ($body === null || $body === '') {
            return new WP_Error(
                'empty_body',
                __( 'Request body is empty. Send raw binary file data.', 'airano-mcp-bridge' ),
                ['status' => 400]
            );
        }

        $content_type = $request->get_header('content_type');
        if (empty($content_type)) {
            $content_type = 'application/octet-stream';
        }

        // Parse Content-Disposition to extract filename.
        $disposition = $request->get_header('content_disposition');
        $filename = $this->parse_content_disposition_filename($disposition);
        if (empty($filename)) {
            // Fall back to a safe generic filename; wp_check_filetype will
            // derive an extension from the MIME if one is mapped.
            $ext = '';
            $guess = wp_check_filetype('x.' . $this->mime_to_ext($content_type));
            if (!empty($guess['ext'])) {
                $ext = '.' . $guess['ext'];
            }
            $filename = 'upload-' . time() . $ext;
        }
        $filename = sanitize_file_name($filename);

        // Validate MIME against WP's allowed types.
        $check = wp_check_filetype($filename);
        if (empty($check['type'])) {
            return new WP_Error(
                'invalid_mime',
                __( 'File type is not allowed by this WordPress installation.', 'airano-mcp-bridge' ),
                ['status' => 400, 'filename' => $filename]
            );
        }

        // wp_tempnam() + wp_handle_sideload() live in file.php;
        // wp_generate_attachment_metadata() lives in image.php. media.php
        // is intentionally NOT loaded — none of its helpers are called here.
        require_once ABSPATH . 'wp-admin/includes/file.php';
        require_once ABSPATH . 'wp-admin/includes/image.php';

        $tmp = wp_tempnam($filename);
        if (!$tmp) {
            return new WP_Error(
                'tmp_failed',
                __( 'Could not create temp file.', 'airano-mcp-bridge' ),
                ['status' => 500]
            );
        }
        $written = $this->write_temp_body( $tmp, $body );
        if ($written === false) {
            wp_delete_file($tmp);
            return new WP_Error(
                'write_failed',
                __( 'Could not write payload to temp file.', 'airano-mcp-bridge' ),
                ['status' => 500]
            );
        }

        $file_array = [
            'name'     => $filename,
            'type'     => $content_type,
            'tmp_name' => $tmp,
            'error'    => 0,
            'size'     => filesize($tmp),
        ];

        $overrides = [
            'test_form' => false,
            'test_size' => true,
        ];

        $sideload = wp_handle_sideload($file_array, $overrides);
        if (isset($sideload['error'])) {
            wp_delete_file($tmp);
            return new WP_Error(
                'sideload_failed',
                (string) $sideload['error'],
                ['status' => 400]
            );
        }

        $attachment = [
            'post_mime_type' => $sideload['type'],
            'post_title'     => sanitize_text_field(pathinfo($filename, PATHINFO_FILENAME)),
            'post_content'   => '',
            'post_status'    => 'inherit',
        ];

        $attach_id = wp_insert_attachment($attachment, $sideload['file']);
        if (is_wp_error($attach_id) || !$attach_id) {
            wp_delete_file($sideload['file']);
            return new WP_Error(
                'insert_failed',
                is_wp_error($attach_id)
                    ? $attach_id->get_error_message()
                    : __( 'wp_insert_attachment failed.', 'airano-mcp-bridge' ),
                ['status' => 500]
            );
        }

        $metadata = wp_generate_attachment_metadata($attach_id, $sideload['file']);
        wp_update_attachment_metadata($attach_id, $metadata);

        // Build response with same shape as /wp/v2/media so MCPHub's parser
        // continues to work unchanged.
        $response = $this->format_attachment_response($attach_id, $sideload, $metadata);
        return rest_ensure_response($response);
    }

    /**
     * POST /airano-mcp/v1/upload-and-attach
     *
     * F.5a.8.5: raw-body upload, then in one PHP call apply metadata and
     * optionally attach to a post and mark as the post's featured image.
     * Replaces 2-3 REST round-trips with one.
     *
     * Same raw-body semantics as /upload-chunk. Metadata comes from query
     * params (URL-encoded):
     *   attach_to_post  — positive int
     *   set_featured    — "1" / "true" to mark as the post's featured image;
     *                     requires attach_to_post to also be set.
     *   title           — attachment title override (otherwise derived from filename)
     *   alt_text        — stored as post_meta _wp_attachment_image_alt
     *   caption         — stored as post_excerpt
     *   description     — stored as post_content
     *
     * Returns the same /wp/v2/media-shaped response as upload-chunk, plus
     * ``_upload_and_attach: { attach_to_post, set_featured, applied_meta }``
     * so the caller can verify what actually happened.
     */
    public function handle_upload_and_attach($request) {
        // --- F.X.fix #7: idempotent replay --------------------------------
        // Clients generate a stable ``Idempotency-Key`` header per
        // logical upload. If a client timed out mid-call and retried,
        // we return the already-created attachment rather than
        // producing an "-2.webp" orphan. Transient TTL 24h.
        $idempotency_key = $request->get_header('idempotency_key');
        if (is_string($idempotency_key) && $idempotency_key !== ''
            && preg_match('/^[A-Za-z0-9_\-]{1,128}$/', $idempotency_key)) {
            $cached_id = get_transient('airano_idemp_' . md5($idempotency_key));
            if ($cached_id) {
                $cached_post = get_post((int) $cached_id);
                if ($cached_post && $cached_post->post_type === 'attachment') {
                    $replay = $this->format_idempotent_replay((int) $cached_id);
                    return rest_ensure_response($replay);
                }
            }
        }

        // --- Same raw-body upload as handle_upload_chunk -----------------
        $body = $request->get_body();
        if ($body === null || $body === '') {
            return new WP_Error(
                'empty_body',
                __( 'Request body is empty. Send raw binary file data.', 'airano-mcp-bridge' ),
                ['status' => 400]
            );
        }

        $content_type = $request->get_header('content_type');
        if (empty($content_type)) {
            $content_type = 'application/octet-stream';
        }

        $disposition = $request->get_header('content_disposition');
        $filename = $this->parse_content_disposition_filename($disposition);
        if (empty($filename)) {
            $ext = '';
            $guess = wp_check_filetype('x.' . $this->mime_to_ext($content_type));
            if (!empty($guess['ext'])) {
                $ext = '.' . $guess['ext'];
            }
            $filename = 'upload-' . time() . $ext;
        }
        $filename = sanitize_file_name($filename);

        $check = wp_check_filetype($filename);
        if (empty($check['type'])) {
            return new WP_Error(
                'invalid_mime',
                __( 'File type is not allowed by this WordPress installation.', 'airano-mcp-bridge' ),
                ['status' => 400, 'filename' => $filename]
            );
        }

        // file.php → wp_tempnam, wp_handle_sideload; image.php →
        // wp_generate_attachment_metadata. media.php is NOT needed — none
        // of its helpers are used in this REST callback.
        require_once ABSPATH . 'wp-admin/includes/file.php';
        require_once ABSPATH . 'wp-admin/includes/image.php';

        $tmp = wp_tempnam($filename);
        if (!$tmp) {
            return new WP_Error(
                'tmp_failed',
                __( 'Could not create temp file.', 'airano-mcp-bridge' ),
                ['status' => 500]
            );
        }
        $written = $this->write_temp_body( $tmp, $body );
        if ($written === false) {
            wp_delete_file($tmp);
            return new WP_Error(
                'write_failed',
                __( 'Could not write payload to temp file.', 'airano-mcp-bridge' ),
                ['status' => 500]
            );
        }

        $file_array = [
            'name'     => $filename,
            'type'     => $content_type,
            'tmp_name' => $tmp,
            'error'    => 0,
            'size'     => filesize($tmp),
        ];
        $sideload = wp_handle_sideload($file_array, ['test_form' => false, 'test_size' => true]);
        if (isset($sideload['error'])) {
            wp_delete_file($tmp);
            return new WP_Error('sideload_failed', (string) $sideload['error'], ['status' => 400]);
        }

        // --- Gather query params -----------------------------------------
        $attach_to_post = (int) $request->get_param('attach_to_post');
        $set_featured   = filter_var(
            $request->get_param('set_featured'),
            FILTER_VALIDATE_BOOLEAN,
            FILTER_NULL_ON_FAILURE
        );
        $title_override = $request->get_param('title');
        $alt_text       = $request->get_param('alt_text');
        $caption        = $request->get_param('caption');
        $description    = $request->get_param('description');

        // set_featured requires a target post; silently drop otherwise.
        if ($attach_to_post <= 0) {
            $attach_to_post = 0;
            $set_featured = false;
        }

        // Per-target permission check when attaching.
        if ($attach_to_post > 0 && ! current_user_can('edit_post', $attach_to_post)) {
            wp_delete_file($sideload['file']);
            return new WP_Error(
                'cannot_edit_target',
                __( 'Current user lacks edit_post on attach_to_post target.', 'airano-mcp-bridge' ),
                ['status' => 403, 'attach_to_post' => $attach_to_post]
            );
        }

        // --- Insert attachment with desired parent + title ---------------
        $attachment = [
            'post_mime_type' => $sideload['type'],
            'post_title'     => is_string($title_override) && $title_override !== ''
                                  ? sanitize_text_field($title_override)
                                  : sanitize_text_field(pathinfo($filename, PATHINFO_FILENAME)),
            'post_content'   => is_string($description) ? wp_kses_post($description) : '',
            'post_excerpt'   => is_string($caption) ? sanitize_text_field($caption) : '',
            'post_status'    => 'inherit',
            'post_parent'    => $attach_to_post,
        ];

        $attach_id = wp_insert_attachment($attachment, $sideload['file'], $attach_to_post);
        if (is_wp_error($attach_id) || !$attach_id) {
            wp_delete_file($sideload['file']);
            return new WP_Error(
                'insert_failed',
                is_wp_error($attach_id)
                    ? $attach_id->get_error_message()
                    : __( 'wp_insert_attachment failed.', 'airano-mcp-bridge' ),
                ['status' => 500]
            );
        }

        // --- Alt text (stored in post_meta, not post_excerpt) ------------
        $applied_alt = false;
        if (is_string($alt_text) && $alt_text !== '') {
            update_post_meta($attach_id, '_wp_attachment_image_alt', sanitize_text_field($alt_text));
            $applied_alt = true;
        }

        // --- Metadata rebuild (thumbnails, EXIF, etc.) -------------------
        $metadata = wp_generate_attachment_metadata($attach_id, $sideload['file']);
        wp_update_attachment_metadata($attach_id, $metadata);

        // --- Set as featured image ---------------------------------------
        $applied_featured = false;
        if ($set_featured && $attach_to_post > 0) {
            $ok = update_post_meta($attach_to_post, '_thumbnail_id', $attach_id);
            $applied_featured = (bool) $ok;
        }

        $response = $this->format_attachment_response($attach_id, $sideload, $metadata);
        if (is_array($response)) {
            $response['_upload_and_attach'] = [
                'attach_to_post' => $attach_to_post ?: null,
                'set_featured'   => $applied_featured,
                'applied_meta'   => [
                    'title'       => isset($attachment['post_title']) ? $attachment['post_title'] : null,
                    'alt_text'    => $applied_alt,
                    'caption'     => is_string($caption) && $caption !== '',
                    'description' => is_string($description) && $description !== '',
                ],
            ];
        }

        // F.X.fix #7: record the (idempotency_key -> attach_id) mapping
        // so a retry within 24h gets the same id back.
        if (is_string($idempotency_key) && $idempotency_key !== ''
            && preg_match('/^[A-Za-z0-9_\-]{1,128}$/', $idempotency_key)) {
            set_transient(
                'airano_idemp_' . md5($idempotency_key),
                (int) $attach_id,
                24 * HOUR_IN_SECONDS
            );
        }

        return rest_ensure_response($response);
    }

    /**
     * Build a replay response for an already-created attachment.
     *
     * Called when the client retries with a matching Idempotency-Key.
     * We re-derive just enough of the ``/wp/v2/media`` shape from the
     * stored attachment so the Python side sees the same ``id``,
     * ``source_url``, ``mime_type`` as the original response, plus an
     * ``_idempotent_replay: true`` marker for audit logs.
     */
    private function format_idempotent_replay($attach_id) {
        $post = get_post($attach_id);
        $mime = $post ? (string) $post->post_mime_type : '';
        $source_url = wp_get_attachment_url($attach_id);
        return [
            'id'                  => (int) $attach_id,
            'date'                => $post ? mysql_to_rfc3339($post->post_date) : null,
            'slug'                => $post ? $post->post_name : '',
            'type'                => 'attachment',
            'link'                => get_permalink($attach_id),
            'title'               => ['rendered' => $post ? $post->post_title : ''],
            'author'              => $post ? (int) $post->post_author : 0,
            'post'                => $post ? (int) $post->post_parent : 0,
            'mime_type'           => $mime,
            'media_type'          => $this->mime_to_media_type($mime),
            'source_url'          => $source_url,
            'media_details'       => wp_get_attachment_metadata($attach_id) ?: [],
            'companion'           => true,
            '_idempotent_replay'  => true,
        ];
    }

    /**
     * Write a raw upload body to a temp path using WP_Filesystem.
     *
     * Plugin Check flags direct file_put_contents(). WP_Filesystem's
     * put_contents() provides the wp.org-approved wrapper and normalises
     * permissions via FS_CHMOD_FILE. The temp path is expected to be the
     * result of wp_tempnam(), which is already in WP's upload directory.
     *
     * Returns the byte count on success, false on failure.
     *
     * @param string $tmp  Absolute path created by wp_tempnam().
     * @param string $body Raw request body bytes.
     * @return int|false
     */
    private function write_temp_body( $tmp, $body ) {
        global $wp_filesystem;
        if ( empty( $wp_filesystem ) ) {
            require_once ABSPATH . 'wp-admin/includes/file.php';
            WP_Filesystem();
        }
        if ( empty( $wp_filesystem ) || ! is_object( $wp_filesystem ) ) {
            return false;
        }
        $ok = $wp_filesystem->put_contents( $tmp, $body, FS_CHMOD_FILE );
        if ( ! $ok ) {
            return false;
        }
        return strlen( $body );
    }

    /**
     * Extract filename from a Content-Disposition header.
     *
     * Supports:
     *   - filename="photo.jpg"
     *   - filename=photo.jpg
     *   - filename*=UTF-8''%D8%B9%DA%A9%D8%B3.jpg  (RFC 5987)
     *
     * Returns null if no filename can be extracted.
     */
    private function parse_content_disposition_filename($disposition) {
        if (empty($disposition)) {
            return null;
        }
        // RFC 5987: filename*=charset''percent-encoded
        if (preg_match("/filename\\*\\s*=\\s*(?:UTF-8'')?([^;]+)/i", $disposition, $m)) {
            $val = trim($m[1], " \t\"'");
            $decoded = rawurldecode($val);
            if (!empty($decoded)) {
                return $decoded;
            }
        }
        // filename=... or filename="..."
        if (preg_match('/filename\\s*=\\s*"([^"]+)"/i', $disposition, $m)) {
            return $m[1];
        }
        if (preg_match('/filename\\s*=\\s*([^;]+)/i', $disposition, $m)) {
            return trim($m[1], " \t\"'");
        }
        return null;
    }

    /**
     * Best-effort MIME → extension mapping used only when Content-Disposition
     * is missing so we can still pick a non-ambiguous filename.
     */
    private function mime_to_ext($mime) {
        $map = [
            'image/png'       => 'png',
            'image/jpeg'      => 'jpg',
            'image/gif'       => 'gif',
            'image/webp'      => 'webp',
            'image/svg+xml'   => 'svg',
            'application/pdf' => 'pdf',
            'video/mp4'       => 'mp4',
            'audio/mpeg'      => 'mp3',
        ];
        return isset($map[$mime]) ? $map[$mime] : 'bin';
    }

    /**
     * Build a JSON shape matching /wp/v2/media so existing MCPHub parsers
     * continue to work unchanged.
     */
    private function format_attachment_response($attach_id, $sideload, $metadata) {
        $post = get_post($attach_id);
        $source_url = wp_get_attachment_url($attach_id);
        $title = $post ? $post->post_title : '';

        return [
            'id'            => (int) $attach_id,
            'date'          => $post ? mysql_to_rfc3339($post->post_date) : null,
            'slug'          => $post ? $post->post_name : '',
            'type'          => 'attachment',
            'link'          => get_permalink($attach_id),
            'title'         => ['rendered' => $title],
            'author'        => $post ? (int) $post->post_author : 0,
            'mime_type'     => $sideload['type'],
            'media_type'    => $this->mime_to_media_type($sideload['type']),
            'source_url'    => $source_url,
            'media_details' => is_array($metadata) ? $metadata : [],
            'companion'     => true,
        ];
    }

    private function mime_to_media_type($mime) {
        if (strpos($mime, 'image/') === 0) return 'image';
        if (strpos($mime, 'video/') === 0) return 'video';
        if (strpos($mime, 'audio/') === 0) return 'audio';
        return 'file';
    }

    // ------------------------------------------------------------------
    //  F.18.1 — Capability probe (airano-mcp/v1/capabilities)
    // ------------------------------------------------------------------

    /**
     * GET /airano-mcp/v1/capabilities
     *
     * Reports the effective capability set of the currently-authenticated
     * user (i.e. the owner of the application password MCPHub is using) so
     * MCPHub's F.7e probe can decide which tool families to expose.
     *
     * Response shape:
     *   {
     *     "plugin_version": "2.1.0",
     *     "companion": true,
     *     "user": {
     *        "id": int,
     *        "login": "string",
     *        "roles": ["administrator"],
     *        "capabilities": { "upload_files": true, "edit_posts": true, ... }
     *     },
     *     "features": { "rank_math": bool, "yoast": bool, "woocommerce": bool, "multisite": bool },
     *     "routes": { "capabilities": true, "upload_limits": true, ... },
     *     "wordpress": { "version": "6.5.3", "php_version": "8.1.x", "rest_enabled": true }
     *   }
     */
    public function get_capabilities() {
        $user = wp_get_current_user();
        if (!$user || !$user->ID) {
            return new WP_Error(
                'not_authenticated',
                __( 'No authenticated user found for capability probe.', 'airano-mcp-bridge' ),
                ['status' => 401]
            );
        }

        // Report the explicit capability set MCPHub cares about. We do NOT
        // return the entire $user->allcaps map: we curate a stable shape so
        // the Python side can type-check it cleanly.
        $caps = [
            'upload_files'      => user_can($user, 'upload_files'),
            'edit_posts'        => user_can($user, 'edit_posts'),
            'publish_posts'     => user_can($user, 'publish_posts'),
            'edit_others_posts' => user_can($user, 'edit_others_posts'),
            'delete_posts'      => user_can($user, 'delete_posts'),
            'edit_pages'        => user_can($user, 'edit_pages'),
            'publish_pages'     => user_can($user, 'publish_pages'),
            'manage_categories' => user_can($user, 'manage_categories'),
            'moderate_comments' => user_can($user, 'moderate_comments'),
            'manage_options'    => user_can($user, 'manage_options'),
            'edit_users'        => user_can($user, 'edit_users'),
            'list_users'        => user_can($user, 'list_users'),
            'manage_woocommerce'=> user_can($user, 'manage_woocommerce'),
            'edit_shop_orders'  => user_can($user, 'edit_shop_orders'),
            'edit_products'     => user_can($user, 'edit_products'),
        ];

        $features = [
            'rank_math'    => $this->is_rank_math_active(),
            'yoast'        => $this->is_yoast_active(),
            'woocommerce' => $this->is_woocommerce_active(),
            'multisite'   => is_multisite(),
        ];

        // F.X.fix #10: read from the single-source route map so
        // capabilities and site_health can never drift again.
        $routes = self::get_route_map();

        $wp_env = [
            'version'      => get_bloginfo('version'),
            'php_version'  => PHP_VERSION,
            'rest_enabled' => true,
        ];

        $response = [
            'plugin_version' => self::VERSION,
            'companion'      => true,
            'user' => [
                'id'           => (int) $user->ID,
                'login'        => $user->user_login,
                'roles'        => array_values((array) $user->roles),
                'capabilities' => $caps,
            ],
            'features' => $features,
            'routes'   => $routes,
            'wordpress'=> $wp_env,
        ];

        return rest_ensure_response($response);
    }

    // ------------------------------------------------------------------
    //  F.18.2 — Bulk meta writes (airano-mcp/v1/bulk-meta)
    // ------------------------------------------------------------------

    /**
     * Maximum number of {post_id, meta} items accepted in a single request.
     * Protects the site from accidental DoS through runaway batches.
     */
    const BULK_META_MAX_ITEMS = 500;

    /**
     * POST /airano-mcp/v1/bulk-meta
     *
     * Body shape:
     *   { "updates": [ { "post_id": 123, "meta": { "key": "value", ... } }, ... ] }
     *
     * Per item:
     *  - Skipped if post doesn't exist (status=not_found)
     *  - Skipped if current user cannot edit it (status=forbidden)
     *  - Otherwise each meta key is written via update_post_meta().
     *  - Values of null delete the meta key (delete_post_meta).
     *
     * Response:
     *   {
     *     "total": N, "updated": U, "failed": F, "skipped": S,
     *     "results": [ { "post_id": int, "status": "ok|forbidden|not_found|error",
     *                    "updated_keys": [...], "error": "..." }, ... ]
     *   }
     */
    public function handle_bulk_meta($request) {
        $params = $request->get_json_params();
        if (!is_array($params)) {
            return new WP_Error(
                'invalid_body',
                __( 'Expected JSON body with `updates` array.', 'airano-mcp-bridge' ),
                ['status' => 400]
            );
        }

        // Accept either {"updates": [...]} or a bare top-level array for
        // convenience when calling from the CLI.
        $updates = isset($params['updates']) ? $params['updates'] : $params;
        if (!is_array($updates) || empty($updates)) {
            return new WP_Error(
                'invalid_updates',
                __( 'No updates supplied. Send `{"updates": [{"post_id": N, "meta": {...}}, ...]}`.', 'airano-mcp-bridge' ),
                ['status' => 400]
            );
        }

        if (count($updates) > self::BULK_META_MAX_ITEMS) {
            return new WP_Error(
                'too_many_items',
                /* translators: %d: maximum items per bulk-meta request. */
                sprintf( __( 'bulk-meta supports at most %d items per request.', 'airano-mcp-bridge' ), self::BULK_META_MAX_ITEMS ),
                ['status' => 413]
            );
        }

        $results = [];
        $updated_count = 0;
        $failed_count = 0;
        $skipped_count = 0;

        foreach ($updates as $idx => $item) {
            if (!is_array($item)) {
                $results[] = [
                    'index' => $idx,
                    'post_id' => null,
                    'status' => 'error',
                    'error' => 'invalid_item',
                    'message' => __( 'Each update must be an object with post_id + meta.', 'airano-mcp-bridge' ),
                ];
                $failed_count++;
                continue;
            }

            $post_id = isset($item['post_id']) ? (int) $item['post_id'] : 0;
            $meta    = isset($item['meta']) && is_array($item['meta']) ? $item['meta'] : null;

            if ($post_id <= 0 || $meta === null) {
                $results[] = [
                    'index' => $idx,
                    'post_id' => $post_id ?: null,
                    'status' => 'error',
                    'error' => 'invalid_item',
                    'message' => __( 'Each item needs a positive post_id and a meta object.', 'airano-mcp-bridge' ),
                ];
                $failed_count++;
                continue;
            }

            $post = get_post($post_id);
            if (!$post) {
                $results[] = [
                    'index' => $idx,
                    'post_id' => $post_id,
                    'status' => 'not_found',
                    'error' => 'post_not_found',
                ];
                $skipped_count++;
                continue;
            }

            if (!current_user_can('edit_post', $post_id)) {
                $results[] = [
                    'index' => $idx,
                    'post_id' => $post_id,
                    'status' => 'forbidden',
                    'error' => 'cannot_edit_post',
                ];
                $skipped_count++;
                continue;
            }

            $updated_keys = [];
            $deleted_keys = [];
            $item_error = null;

            foreach ($meta as $meta_key => $meta_value) {
                if (!is_string($meta_key) || $meta_key === '') {
                    $item_error = 'invalid_meta_key';
                    break;
                }
                // Block `_` (private) keys unless the user can edit others'
                // posts — matches WP's own guardrail for register_post_meta
                // with non-exposed keys. Application passwords typically
                // belong to admins so this is rarely limiting in practice.
                if (strpos($meta_key, '_') === 0 && !current_user_can('edit_others_posts')) {
                    $item_error = 'private_meta_key_denied';
                    break;
                }

                if ($meta_value === null) {
                    delete_post_meta($post_id, $meta_key);
                    $deleted_keys[] = $meta_key;
                } else {
                    update_post_meta($post_id, $meta_key, $meta_value);
                    $updated_keys[] = $meta_key;
                }
            }

            if ($item_error !== null) {
                $results[] = [
                    'index' => $idx,
                    'post_id' => $post_id,
                    'status' => 'error',
                    'error' => $item_error,
                    'updated_keys' => $updated_keys,
                    'deleted_keys' => $deleted_keys,
                ];
                $failed_count++;
                continue;
            }

            $results[] = [
                'index' => $idx,
                'post_id' => $post_id,
                'status' => 'ok',
                'updated_keys' => $updated_keys,
                'deleted_keys' => $deleted_keys,
            ];
            $updated_count++;
        }

        return rest_ensure_response([
            'total'   => count($updates),
            'updated' => $updated_count,
            'failed'  => $failed_count,
            'skipped' => $skipped_count,
            'results' => $results,
        ]);
    }

    // ------------------------------------------------------------------
    //  F.18.3 — Structured JSON export (airano-mcp/v1/export)
    // ------------------------------------------------------------------

    /**
     * Maximum number of posts returned in a single export page. Larger
     * datasets must be paginated via offset.
     */
    const EXPORT_MAX_LIMIT = 500;
    const EXPORT_DEFAULT_LIMIT = 100;

    /**
     * GET /airano-mcp/v1/export
     *
     * Query params:
     *   post_type       — comma-list, default "post" ("post,page,product,...")
     *   status          — comma-list or "any", default "publish"
     *   since           — ISO8601 date; only posts modified after this
     *   limit           — 1..500, default 100
     *   offset          — default 0
     *   include_media   — bool, default true
     *   include_terms   — bool, default true
     *   include_meta    — bool, default true
     *
     * Response is a single JSON envelope (no chunking) so chunking/paging
     * is the caller's responsibility via `offset` + `has_more` + `next_offset`.
     */
    public function handle_export($request) {
        $post_types_raw = (string) ($request->get_param('post_type') ?: 'post');
        $status_raw     = (string) ($request->get_param('status') ?: 'publish');
        $since          = $request->get_param('since');
        $limit          = (int) ($request->get_param('limit') ?: self::EXPORT_DEFAULT_LIMIT);
        $offset         = (int) ($request->get_param('offset') ?: 0);

        $include_media  = $this->bool_param($request->get_param('include_media'), true);
        $include_terms  = $this->bool_param($request->get_param('include_terms'), true);
        $include_meta   = $this->bool_param($request->get_param('include_meta'), true);

        // Normalise the input.
        $post_types = array_values(array_filter(array_map('trim', explode(',', $post_types_raw))));
        if (empty($post_types)) {
            $post_types = ['post'];
        }
        $statuses = array_values(array_filter(array_map('trim', explode(',', $status_raw))));
        if (empty($statuses)) {
            $statuses = ['publish'];
        }
        if (in_array('any', $statuses, true)) {
            $statuses = 'any';
        }

        if ($limit <= 0) {
            $limit = self::EXPORT_DEFAULT_LIMIT;
        }
        if ($limit > self::EXPORT_MAX_LIMIT) {
            $limit = self::EXPORT_MAX_LIMIT;
        }
        if ($offset < 0) {
            $offset = 0;
        }

        // Validate each requested post_type is real + readable.
        foreach ($post_types as $pt) {
            if (!post_type_exists($pt)) {
                return new WP_Error(
                    'unknown_post_type',
                    /* translators: %s: post type slug supplied by caller. */
                    sprintf( __( 'Unknown post type: %s', 'airano-mcp-bridge' ), $pt ),
                    ['status' => 400]
                );
            }
        }

        $query_args = [
            'post_type'      => $post_types,
            'post_status'    => $statuses,
            'posts_per_page' => $limit,
            'offset'         => $offset,
            'orderby'        => 'modified',
            'order'          => 'DESC',
            'no_found_rows'  => false,
            'suppress_filters' => false,
        ];

        // Validate and translate `since` to a date_query.
        if ($since) {
            $ts = strtotime((string) $since);
            if (!$ts) {
                return new WP_Error(
                    'invalid_since',
                    __( '`since` must be a parseable ISO8601 / strtotime date.', 'airano-mcp-bridge' ),
                    ['status' => 400]
                );
            }
            $query_args['date_query'] = [
                [
                    'column' => 'post_modified_gmt',
                    'after'  => gmdate('Y-m-d H:i:s', $ts),
                    'inclusive' => false,
                ],
            ];
        }

        $q = new WP_Query($query_args);
        $posts = [];
        $media_ids = [];

        foreach ($q->posts as $post) {
            $item = [
                'id'              => (int) $post->ID,
                'post_type'       => $post->post_type,
                'status'          => $post->post_status,
                'title'           => $post->post_title,
                'slug'            => $post->post_name,
                'content'         => $post->post_content,
                'excerpt'         => $post->post_excerpt,
                'date_gmt'        => mysql_to_rfc3339($post->post_date_gmt),
                'modified_gmt'    => mysql_to_rfc3339($post->post_modified_gmt),
                'author_id'       => (int) $post->post_author,
                'parent_id'       => (int) $post->post_parent,
                'menu_order'      => (int) $post->menu_order,
                'link'            => get_permalink($post),
            ];

            $featured = (int) get_post_thumbnail_id($post->ID);
            $item['featured_media_id'] = $featured ?: null;
            if ($featured) {
                $media_ids[$featured] = true;
            }

            if ($include_meta) {
                // get_post_meta with no key returns all meta — keys are arrays
                // because meta is multi-value; we flatten single-value keys for
                // ergonomics but preserve arrays when > 1.
                $raw_meta = get_post_meta($post->ID);
                $flat = [];
                if (is_array($raw_meta)) {
                    foreach ($raw_meta as $mk => $mv) {
                        if (is_array($mv) && count($mv) === 1) {
                            $flat[$mk] = maybe_unserialize($mv[0]);
                        } else {
                            $flat[$mk] = array_map('maybe_unserialize', (array) $mv);
                        }
                    }
                }
                $item['meta'] = $flat;
            }

            if ($include_terms) {
                $taxonomies = get_object_taxonomies($post->post_type, 'objects');
                $terms_out = [];
                foreach ($taxonomies as $tx_name => $tx_obj) {
                    if (!$tx_obj->show_in_rest && !$tx_obj->public) {
                        continue;
                    }
                    $terms = wp_get_post_terms($post->ID, $tx_name, ['fields' => 'all']);
                    if (is_wp_error($terms) || empty($terms)) {
                        continue;
                    }
                    $terms_out[$tx_name] = array_map(function ($t) {
                        return [
                            'id'   => (int) $t->term_id,
                            'name' => $t->name,
                            'slug' => $t->slug,
                        ];
                    }, $terms);
                }
                $item['terms'] = $terms_out;
            }

            $posts[] = $item;
        }

        $media = [];
        if ($include_media && !empty($media_ids)) {
            $ids = array_keys($media_ids);
            // Fetch media in a single WP_Query for efficiency.
            $mq = new WP_Query([
                'post_type'      => 'attachment',
                'post_status'    => 'inherit',
                'post__in'       => $ids,
                'posts_per_page' => count($ids),
                'no_found_rows'  => true,
            ]);
            foreach ($mq->posts as $m) {
                $media[] = [
                    'id'            => (int) $m->ID,
                    'source_url'    => wp_get_attachment_url($m->ID),
                    'mime_type'     => $m->post_mime_type,
                    'alt_text'      => (string) get_post_meta($m->ID, '_wp_attachment_image_alt', true),
                    'title'         => $m->post_title,
                ];
            }
        }

        $total = (int) $q->found_posts;
        $returned = count($posts);
        $has_more = ($offset + $returned) < $total;

        return rest_ensure_response([
            'post_types'      => $post_types,
            'status'          => is_array($statuses) ? $statuses : ['any'],
            'since'           => $since ?: null,
            'limit'           => $limit,
            'offset'          => $offset,
            'returned'        => $returned,
            'total_matching'  => $total,
            'has_more'        => $has_more,
            'next_offset'     => $has_more ? $offset + $returned : null,
            'include_media'   => $include_media,
            'include_terms'   => $include_terms,
            'include_meta'    => $include_meta,
            'posts'           => $posts,
            'media'           => $media,
            'exported_at_gmt' => gmdate('Y-m-d\TH:i:s\Z'),
            'plugin_version'  => self::VERSION,
        ]);
    }

    /**
     * Coerce a REST query param into a bool.
     * Accepts true/false/"true"/"false"/"1"/"0"/1/0; anything else → $default.
     */
    private function bool_param($v, $default) {
        if ($v === null || $v === '') {
            return (bool) $default;
        }
        if (is_bool($v)) {
            return $v;
        }
        if (is_numeric($v)) {
            return (int) $v !== 0;
        }
        $s = strtolower((string) $v);
        if (in_array($s, ['true', 'yes', 'on'], true)) {
            return true;
        }
        if (in_array($s, ['false', 'no', 'off'], true)) {
            return false;
        }
        return (bool) $default;
    }

    // ------------------------------------------------------------------
    //  F.18.4 — Cache purge (airano-mcp/v1/cache-purge)
    // ------------------------------------------------------------------

    /**
     * POST /airano-mcp/v1/cache-purge
     *
     * Auto-detects active cache plugins and invokes their "purge all"
     * API. Always flushes the WP object cache (safe no-op when no
     * persistent object cache is configured). Makes the Docker-socket +
     * WP-CLI fallback unnecessary for cache maintenance on platforms
     * that don't allow the socket mount.
     *
     * Response shape:
     *   {
     *     "detected":  ["wp_rocket", "litespeed"],
     *     "purged":    ["wp_rocket_all", "litespeed_all", "object_cache"],
     *     "skipped":   [],
     *     "errors":    [],
     *     "plugin_version": "2.4.0"
     *   }
     */
    public function handle_cache_purge($request) {
        $detected = [];
        $purged   = [];
        $errors   = [];

        // --- WP Rocket ---
        if (function_exists('rocket_clean_domain')) {
            $detected[] = 'wp_rocket';
            try {
                rocket_clean_domain();
                if (function_exists('rocket_clean_minify')) {
                    rocket_clean_minify();
                }
                $purged[] = 'wp_rocket_all';
            } catch (\Throwable $e) {
                $errors[] = ['plugin' => 'wp_rocket', 'message' => $e->getMessage()];
            }
        }

        // --- W3 Total Cache ---
        if (function_exists('w3tc_flush_all')) {
            $detected[] = 'w3_total_cache';
            try {
                w3tc_flush_all();
                $purged[] = 'w3_total_cache_all';
            } catch (\Throwable $e) {
                $errors[] = ['plugin' => 'w3_total_cache', 'message' => $e->getMessage()];
            }
        }

        // --- WP Super Cache ---
        if (function_exists('wp_cache_clear_cache')) {
            $detected[] = 'wp_super_cache';
            try {
                wp_cache_clear_cache();
                $purged[] = 'wp_super_cache_all';
            } catch (\Throwable $e) {
                $errors[] = ['plugin' => 'wp_super_cache', 'message' => $e->getMessage()];
            }
        }

        // --- LiteSpeed Cache ---
        if (defined('LSCWP_V') || class_exists('\\LiteSpeed\\Purge')) {
            $detected[] = 'litespeed';
            try {
                // phpcs:ignore WordPress.NamingConventions.PrefixAllGlobals.NonPrefixedHooknameFound -- third-party hook
                do_action('litespeed_purge_all');
                $purged[] = 'litespeed_all';
            } catch (\Throwable $e) {
                $errors[] = ['plugin' => 'litespeed', 'message' => $e->getMessage()];
            }
        }

        // --- WP Fastest Cache ---
        if (class_exists('WpFastestCache')) {
            $detected[] = 'wp_fastest_cache';
            try {
                $wpfc = new \WpFastestCache();
                if (method_exists($wpfc, 'deleteCache')) {
                    $wpfc->deleteCache(true);
                    $purged[] = 'wp_fastest_cache_all';
                } else {
                    // phpcs:ignore WordPress.NamingConventions.PrefixAllGlobals.NonPrefixedHooknameFound -- third-party hook
                    do_action('wpfc_clear_all_cache', true);
                    $purged[] = 'wp_fastest_cache_all';
                }
            } catch (\Throwable $e) {
                $errors[] = ['plugin' => 'wp_fastest_cache', 'message' => $e->getMessage()];
            }
        }

        // --- SiteGround Optimizer ---
        if (
            function_exists('sg_cachepress_purge_cache')
            || class_exists('SiteGround_Optimizer\\Supercacher\\Supercacher')
        ) {
            $detected[] = 'siteground_optimizer';
            try {
                if (function_exists('sg_cachepress_purge_cache')) {
                    sg_cachepress_purge_cache();
                } elseif (method_exists('SiteGround_Optimizer\\Supercacher\\Supercacher', 'purge_cache')) {
                    \SiteGround_Optimizer\Supercacher\Supercacher::purge_cache();
                }
                $purged[] = 'siteground_optimizer_all';
            } catch (\Throwable $e) {
                $errors[] = ['plugin' => 'siteground_optimizer', 'message' => $e->getMessage()];
            }
        }

        // --- Cloudflare (WP) ---
        // CF has no canonical "purge all" helper exposed publicly; skip unless
        // we detect the official plugin and even then we only advertise
        // detection so the user can act.
        if (class_exists('CF\\WordPress\\Hooks')) {
            $detected[] = 'cloudflare';
            // no-op — CF's purge requires the user's API token we don't have.
        }

        // --- Object cache (always) ---
        // Safe no-op if no persistent object cache is configured.
        if (function_exists('wp_cache_flush')) {
            try {
                wp_cache_flush();
                $purged[] = 'object_cache';
            } catch (\Throwable $e) {
                $errors[] = ['plugin' => 'object_cache', 'message' => $e->getMessage()];
            }
        }

        return rest_ensure_response([
            'detected'       => array_values(array_unique($detected)),
            'purged'         => array_values(array_unique($purged)),
            'skipped'        => [],
            'errors'         => $errors,
            'ok'             => empty($errors),
            'plugin_version' => self::VERSION,
        ]);
    }

    // ------------------------------------------------------------------
    //  F.18.5 — Transient flush (airano-mcp/v1/transient-flush)
    // ------------------------------------------------------------------

    /**
     * Cap on the number of deleted-key samples returned so the response
     * stays small even when thousands of transients are purged.
     */
    const TRANSIENT_SAMPLE_MAX = 100;

    /**
     * POST /airano-mcp/v1/transient-flush
     *
     * Body (optional):
     *   {
     *     "scope":   "expired" | "all" | "pattern",   // default "expired"
     *     "pattern": "foo_*",                           // required when scope=pattern
     *     "include_site_transients": true               // default true
     *   }
     *
     * Response:
     *   {
     *     "ok": bool, "scope": ..., "pattern": ..., "include_site_transients": ...,
     *     "deleted_count": N,
     *     "deleted_sample": [...],       // capped at TRANSIENT_SAMPLE_MAX
     *     "plugin_version": "2.5.0"
     *   }
     */
    public function handle_transient_flush($request) {
        global $wpdb;

        $params = $request->get_json_params();
        if (!is_array($params)) {
            $params = [];
        }

        $scope   = isset($params['scope']) ? strtolower((string) $params['scope']) : 'expired';
        $pattern = isset($params['pattern']) ? (string) $params['pattern'] : '';
        $include_site = array_key_exists('include_site_transients', $params)
            ? $this->bool_param($params['include_site_transients'], true)
            : true;

        if (!in_array($scope, ['expired', 'all', 'pattern'], true)) {
            return new WP_Error(
                'invalid_scope',
                __( '`scope` must be one of: "expired", "all", "pattern".', 'airano-mcp-bridge' ),
                ['status' => 400]
            );
        }
        if ($scope === 'pattern' && $pattern === '') {
            return new WP_Error(
                'pattern_required',
                __( '`pattern` is required when scope="pattern" (e.g. "rank_math_*").', 'airano-mcp-bridge' ),
                ['status' => 400]
            );
        }

        $deleted_keys = [];

        if ($scope === 'expired') {
            // Count the timeout rows that will be considered expired by
            // delete_expired_transients() (option_value < UNIX_TIMESTAMP())
            // so we can report a stable count.
            $now = time();
            // phpcs:ignore WordPress.DB.DirectDatabaseQuery.DirectQuery, WordPress.DB.DirectDatabaseQuery.NoCaching -- transient inventory has no WP API; cache flush follows below
            $rows = $wpdb->get_col($wpdb->prepare(
                "SELECT option_name FROM {$wpdb->options}
                 WHERE option_name LIKE %s AND option_value < %d",
                $wpdb->esc_like('_transient_timeout_') . '%',
                $now
            ));
            foreach ($rows as $row) {
                $deleted_keys[] = preg_replace('/^_transient_timeout_/', '', $row);
            }

            if (function_exists('delete_expired_transients')) {
                delete_expired_transients($include_site);
            }
        } elseif ($scope === 'all') {
            // phpcs:ignore WordPress.DB.DirectDatabaseQuery.DirectQuery, WordPress.DB.DirectDatabaseQuery.NoCaching -- transient inventory has no WP API; cache flush follows below
            $option_names = $wpdb->get_col($wpdb->prepare(
                "SELECT option_name FROM {$wpdb->options}
                 WHERE option_name LIKE %s AND option_name NOT LIKE %s",
                $wpdb->esc_like('_transient_') . '%',
                $wpdb->esc_like('_transient_timeout_') . '%'
            ));
            foreach ($option_names as $name) {
                $key = preg_replace('/^_transient_/', '', $name);
                if (delete_transient($key)) {
                    $deleted_keys[] = $key;
                }
            }

            if ($include_site && is_multisite()) {
                // phpcs:ignore WordPress.DB.DirectDatabaseQuery.DirectQuery, WordPress.DB.DirectDatabaseQuery.NoCaching -- site-transient inventory has no WP API
                $site_names = $wpdb->get_col($wpdb->prepare(
                    "SELECT meta_key FROM {$wpdb->sitemeta}
                     WHERE meta_key LIKE %s AND meta_key NOT LIKE %s",
                    $wpdb->esc_like('_site_transient_') . '%',
                    $wpdb->esc_like('_site_transient_timeout_') . '%'
                ));
                foreach ($site_names as $name) {
                    $key = preg_replace('/^_site_transient_/', '', $name);
                    if (delete_site_transient($key)) {
                        $deleted_keys[] = 'site:' . $key;
                    }
                }
            }
        } else {
            // pattern: convert shell-style * glob to SQL LIKE %.
            $like = $wpdb->esc_like('_transient_') . str_replace('*', '%', $pattern);
            // phpcs:ignore WordPress.DB.DirectDatabaseQuery.DirectQuery, WordPress.DB.DirectDatabaseQuery.NoCaching -- pattern-match transient inventory has no WP API
            $option_names = $wpdb->get_col($wpdb->prepare(
                "SELECT option_name FROM {$wpdb->options}
                 WHERE option_name LIKE %s AND option_name NOT LIKE %s",
                $like,
                $wpdb->esc_like('_transient_timeout_') . '%'
            ));
            foreach ($option_names as $name) {
                $key = preg_replace('/^_transient_/', '', $name);
                if (delete_transient($key)) {
                    $deleted_keys[] = $key;
                }
            }

            if ($include_site && is_multisite()) {
                $site_like = $wpdb->esc_like('_site_transient_') . str_replace('*', '%', $pattern);
                // phpcs:ignore WordPress.DB.DirectDatabaseQuery.DirectQuery, WordPress.DB.DirectDatabaseQuery.NoCaching -- site-transient pattern inventory has no WP API
                $site_names = $wpdb->get_col($wpdb->prepare(
                    "SELECT meta_key FROM {$wpdb->sitemeta}
                     WHERE meta_key LIKE %s AND meta_key NOT LIKE %s",
                    $site_like,
                    $wpdb->esc_like('_site_transient_timeout_') . '%'
                ));
                foreach ($site_names as $name) {
                    $key = preg_replace('/^_site_transient_/', '', $name);
                    if (delete_site_transient($key)) {
                        $deleted_keys[] = 'site:' . $key;
                    }
                }
            }
        }

        wp_cache_flush();

        return rest_ensure_response([
            'ok'                      => true,
            'scope'                   => $scope,
            'pattern'                 => $scope === 'pattern' ? $pattern : null,
            'include_site_transients' => $include_site,
            'deleted_count'           => count($deleted_keys),
            'deleted_sample'          => array_slice($deleted_keys, 0, self::TRANSIENT_SAMPLE_MAX),
            'plugin_version'          => self::VERSION,
        ]);
    }

    // ------------------------------------------------------------------
    //  F.18.6 — Unified site health (airano-mcp/v1/site-health)
    // ------------------------------------------------------------------

    /**
     * GET /airano-mcp/v1/site-health
     *
     * Single JSON envelope with everything MCPHub needs to render a
     * "is this site healthy" dashboard. Collects in one request what
     * otherwise requires 5+ round-trips and/or WP-CLI.
     */
    public function handle_site_health() {
        global $wp_version, $wpdb;

        // --- WordPress environment ----------------------------------------
        $wp_env = [
            'version'                        => $wp_version,
            'multisite'                      => is_multisite(),
            'home_url'                       => home_url(),
            'site_url'                       => site_url(),
            'language'                       => get_locale(),
            'timezone'                       => wp_timezone_string(),
            'rest_enabled'                   => true,
            'application_passwords_available'=> function_exists('wp_is_application_passwords_available')
                ? (bool) wp_is_application_passwords_available()
                : true,
            'debug_mode'                     => defined('WP_DEBUG') && WP_DEBUG,
            'script_debug'                   => defined('SCRIPT_DEBUG') && SCRIPT_DEBUG,
            'savequeries'                    => defined('SAVEQUERIES') && SAVEQUERIES,
            'https_home'                     => strpos(home_url(), 'https://') === 0,
        ];

        // --- PHP ---------------------------------------------------------
        $extensions = get_loaded_extensions();
        sort($extensions);
        $php_env = [
            'version'             => PHP_VERSION,
            'memory_limit'        => (string) ini_get('memory_limit'),
            'max_execution_time'  => (string) ini_get('max_execution_time'),
            'upload_max_filesize' => (string) ini_get('upload_max_filesize'),
            'post_max_size'       => (string) ini_get('post_max_size'),
            'max_input_vars'      => (int) ini_get('max_input_vars'),
            'extensions'          => array_values($extensions),
            'has_mbstring'        => extension_loaded('mbstring'),
            'has_curl'            => extension_loaded('curl'),
            'has_gd'              => extension_loaded('gd'),
            'has_imagick'         => extension_loaded('imagick'),
            'has_intl'            => extension_loaded('intl'),
        ];

        // --- Server ------------------------------------------------------
        $server_software = '';
        if ( isset( $_SERVER['SERVER_SOFTWARE'] ) ) {
            // phpcs:ignore WordPress.Security.ValidatedSanitizedInput.InputNotSanitized -- sanitised on the next line
            $raw_software    = wp_unslash( $_SERVER['SERVER_SOFTWARE'] );
            $server_software = sanitize_text_field( $raw_software );
        }

        $disk_free  = @disk_free_space(ABSPATH);
        $disk_total = @disk_total_space(ABSPATH);
        $server_env = [
            'software'         => $server_software,
            'disk_free_bytes'  => $disk_free !== false ? (int) $disk_free : null,
            'disk_total_bytes' => $disk_total !== false ? (int) $disk_total : null,
        ];

        // --- MySQL / MariaDB --------------------------------------------
        $db_version = '';
        if (is_object($wpdb) && method_exists($wpdb, 'db_version')) {
            $db_version = (string) $wpdb->db_version();
        }
        $db_env = [
            'version'     => $db_version,
            'server_info' => is_object($wpdb) && isset($wpdb->dbh) && is_object($wpdb->dbh)
                && method_exists($wpdb->dbh, 'get_server_info')
                ? $wpdb->dbh->get_server_info()
                : null,
            'charset'     => (string) $wpdb->charset,
            'collate'     => (string) $wpdb->collate,
            'prefix'      => (string) $wpdb->prefix,
        ];

        // --- Plugins -----------------------------------------------------
        if (!function_exists('get_plugins')) {
            require_once ABSPATH . 'wp-admin/includes/plugin.php';
        }
        $all_plugins = get_plugins();
        $active_paths = (array) get_option('active_plugins', []);
        $active_list = [];
        foreach ($active_paths as $path) {
            if (isset($all_plugins[$path])) {
                $meta = $all_plugins[$path];
                $active_list[] = [
                    'file'    => $path,
                    'name'    => $meta['Name'] ?? '',
                    'version' => $meta['Version'] ?? '',
                ];
            }
        }
        // MU plugins
        $mu_plugins = function_exists('get_mu_plugins') ? get_mu_plugins() : [];

        $plugins_env = [
            'total_count'    => count($all_plugins),
            'active_count'   => count($active_list),
            'active'         => $active_list,
            'must_use_count' => count($mu_plugins),
        ];

        // --- Theme -------------------------------------------------------
        $active_theme = wp_get_theme();
        $parent_theme = $active_theme->parent();
        $theme_env = [
            'active' => [
                'name'    => $active_theme ? $active_theme->get('Name') : null,
                'version' => $active_theme ? $active_theme->get('Version') : null,
                'stylesheet' => $active_theme ? $active_theme->get_stylesheet() : null,
            ],
            'parent' => $parent_theme
                ? [
                    'name'    => $parent_theme->get('Name'),
                    'version' => $parent_theme->get('Version'),
                    'stylesheet' => $parent_theme->get_stylesheet(),
                  ]
                : null,
            'total_count' => count(wp_get_themes()),
        ];

        // --- Write/permission checks ------------------------------------
        global $wp_filesystem;
        if ( empty( $wp_filesystem ) ) {
            require_once ABSPATH . 'wp-admin/includes/file.php';
            WP_Filesystem();
        }
        $uploads = wp_get_upload_dir();
        $checks = [
            'writable_wp_content' => ! empty( $wp_filesystem )
                ? $wp_filesystem->is_writable( WP_CONTENT_DIR )
                : null,
            'writable_uploads'    => is_array($uploads) && !empty($uploads['basedir']) && ! empty( $wp_filesystem )
                ? $wp_filesystem->is_writable( $uploads['basedir'] )
                : null,
            'ssl_enabled'         => function_exists('is_ssl') ? is_ssl() : null,
        ];

        // --- Companion self-description ---------------------------------
        // F.X.fix #10: read from the shared route map — capabilities
        // and site_health must agree on what's shipping.
        $companion = [
            'plugin_version' => self::VERSION,
            'routes'         => self::get_route_map(),
            'features' => [
                'rank_math'   => $this->is_rank_math_active(),
                'yoast'       => $this->is_yoast_active(),
                'woocommerce' => $this->is_woocommerce_active(),
            ],
        ];

        return rest_ensure_response([
            'ok'              => true,
            'wordpress'       => $wp_env,
            'php'             => $php_env,
            'server'          => $server_env,
            'database'        => $db_env,
            'plugins'         => $plugins_env,
            'theme'           => $theme_env,
            'checks'          => $checks,
            'companion'       => $companion,
            'generated_at_gmt'=> gmdate('Y-m-d\TH:i:s\Z'),
            'plugin_version'  => self::VERSION,
        ]);
    }

    // ------------------------------------------------------------------
    //  F.18.7 — Audit hook (airano-mcp/v1/audit-hook)
    // ------------------------------------------------------------------

    /**
     * GET /airano-mcp/v1/audit-hook — current config + stats.
     * Secret is returned masked; never echoed in full.
     */
    public function handle_audit_hook_get() {
        $secret = (string) get_option(self::AUDIT_OPT_SECRET, '');
        $secret_last4 = strlen($secret) >= 4 ? substr($secret, -4) : '';
        $events = get_option(self::AUDIT_OPT_EVENTS, self::AUDIT_DEFAULT_EVENTS);
        if (!is_array($events)) {
            $events = self::AUDIT_DEFAULT_EVENTS;
        }
        return rest_ensure_response([
            'enabled'        => (bool) get_option(self::AUDIT_OPT_ENABLED, false),
            'endpoint_url'   => (string) get_option(self::AUDIT_OPT_ENDPOINT, ''),
            'secret_set'     => $secret !== '',
            'secret_last4'   => $secret_last4,
            'events'         => array_values($events),
            'last_push_gmt'  => (string) get_option(self::AUDIT_OPT_LAST_PUSH_GMT, ''),
            'failure_count'  => (int) get_option(self::AUDIT_OPT_FAILURE_COUNT, 0),
            'last_error'     => (string) get_option(self::AUDIT_OPT_LAST_ERROR, ''),
            'plugin_version' => self::VERSION,
        ]);
    }

    /**
     * POST /airano-mcp/v1/audit-hook — upsert config.
     * Body: {endpoint_url, secret, enabled, events}
     */
    public function handle_audit_hook_set($request) {
        $params = $request->get_json_params();
        if (!is_array($params)) {
            return new WP_Error(
                'invalid_body',
                __( 'JSON body required.', 'airano-mcp-bridge' ),
                ['status' => 400]
            );
        }

        if (isset($params['endpoint_url'])) {
            $raw_url = (string) $params['endpoint_url'];
            $url = esc_url_raw( $raw_url, [ 'http', 'https' ] );
            if ($url === '' && $raw_url !== '') {
                return new WP_Error(
                    'invalid_url',
                    __( 'endpoint_url must be a valid http:// or https:// URL.', 'airano-mcp-bridge' ),
                    ['status' => 400]
                );
            }
            // Defence-in-depth: also reject schemes esc_url_raw accepts but
            // we never want here (e.g. mailto:, javascript:, data:).
            if ( $url !== '' ) {
                $scheme = wp_parse_url( $url, PHP_URL_SCHEME );
                if ( ! in_array( $scheme, [ 'http', 'https' ], true ) ) {
                    return new WP_Error(
                        'invalid_url_scheme',
                        __( 'endpoint_url scheme must be http or https.', 'airano-mcp-bridge' ),
                        ['status' => 400]
                    );
                }
            }
            update_option(self::AUDIT_OPT_ENDPOINT, $url, false);
        }

        if (isset($params['secret'])) {
            $secret = (string) $params['secret'];
            if (strlen($secret) > 0 && strlen($secret) < 16) {
                return new WP_Error(
                    'secret_too_short',
                    __( 'Shared secret must be at least 16 characters (use a random token).', 'airano-mcp-bridge' ),
                    ['status' => 400]
                );
            }
            update_option(self::AUDIT_OPT_SECRET, $secret, false);
        }

        if (array_key_exists('enabled', $params)) {
            update_option(
                self::AUDIT_OPT_ENABLED,
                $this->bool_param($params['enabled'], false),
                false
            );
        }

        if (isset($params['events']) && is_array($params['events'])) {
            $clean = array_values(array_unique(array_filter(array_map(
                function ($e) { return is_string($e) ? sanitize_key($e) : null; },
                $params['events']
            ))));
            if (empty($clean)) {
                $clean = self::AUDIT_DEFAULT_EVENTS;
            }
            update_option(self::AUDIT_OPT_EVENTS, $clean, false);
        }

        // Reset failure counters on successful config change so operators
        // don't see stale errors after fixing the endpoint.
        update_option(self::AUDIT_OPT_FAILURE_COUNT, 0, false);
        update_option(self::AUDIT_OPT_LAST_ERROR, '', false);

        // Re-register hooks immediately so the new event list takes effect
        // without requiring a page reload on the WP side.
        $this->audit_register_hooks();

        return $this->handle_audit_hook_get();
    }

    /**
     * DELETE /airano-mcp/v1/audit-hook — disable + clear config.
     * Deliberately does NOT leave the secret in wp_options.
     */
    public function handle_audit_hook_clear() {
        delete_option(self::AUDIT_OPT_ENABLED);
        delete_option(self::AUDIT_OPT_ENDPOINT);
        delete_option(self::AUDIT_OPT_SECRET);
        delete_option(self::AUDIT_OPT_EVENTS);
        delete_option(self::AUDIT_OPT_LAST_PUSH_GMT);
        delete_option(self::AUDIT_OPT_FAILURE_COUNT);
        delete_option(self::AUDIT_OPT_LAST_ERROR);

        return rest_ensure_response([
            'enabled'        => false,
            'endpoint_url'   => '',
            'secret_set'     => false,
            'cleared'        => true,
            'plugin_version' => self::VERSION,
        ]);
    }

    // ------------------------------------------------------------------
    //  F.5a.8.2 — Regenerate attachment thumbnails
    // ------------------------------------------------------------------

    /**
     * POST /airano-mcp/v1/regenerate-thumbnails
     *
     * Body shapes:
     *   { "ids": [12, 34, 56] }             — regenerate specific attachments
     *   { "all": true }                     — batch mode starting at offset 0
     *   { "all": true, "offset": 100, "limit": 25 }  — paged batch
     *
     * Per request cap: 50 attachments. Callers paginate via the returned
     * `next_offset` when `has_more` is true. Only `image/*` attachments are
     * regenerated; other types are silently skipped.
     *
     * Uses `wp_generate_attachment_metadata()` which rebuilds the size set
     * registered by `add_image_size()` plus the standard WP sizes.
     */
    public function handle_regenerate_thumbnails( $request ) {
        $body  = $request->get_json_params();
        if ( ! is_array( $body ) ) {
            $body = [];
        }

        // The helper requires the core metadata functions, which are not
        // loaded on REST requests by default.
        require_once ABSPATH . 'wp-admin/includes/image.php';

        $per_call_cap = 50;
        $ids          = [];
        $mode         = 'ids';
        $next_offset  = null;
        $has_more     = false;
        $total        = null;

        if ( ! empty( $body['ids'] ) && is_array( $body['ids'] ) ) {
            foreach ( $body['ids'] as $raw_id ) {
                $id = (int) $raw_id;
                if ( $id > 0 ) {
                    $ids[] = $id;
                }
            }
            $ids = array_slice( array_values( array_unique( $ids ) ), 0, $per_call_cap );
        } elseif ( ! empty( $body['all'] ) ) {
            $mode   = 'all';
            $offset = isset( $body['offset'] ) ? max( 0, (int) $body['offset'] ) : 0;
            $limit  = isset( $body['limit'] )  ? max( 1, (int) $body['limit'] )  : $per_call_cap;
            $limit  = min( $limit, $per_call_cap );

            $query = new WP_Query( [
                'post_type'      => 'attachment',
                'post_status'    => 'inherit',
                'post_mime_type' => 'image',
                'fields'         => 'ids',
                'posts_per_page' => $limit,
                'offset'         => $offset,
                'orderby'        => 'ID',
                'order'          => 'ASC',
                'no_found_rows'  => false,
            ] );
            $ids        = array_map( 'intval', $query->posts );
            $total      = (int) $query->found_posts;
            $next_offset = $offset + count( $ids );
            $has_more   = $next_offset < $total;
        } else {
            return new WP_Error(
                'airano_mcp_invalid_request',
                __( 'Provide either "ids" (array of attachment IDs) or "all": true.', 'airano-mcp-bridge' ),
                [ 'status' => 400 ]
            );
        }

        $processed = 0;
        $skipped   = [];
        $errors    = [];

        foreach ( $ids as $attachment_id ) {
            $mime = get_post_mime_type( $attachment_id );
            if ( ! $mime || strpos( $mime, 'image/' ) !== 0 ) {
                $skipped[] = [ 'id' => $attachment_id, 'reason' => 'not_image' ];
                continue;
            }
            if ( ! current_user_can( 'edit_post', $attachment_id ) ) {
                $errors[] = [ 'id' => $attachment_id, 'error' => 'forbidden' ];
                continue;
            }

            $file = get_attached_file( $attachment_id );
            if ( ! $file || ! file_exists( $file ) ) {
                $errors[] = [ 'id' => $attachment_id, 'error' => 'file_missing' ];
                continue;
            }

            $meta = wp_generate_attachment_metadata( $attachment_id, $file );
            if ( is_wp_error( $meta ) ) {
                $errors[] = [
                    'id'    => $attachment_id,
                    'error' => $meta->get_error_code(),
                    'message' => $meta->get_error_message(),
                ];
                continue;
            }
            if ( ! is_array( $meta ) || empty( $meta ) ) {
                $errors[] = [ 'id' => $attachment_id, 'error' => 'empty_metadata' ];
                continue;
            }

            wp_update_attachment_metadata( $attachment_id, $meta );
            $processed++;
        }

        $response = [
            'plugin_version' => self::VERSION,
            'mode'           => $mode,
            'attempted'      => count( $ids ),
            'processed'      => $processed,
            'skipped'        => $skipped,
            'errors'         => $errors,
        ];

        if ( 'all' === $mode ) {
            $response['offset']      = isset( $body['offset'] ) ? (int) $body['offset'] : 0;
            $response['limit']       = isset( $body['limit'] ) ? (int) $body['limit'] : $per_call_cap;
            $response['has_more']    = $has_more;
            $response['next_offset'] = $next_offset;
            $response['total']       = $total;
        }

        return rest_ensure_response( $response );
    }

    /**
     * Attach WordPress action hooks for every configured audit event.
     * Called from __construct() and after handle_audit_hook_set().
     */
    private function audit_register_hooks() {
        if (!get_option(self::AUDIT_OPT_ENABLED, false)) {
            return;
        }
        $events = get_option(self::AUDIT_OPT_EVENTS, self::AUDIT_DEFAULT_EVENTS);
        if (!is_array($events)) {
            return;
        }

        foreach ($events as $event) {
            switch ($event) {
                case 'transition_post_status':
                    add_action('transition_post_status', [$this, 'audit_on_transition_post'], 10, 3);
                    break;
                case 'deleted_post':
                    add_action('deleted_post', [$this, 'audit_on_deleted_post'], 10, 1);
                    break;
                case 'user_register':
                    add_action('user_register', [$this, 'audit_on_user_register'], 10, 1);
                    break;
                case 'profile_update':
                    add_action('profile_update', [$this, 'audit_on_profile_update'], 10, 1);
                    break;
                case 'deleted_user':
                    add_action('deleted_user', [$this, 'audit_on_deleted_user'], 10, 1);
                    break;
                case 'activated_plugin':
                    add_action('activated_plugin', [$this, 'audit_on_activated_plugin'], 10, 1);
                    break;
                case 'deactivated_plugin':
                    add_action('deactivated_plugin', [$this, 'audit_on_deactivated_plugin'], 10, 1);
                    break;
                case 'switch_theme':
                    add_action('switch_theme', [$this, 'audit_on_switch_theme'], 10, 1);
                    break;
            }
        }
    }

    public function audit_on_transition_post($new_status, $old_status, $post) {
        if ($new_status === $old_status) {
            return;
        }
        $this->audit_push('transition_post_status', [
            'post_id'    => is_object($post) ? (int) $post->ID : null,
            'post_type'  => is_object($post) ? $post->post_type : null,
            'title'      => is_object($post) ? $post->post_title : null,
            'new_status' => $new_status,
            'old_status' => $old_status,
        ]);
    }

    public function audit_on_deleted_post($post_id) {
        $this->audit_push('deleted_post', ['post_id' => (int) $post_id]);
    }

    public function audit_on_user_register($user_id) {
        $this->audit_push('user_register', ['user_id' => (int) $user_id]);
    }

    public function audit_on_profile_update($user_id) {
        $this->audit_push('profile_update', ['user_id' => (int) $user_id]);
    }

    public function audit_on_deleted_user($user_id) {
        $this->audit_push('deleted_user', ['user_id' => (int) $user_id]);
    }

    public function audit_on_activated_plugin($plugin) {
        $this->audit_push('activated_plugin', ['plugin' => (string) $plugin]);
    }

    public function audit_on_deactivated_plugin($plugin) {
        $this->audit_push('deactivated_plugin', ['plugin' => (string) $plugin]);
    }

    public function audit_on_switch_theme($new_theme) {
        $this->audit_push('switch_theme', ['new_theme' => (string) $new_theme]);
    }

    /**
     * Sign + POST an event to the configured MCPHub endpoint.
     * Non-blocking (`blocking=false`) so WP admin requests stay snappy —
     * at the cost of not being able to detect per-event delivery failures
     * inline. Failures are instead discovered by MCPHub's own retry /
     * missing-event analysis.
     */
    private function audit_push($event, $data) {
        $endpoint = (string) get_option(self::AUDIT_OPT_ENDPOINT, '');
        $secret   = (string) get_option(self::AUDIT_OPT_SECRET, '');
        if ($endpoint === '' || $secret === '') {
            return;
        }

        $envelope = [
            'event'       => (string) $event,
            'site_url'    => site_url(),
            'timestamp'   => gmdate('Y-m-d\TH:i:s\Z'),
            'user_id'     => (int) get_current_user_id(),
            'data'        => $data,
            'plugin_version' => self::VERSION,
        ];
        $body = wp_json_encode($envelope);
        if ($body === false) {
            return;
        }

        $signature = hash_hmac('sha256', $body, $secret);

        $args = [
            'method'      => 'POST',
            'timeout'     => 2,
            'redirection' => 0,
            'blocking'    => false,
            'headers'     => [
                'Content-Type'            => 'application/json',
                'X-Airano-MCP-Signature'  => 'sha256=' . $signature,
                'X-Airano-MCP-Site'       => site_url(),
                'X-Airano-MCP-Version'    => self::VERSION,
                'User-Agent'              => 'Airano-MCP-Bridge/' . self::VERSION,
            ],
            'body' => $body,
        ];

        $resp = wp_remote_post($endpoint, $args);
        // With blocking=false we get a WP_HTTP_Requests_Response-shaped stub
        // that doesn't carry a real status; record the attempt timestamp
        // so operators know pushes are happening at all.
        update_option(self::AUDIT_OPT_LAST_PUSH_GMT, gmdate('Y-m-d\TH:i:s\Z'), false);

        if (is_wp_error($resp)) {
            $failures = (int) get_option(self::AUDIT_OPT_FAILURE_COUNT, 0) + 1;
            update_option(self::AUDIT_OPT_FAILURE_COUNT, $failures, false);
            update_option(self::AUDIT_OPT_LAST_ERROR, $resp->get_error_message(), false);
        }
    }

    /**
     * Display admin notices
     */
    public function admin_notices() {
        // Only show notices on the Plugins page to avoid clutter on every admin page
        $screen = get_current_screen();
        if ( ! $screen || $screen->id !== 'plugins' ) {
            return;
        }

        $rank_math_active = $this->is_rank_math_active();
        $yoast_active = $this->is_yoast_active();
        $woocommerce_active = $this->is_woocommerce_active();

        if (!$rank_math_active && !$yoast_active) {
            echo '<div class="notice notice-warning is-dismissible">';
            echo '<p><strong>Airano MCP Bridge:</strong> ' . esc_html__( 'Neither Rank Math SEO nor Yoast SEO is detected. SEO meta routes are idle, but upload helper routes remain active.', 'airano-mcp-bridge' ) . '</p>';
            echo '</div>';
        } else {
            $active_plugins = [];
            if ($rank_math_active) $active_plugins[] = 'Rank Math SEO';
            if ($yoast_active) $active_plugins[] = 'Yoast SEO';

            $supported_types = implode(', ', $this->supported_post_types);

            echo '<div class="notice notice-success is-dismissible">';
            echo '<p><strong>Airano MCP Bridge v' . esc_html( self::VERSION ) . ':</strong> ' . esc_html(
                sprintf(
                    /* translators: %s: comma-separated list of active SEO plugin names. */
                    __( 'Successfully registered meta fields for %s.', 'airano-mcp-bridge' ),
                    implode( ' and ', $active_plugins )
                )
            ) . '</p>';
            echo '<p><strong>' . esc_html__( 'Supported post types:', 'airano-mcp-bridge' ) . '</strong> ' . esc_html( $supported_types ) . '</p>';
            echo '<p><strong>' . esc_html__( 'MCP Bridge upload helper:', 'airano-mcp-bridge' ) . '</strong> ' . esc_html__( '/wp-json/airano-mcp/v1/upload-limits + /upload-chunk (bypasses upload_max_filesize).', 'airano-mcp-bridge' ) . '</p>';

            if ($woocommerce_active) {
                echo '<p><strong>WooCommerce:</strong> ' . esc_html__( 'Detected and supported. Product SEO fields are available via REST API.', 'airano-mcp-bridge' ) . '</p>';
            }
            echo '</div>';
        }
    }

    // ============================================================
    // F.19.1 — Admin namespace handlers (read-only)
    // ============================================================

    /**
     * GET /airano-mcp/v1/admin/plugins
     *
     * Returns every plugin known to WordPress with active/network-active
     * status, version, author, update availability. No state changes;
     * activation lands in F.19.2.
     */
    public function handle_admin_plugins(WP_REST_Request $request) {
        if (!function_exists('get_plugins')) {
            require_once ABSPATH . 'wp-admin/includes/plugin.php';
        }
        $plugins = get_plugins();
        $active = (array) get_option('active_plugins', []);
        $network_active = is_multisite() ? array_keys((array) get_site_option('active_sitewide_plugins', [])) : [];

        // Update detection — use the cached transient set by WP's update
        // checker. We never trigger a fresh check here (it's slow + can
        // hit wp.org). MCPHub can force a refresh by calling the WP-CLI
        // path during F.19.3 if needed.
        $update_data = get_site_transient('update_plugins');
        $updates_available = isset($update_data->response) ? (array) $update_data->response : [];

        $items = [];
        foreach ($plugins as $file => $meta) {
            $items[] = [
                'file'           => $file,
                'slug'           => dirname($file) === '.' ? basename($file, '.php') : dirname($file),
                'name'           => isset($meta['Name']) ? (string) $meta['Name'] : '',
                'version'        => isset($meta['Version']) ? (string) $meta['Version'] : '',
                'author'         => isset($meta['Author']) ? wp_strip_all_tags((string) $meta['Author']) : '',
                'plugin_uri'     => isset($meta['PluginURI']) ? (string) $meta['PluginURI'] : '',
                'description'    => isset($meta['Description']) ? wp_strip_all_tags((string) $meta['Description']) : '',
                'active'         => in_array($file, $active, true),
                'network_active' => in_array($file, $network_active, true),
                'update_available' => isset($updates_available[$file]),
                'new_version'    => isset($updates_available[$file]->new_version)
                    ? (string) $updates_available[$file]->new_version : null,
            ];
        }

        return rest_ensure_response([
            'plugins'      => $items,
            'total'        => count($items),
            'active_count' => count($active),
            'multisite'    => is_multisite(),
        ]);
    }

    /**
     * GET /airano-mcp/v1/admin/themes
     *
     * Lists every installed theme + which is active. Parent/child
     * relationship surfaced via ``parent`` field.
     */
    public function handle_admin_themes(WP_REST_Request $request) {
        $themes = wp_get_themes();
        $active_stylesheet = get_option('stylesheet');
        $active_template = get_option('template');

        $update_data = get_site_transient('update_themes');
        $updates_available = isset($update_data->response) ? (array) $update_data->response : [];

        $items = [];
        foreach ($themes as $stylesheet => $theme) {
            /** @var WP_Theme $theme */
            $parent = $theme->parent();
            $items[] = [
                'stylesheet'       => (string) $stylesheet,
                'name'             => (string) $theme->get('Name'),
                'version'          => (string) $theme->get('Version'),
                'author'           => wp_strip_all_tags((string) $theme->get('Author')),
                'description'      => wp_strip_all_tags((string) $theme->get('Description')),
                'theme_uri'        => (string) $theme->get('ThemeURI'),
                'template'         => (string) $theme->get_template(),
                'parent'           => $parent ? (string) $parent->get_stylesheet() : null,
                'is_block_theme'   => method_exists($theme, 'is_block_theme') ? (bool) $theme->is_block_theme() : false,
                'active'           => $stylesheet === $active_stylesheet,
                'is_template'      => $stylesheet === $active_template,
                'update_available' => isset($updates_available[$stylesheet]),
                'new_version'      => isset($updates_available[$stylesheet]['new_version'])
                    ? (string) $updates_available[$stylesheet]['new_version'] : null,
            ];
        }

        return rest_ensure_response([
            'themes'             => $items,
            'total'              => count($items),
            'active_stylesheet'  => (string) $active_stylesheet,
            'active_template'    => (string) $active_template,
        ]);
    }

    /**
     * GET /airano-mcp/v1/admin/users
     *
     * Lists users (id, username, email, roles, registration timestamp).
     * Honours the ``role`` and ``search`` query params; default cap of
     * 200 per call to keep payload sane on large installs.
     */
    public function handle_admin_users(WP_REST_Request $request) {
        $role  = $request->get_param('role');
        $search = $request->get_param('search');
        $per_page = (int) $request->get_param('per_page');
        if ($per_page <= 0 || $per_page > 200) {
            $per_page = 50;
        }
        $page = (int) $request->get_param('page');
        if ($page <= 0) {
            $page = 1;
        }

        $args = [
            'number' => $per_page,
            'paged'  => $page,
            'fields' => ['ID', 'user_login', 'user_email', 'user_registered', 'display_name'],
        ];
        if (is_string($role) && $role !== '') {
            $args['role'] = sanitize_key($role);
        }
        if (is_string($search) && $search !== '') {
            $args['search']         = '*' . esc_attr($search) . '*';
            $args['search_columns'] = ['user_login', 'user_email', 'display_name'];
        }

        $query = new WP_User_Query($args);
        $items = [];
        foreach ((array) $query->get_results() as $user) {
            $u = get_userdata($user->ID);
            if (!$u) {
                continue;
            }
            $items[] = [
                'id'              => (int) $u->ID,
                'username'        => (string) $u->user_login,
                'email'           => (string) $u->user_email,
                'display_name'    => (string) $u->display_name,
                'roles'           => array_values((array) $u->roles),
                'user_registered' => (string) $u->user_registered,
            ];
        }

        return rest_ensure_response([
            'users'       => $items,
            'total'       => (int) $query->get_total(),
            'page'        => $page,
            'per_page'    => $per_page,
        ]);
    }

    /**
     * GET /airano-mcp/v1/admin/options/{name}
     *
     * Returns a single named option. Refuses keys that match the
     * deny-list of credential-shaped suffixes. The caller already has
     * ``manage_options``, so this is a defence-in-depth check (operators
     * who store extra secrets in custom options should still be safe).
     */
    public function handle_admin_option_get(WP_REST_Request $request) {
        $name = (string) $request->get_param('name');
        $name = sanitize_key($name);
        if ($name === '') {
            return new WP_Error(
                'invalid_option_name',
                __( 'Option name is required.', 'airano-mcp-bridge' ),
                ['status' => 400]
            );
        }

        foreach (self::ADMIN_OPTION_BLOCKED_PATTERNS as $pattern) {
            if (preg_match($pattern, $name)) {
                return new WP_Error(
                    'option_blocked',
                    __( 'This option key is blocked from remote read for safety. Inspect it directly via wp-admin if needed.', 'airano-mcp-bridge' ),
                    ['status' => 403, 'option' => $name]
                );
            }
        }

        $sentinel = '__airano_mcp_missing__';
        $value = get_option($name, $sentinel);
        $exists = ($value !== $sentinel);
        if (!$exists) {
            $value = null;
        }

        return rest_ensure_response([
            'option'  => $name,
            'exists'  => $exists,
            'value'   => $value,
            'autoload' => $exists ? null : null,  // reserved for F.19.2
        ]);
    }

    /**
     * GET /airano-mcp/v1/admin/cron
     *
     * Dumps the current cron array (next run, hook name, schedule, args).
     * Times reported as both unix epoch and ISO 8601 UTC.
     */
    public function handle_admin_cron(WP_REST_Request $request) {
        $cron = _get_cron_array();
        $events = [];
        if (is_array($cron)) {
            foreach ($cron as $timestamp => $hooks) {
                if (!is_array($hooks)) {
                    continue;
                }
                foreach ($hooks as $hook => $instances) {
                    if (!is_array($instances)) {
                        continue;
                    }
                    foreach ($instances as $key => $event) {
                        $schedule = isset($event['schedule']) ? (string) $event['schedule'] : '';
                        $interval = isset($event['interval']) ? (int) $event['interval'] : null;
                        $events[] = [
                            'hook'         => (string) $hook,
                            'next_run_at'  => (int) $timestamp,
                            'next_run_iso' => gmdate('c', (int) $timestamp),
                            'schedule'     => $schedule,
                            'interval_sec' => $interval,
                            'args'         => isset($event['args']) ? $event['args'] : [],
                            'key'          => (string) $key,
                        ];
                    }
                }
            }
        }

        return rest_ensure_response([
            'events'    => $events,
            'total'     => count($events),
            'now'       => time(),
            'now_iso'   => gmdate('c'),
            'timezone'  => (string) wp_timezone_string(),
            'doing_cron' => (bool) defined('DOING_CRON') && DOING_CRON,
        ]);
    }

    /**
     * GET /airano-mcp/v1/admin/maintenance
     *
     * Reports maintenance-mode status by inspecting WP's
     * ``.maintenance`` sentinel file in ABSPATH (set during core/plugin
     * updates, removed when finished). Toggling lands in F.19.2.
     */
    public function handle_admin_maintenance(WP_REST_Request $request) {
        $sentinel = ABSPATH . '.maintenance';
        $enabled = false;
        $started_at = null;
        $stale = false;

        if (file_exists($sentinel)) {
            $enabled = true;
            $upgrading = 0;
            // The file defines $upgrading = time() at the moment WP
            // entered maintenance. Read it without including (the file
            // only does an integer assignment, but include is risky).
            $contents = file_get_contents($sentinel);
            if (is_string($contents) && preg_match('/\$upgrading\s*=\s*(\d+)/', $contents, $m)) {
                $upgrading = (int) $m[1];
            }
            $started_at = $upgrading > 0 ? $upgrading : null;
            // WP itself treats >10 min as stale (wp_is_maintenance_mode).
            $stale = $upgrading > 0 && (time() - $upgrading) > 600;
        }

        return rest_ensure_response([
            'enabled'    => $enabled,
            'started_at' => $started_at,
            'started_iso' => $started_at ? gmdate('c', $started_at) : null,
            'stale'      => $stale,
        ]);
    }

    // ============================================================
    // F.19.3.1 — Ports from wordpress_advanced (read-only)
    // ============================================================

    /**
     * GET /airano-mcp/v1/admin/system-info
     *
     * Replaces wordpress_advanced.system_info — returns the same shape
     * the WP-CLI version produced (PHP/MySQL/WordPress versions, server
     * software, memory limits, time settings, multisite flag) but via
     * native PHP so no Docker socket is required.
     */
    public function handle_admin_system_info(WP_REST_Request $request) {
        global $wpdb;

        $mysql_version = '';
        try {
            $row = $wpdb->get_var('SELECT VERSION()');
            if (is_string($row)) {
                $mysql_version = $row;
            }
        } catch (Exception $e) {  // pragma: defensive
            $mysql_version = '';
        }

        $upload_dir = wp_upload_dir();

        return rest_ensure_response([
            'wordpress' => [
                'version'      => get_bloginfo('version'),
                'site_url'     => home_url(),
                'admin_url'    => admin_url(),
                'language'     => get_locale(),
                'timezone'     => (string) wp_timezone_string(),
                'multisite'    => is_multisite(),
                'debug'        => defined('WP_DEBUG') && WP_DEBUG,
                'debug_log'    => defined('WP_DEBUG_LOG') && WP_DEBUG_LOG,
                'memory_limit' => defined('WP_MEMORY_LIMIT') ? WP_MEMORY_LIMIT : null,
            ],
            'php' => [
                'version'              => PHP_VERSION,
                'sapi'                 => PHP_SAPI,
                'memory_limit'         => ini_get('memory_limit'),
                'max_execution_time'   => (int) ini_get('max_execution_time'),
                'post_max_size'        => ini_get('post_max_size'),
                'upload_max_filesize'  => ini_get('upload_max_filesize'),
                'max_input_vars'       => (int) ini_get('max_input_vars'),
            ],
            'database' => [
                'engine'        => 'MySQL/MariaDB',
                'version'       => $mysql_version,
                'charset'       => defined('DB_CHARSET') ? DB_CHARSET : null,
                'collate'       => defined('DB_COLLATE') ? DB_COLLATE : null,
                'table_prefix'  => $wpdb->prefix,
            ],
            'server' => [
                'software'   => isset($_SERVER['SERVER_SOFTWARE']) ? sanitize_text_field(wp_unslash($_SERVER['SERVER_SOFTWARE'])) : '',
                'os'         => function_exists('php_uname') ? php_uname('s') . ' ' . php_uname('r') : '',
                'protocol'   => isset($_SERVER['SERVER_PROTOCOL']) ? sanitize_text_field(wp_unslash($_SERVER['SERVER_PROTOCOL'])) : '',
            ],
            'paths' => [
                'abspath'    => ABSPATH,
                'wp_content' => defined('WP_CONTENT_DIR') ? WP_CONTENT_DIR : null,
                'plugins'    => defined('WP_PLUGIN_DIR') ? WP_PLUGIN_DIR : null,
                'uploads'    => $upload_dir['basedir'] ?? null,
            ],
        ]);
    }

    /**
     * GET /airano-mcp/v1/admin/phpinfo
     *
     * Curated PHP configuration snapshot — extension list, common ini
     * settings, disabled functions, opcache state. Unlike PHP's
     * built-in ``phpinfo()`` this returns structured JSON; we never
     * dump full ``phpinfo(INFO_ALL)`` output because that leaks
     * server-internal paths and credentials.
     */
    public function handle_admin_phpinfo(WP_REST_Request $request) {
        $extensions = get_loaded_extensions();
        sort($extensions);

        // Curated subset of ini settings — covers the common
        // diagnostic surface (memory, file uploads, sessions) without
        // exposing the full ini map.
        $ini_keys = [
            'memory_limit',
            'max_execution_time',
            'max_input_time',
            'max_input_vars',
            'post_max_size',
            'upload_max_filesize',
            'file_uploads',
            'allow_url_fopen',
            'allow_url_include',
            'display_errors',
            'log_errors',
            'error_log',
            'session.gc_maxlifetime',
            'session.save_handler',
            'date.timezone',
            'default_socket_timeout',
        ];
        $ini = [];
        foreach ($ini_keys as $key) {
            $ini[$key] = ini_get($key);
        }

        $opcache_enabled = function_exists('opcache_get_status') && (bool) ini_get('opcache.enable');
        $opcache = null;
        if ($opcache_enabled) {
            $status = @opcache_get_status(false);
            if (is_array($status)) {
                $opcache = [
                    'enabled'         => (bool) ($status['opcache_enabled'] ?? false),
                    'cache_full'      => (bool) ($status['cache_full'] ?? false),
                    'memory_used'     => (int) ($status['memory_usage']['used_memory'] ?? 0),
                    'memory_free'     => (int) ($status['memory_usage']['free_memory'] ?? 0),
                    'cached_scripts'  => (int) ($status['opcache_statistics']['num_cached_scripts'] ?? 0),
                ];
            }
        }

        $disabled_functions_raw = (string) ini_get('disable_functions');
        $disabled_functions = $disabled_functions_raw === ''
            ? []
            : array_values(array_filter(array_map('trim', explode(',', $disabled_functions_raw))));

        return rest_ensure_response([
            'php_version'        => PHP_VERSION,
            'sapi'               => PHP_SAPI,
            'extensions'         => $extensions,
            'ini'                => $ini,
            'disabled_functions' => $disabled_functions,
            'opcache'            => $opcache,
        ]);
    }

    /**
     * GET /airano-mcp/v1/admin/disk-usage
     *
     * Replaces wordpress_advanced.system_disk_usage. Returns bytes (not
     * MB strings) so the dashboard can format them client-side. Walks
     * uploads, plugins, themes — caps at 200k files / 5s wall clock per
     * tree to keep the route bounded on huge installs.
     */
    public function handle_admin_disk_usage(WP_REST_Request $request) {
        $upload_dir = wp_upload_dir();
        $uploads_path = $upload_dir['basedir'] ?? '';
        $plugins_path = defined('WP_PLUGIN_DIR') ? WP_PLUGIN_DIR : '';
        $themes_path = defined('WP_CONTENT_DIR') ? trailingslashit(WP_CONTENT_DIR) . 'themes' : '';
        $abspath = ABSPATH;

        $uploads = $this->_safe_dir_size($uploads_path);
        $plugins = $this->_safe_dir_size($plugins_path);
        $themes  = $this->_safe_dir_size($themes_path);

        $disk_total = function_exists('disk_total_space') ? @disk_total_space($abspath) : null;
        $disk_free  = function_exists('disk_free_space') ? @disk_free_space($abspath) : null;
        $disk_used  = ($disk_total !== false && $disk_free !== false && $disk_total !== null && $disk_free !== null)
            ? ($disk_total - $disk_free) : null;

        return rest_ensure_response([
            'uploads' => $uploads,
            'plugins' => $plugins,
            'themes'  => $themes,
            'disk' => [
                'total_bytes' => $disk_total === false ? null : $disk_total,
                'free_bytes'  => $disk_free === false ? null : $disk_free,
                'used_bytes'  => $disk_used,
            ],
            'paths' => [
                'uploads' => $uploads_path,
                'plugins' => $plugins_path,
                'themes'  => $themes_path,
                'abspath' => $abspath,
            ],
        ]);
    }

    /**
     * Safely walk a directory tree and return total bytes + file count.
     * Bounded at 200,000 files OR 5 seconds wall clock per tree so a
     * pathological directory cannot hang the request. Truncated walks
     * surface ``truncated: true`` in the response so the caller can
     * tell the number is a lower bound.
     */
    private function _safe_dir_size(string $path): array {
        if ($path === '' || !is_dir($path) || !is_readable($path)) {
            return ['size_bytes' => 0, 'file_count' => 0, 'truncated' => false, 'available' => false];
        }
        $deadline = microtime(true) + 5.0;
        $max_files = 200000;
        $size = 0;
        $count = 0;
        $truncated = false;
        try {
            $iterator = new RecursiveIteratorIterator(
                new RecursiveDirectoryIterator($path, FilesystemIterator::SKIP_DOTS | FilesystemIterator::FOLLOW_SYMLINKS)
            );
            foreach ($iterator as $file) {
                if ($file->isFile()) {
                    $size += (int) $file->getSize();
                    $count++;
                    if ($count >= $max_files || microtime(true) > $deadline) {
                        $truncated = true;
                        break;
                    }
                }
            }
        } catch (Exception $e) {
            // Permission denied somewhere mid-walk — return what we have.
            $truncated = true;
        }
        return [
            'size_bytes' => $size,
            'file_count' => $count,
            'truncated'  => $truncated,
            'available'  => true,
        ];
    }

    // ============================================================
    // F.19.5 — Page editing (Gutenberg + Elementor + Classic)
    // ============================================================
    //
    // Security rules enforced here, on top of the F.19.2 S-1…S-11 set
    // documented in `docs/ROADMAP.md`:
    //   * S-12 — every block / Elementor write requires `edit_post`
    //            on the target post (per-item, not just the global tier).
    //   * S-13 — block content is sanitised via `wp_kses_post` by
    //            default; `raw_html=true` only with `unfiltered_html`
    //            (which WP grants only to administrators on
    //            single-site, and only to network admins on
    //            multisite).
    //   * S-14 — Elementor JSON node count capped at 5,000 per call
    //            to bound parse cost; oversized payloads return
    //            `elementor_too_large`.

    /**
     * Maximum number of blocks accepted in a single F.19.5 write call.
     * Bounds parse + serialize cost on huge `wp_kses_post` runs.
     */
    const BLOCKS_MAX_PER_CALL = 200;

    /**
     * Maximum number of Elementor nodes accepted in a single F.19.5
     * write call (S-14). Counted recursively across the whole tree.
     */
    const ELEMENTOR_MAX_NODES = 5000;

    /**
     * Resolve a post id from request input.
     *
     * @param mixed $raw The raw input (from URL param or JSON body).
     * @return int|WP_Error Positive int post id on success, WP_Error otherwise.
     */
    private function _resolve_post_id($raw) {
        if (!is_numeric($raw)) {
            return new WP_Error(
                'invalid_post_id',
                __( 'post_id must be an integer.', 'airano-mcp-bridge' ),
                ['status' => 400]
            );
        }
        $post_id = (int) $raw;
        if ($post_id <= 0) {
            return new WP_Error(
                'invalid_post_id',
                __( 'post_id must be a positive integer.', 'airano-mcp-bridge' ),
                ['status' => 400]
            );
        }
        $post = get_post($post_id);
        if (!$post) {
            return new WP_Error(
                'post_not_found',
                sprintf(
                    /* translators: %d is the post id. */
                    __( 'No post with id %d exists.', 'airano-mcp-bridge' ),
                    $post_id
                ),
                ['status' => 404]
            );
        }
        // S-12 — per-item edit_post check on top of the route-level
        // manage_options gate.
        if (!current_user_can('edit_post', $post_id)) {
            return new WP_Error(
                'rest_forbidden',
                __( 'Current user cannot edit this post.', 'airano-mcp-bridge' ),
                ['status' => 403]
            );
        }
        return $post_id;
    }

    /**
     * Sanitize a single block's content per S-13.
     *
     * Recursively walks the block tree applying `wp_kses_post` to
     * `innerHTML` / `innerContent` strings. When `$raw_html` is true
     * and the current user has `unfiltered_html`, the strings are
     * passed through unchanged. Anything else falls back to
     * `wp_kses_post` regardless of the flag (defence in depth — a
     * caller can never bypass sanitisation by lying about caps).
     *
     * @param array $blocks   Parsed block tree from `parse_blocks()`.
     * @param bool  $raw_html Whether to skip sanitisation.
     * @return array Sanitised block tree (same shape).
     */
    private function _sanitize_blocks(array $blocks, bool $raw_html): array {
        $allow_raw = $raw_html && current_user_can('unfiltered_html');
        return array_values(array_map(
            function ($block) use ($allow_raw) {
                if (!is_array($block)) {
                    return $block;
                }
                if (isset($block['innerHTML']) && is_string($block['innerHTML']) && !$allow_raw) {
                    $block['innerHTML'] = wp_kses_post($block['innerHTML']);
                }
                if (isset($block['innerContent']) && is_array($block['innerContent']) && !$allow_raw) {
                    $block['innerContent'] = array_map(
                        function ($chunk) {
                            return is_string($chunk) ? wp_kses_post($chunk) : $chunk;
                        },
                        $block['innerContent']
                    );
                }
                if (isset($block['innerBlocks']) && is_array($block['innerBlocks'])) {
                    $block['innerBlocks'] = $this->_sanitize_blocks($block['innerBlocks'], $allow_raw);
                }
                return $block;
            },
            $blocks
        ));
    }

    /**
     * Validate Elementor data shape per S-14 — every node must carry
     * `id`, `elType`, `settings`, and the recursive node count must
     * stay under {@see ELEMENTOR_MAX_NODES}.
     *
     * @param array $tree Top-level Elementor data array.
     * @return true|WP_Error true on success, WP_Error on validation failure.
     */
    private function _validate_elementor_tree(array $tree) {
        $count = 0;
        $walker = function (array $nodes) use (&$walker, &$count) {
            foreach ($nodes as $node) {
                if (!is_array($node)) {
                    return new WP_Error(
                        'elementor_invalid',
                        __( 'Elementor node must be an object.', 'airano-mcp-bridge' ),
                        ['status' => 400]
                    );
                }
                foreach (['id', 'elType', 'settings'] as $required) {
                    if (!array_key_exists($required, $node)) {
                        return new WP_Error(
                            'elementor_invalid',
                            sprintf(
                                /* translators: %s is the missing field name. */
                                __( 'Elementor node missing required field: %s', 'airano-mcp-bridge' ),
                                $required
                            ),
                            ['status' => 400]
                        );
                    }
                }
                $count++;
                if ($count > self::ELEMENTOR_MAX_NODES) {
                    return new WP_Error(
                        'elementor_too_large',
                        sprintf(
                            /* translators: %d is the configured node cap. */
                            __( 'Elementor payload exceeds %d nodes — use template apply instead.', 'airano-mcp-bridge' ),
                            self::ELEMENTOR_MAX_NODES
                        ),
                        ['status' => 413]
                    );
                }
                if (!empty($node['elements']) && is_array($node['elements'])) {
                    $err = $walker($node['elements']);
                    if (is_wp_error($err)) {
                        return $err;
                    }
                }
            }
            return null;
        };
        $err = $walker($tree);
        if (is_wp_error($err)) {
            return $err;
        }
        return true;
    }

    /**
     * Read-back helper: parse a post's content into blocks and return
     * the ready-to-send envelope used by /admin/blocks/* responses.
     */
    private function _blocks_envelope(int $post_id): array {
        $post = get_post($post_id);
        $blocks = parse_blocks((string) ($post ? $post->post_content : ''));
        return [
            'post_id' => $post_id,
            'count'   => count($blocks),
            'blocks'  => $blocks,
        ];
    }

    /**
     * POST /airano-mcp/v1/admin/blocks/replace
     *
     * Body: { "post_id": int, "blocks": array, "raw_html"?: bool }
     */
    public function handle_admin_blocks_replace(WP_REST_Request $request) {
        $params = $request->get_json_params();
        if (!is_array($params)) {
            return new WP_Error('invalid_body', __( 'Expected JSON body.', 'airano-mcp-bridge' ), ['status' => 400]);
        }
        $post_id = $this->_resolve_post_id($params['post_id'] ?? null);
        if (is_wp_error($post_id)) {
            return $post_id;
        }
        $blocks = $params['blocks'] ?? null;
        if (!is_array($blocks)) {
            return new WP_Error('invalid_blocks', __( '`blocks` must be an array.', 'airano-mcp-bridge' ), ['status' => 400]);
        }
        if (count($blocks) > self::BLOCKS_MAX_PER_CALL) {
            return new WP_Error(
                'blocks_too_large',
                sprintf(
                    /* translators: %d is the per-call cap. */
                    __( 'Block payload exceeds %d items per call.', 'airano-mcp-bridge' ),
                    self::BLOCKS_MAX_PER_CALL
                ),
                ['status' => 413]
            );
        }
        $sanitised = $this->_sanitize_blocks($blocks, !empty($params['raw_html']));
        $serialised = serialize_blocks($sanitised);
        $update = wp_update_post([
            'ID'           => $post_id,
            'post_content' => $serialised,
        ], true);
        if (is_wp_error($update)) {
            return $update;
        }
        return rest_ensure_response($this->_blocks_envelope($post_id));
    }

    /**
     * POST /airano-mcp/v1/admin/blocks/insert
     *
     * Body: { "post_id": int, "index": int, "block": array, "raw_html"?: bool }
     */
    public function handle_admin_blocks_insert(WP_REST_Request $request) {
        $params = $request->get_json_params();
        if (!is_array($params)) {
            return new WP_Error('invalid_body', __( 'Expected JSON body.', 'airano-mcp-bridge' ), ['status' => 400]);
        }
        $post_id = $this->_resolve_post_id($params['post_id'] ?? null);
        if (is_wp_error($post_id)) {
            return $post_id;
        }
        if (!isset($params['block']) || !is_array($params['block'])) {
            return new WP_Error('invalid_block', __( '`block` must be an object.', 'airano-mcp-bridge' ), ['status' => 400]);
        }
        $existing = parse_blocks((string) get_post_field('post_content', $post_id));
        $index = isset($params['index']) ? (int) $params['index'] : count($existing);
        if ($index < 0 || $index > count($existing)) {
            return new WP_Error(
                'index_out_of_range',
                sprintf(
                    /* translators: 1: requested index, 2: current block count. */
                    __( 'index %1$d out of range for post with %2$d blocks.', 'airano-mcp-bridge' ),
                    $index,
                    count($existing)
                ),
                ['status' => 400]
            );
        }
        if (count($existing) + 1 > self::BLOCKS_MAX_PER_CALL) {
            return new WP_Error(
                'blocks_too_large',
                sprintf(
                    /* translators: %d is the per-call cap. */
                    __( 'Inserting would push the post beyond %d blocks.', 'airano-mcp-bridge' ),
                    self::BLOCKS_MAX_PER_CALL
                ),
                ['status' => 413]
            );
        }
        $sanitised_one = $this->_sanitize_blocks([$params['block']], !empty($params['raw_html']));
        array_splice($existing, $index, 0, $sanitised_one);
        $update = wp_update_post([
            'ID'           => $post_id,
            'post_content' => serialize_blocks($existing),
        ], true);
        if (is_wp_error($update)) {
            return $update;
        }
        return rest_ensure_response($this->_blocks_envelope($post_id));
    }

    /**
     * POST /airano-mcp/v1/admin/blocks/remove
     *
     * Body: { "post_id": int, "index": int }
     * Returns the removed block under `removed` so the caller can rollback.
     */
    public function handle_admin_blocks_remove(WP_REST_Request $request) {
        $params = $request->get_json_params();
        if (!is_array($params)) {
            return new WP_Error('invalid_body', __( 'Expected JSON body.', 'airano-mcp-bridge' ), ['status' => 400]);
        }
        $post_id = $this->_resolve_post_id($params['post_id'] ?? null);
        if (is_wp_error($post_id)) {
            return $post_id;
        }
        $existing = parse_blocks((string) get_post_field('post_content', $post_id));
        if (!isset($params['index']) || !is_numeric($params['index'])) {
            return new WP_Error('invalid_index', __( '`index` is required.', 'airano-mcp-bridge' ), ['status' => 400]);
        }
        $index = (int) $params['index'];
        if ($index < 0 || $index >= count($existing)) {
            return new WP_Error(
                'index_out_of_range',
                sprintf(
                    /* translators: 1: requested index, 2: current block count. */
                    __( 'index %1$d out of range for post with %2$d blocks.', 'airano-mcp-bridge' ),
                    $index,
                    count($existing)
                ),
                ['status' => 400]
            );
        }
        $removed = $existing[$index];
        array_splice($existing, $index, 1);
        $update = wp_update_post([
            'ID'           => $post_id,
            'post_content' => serialize_blocks($existing),
        ], true);
        if (is_wp_error($update)) {
            return $update;
        }
        $envelope = $this->_blocks_envelope($post_id);
        $envelope['removed'] = $removed;
        return rest_ensure_response($envelope);
    }

    /**
     * GET /airano-mcp/v1/admin/elementor/status
     *
     * Reports Elementor presence + version + Pro flag + supported post
     * types. Returns `{installed: false}` cleanly when Elementor is not
     * active, so the caller can branch without a 404.
     */
    public function handle_admin_elementor_status(WP_REST_Request $request) {
        $installed = defined('ELEMENTOR_VERSION') || class_exists('\\Elementor\\Plugin');
        if (!$installed) {
            return rest_ensure_response([
                'installed'   => false,
                'version'     => null,
                'pro'         => false,
                'post_types'  => [],
            ]);
        }
        $version = defined('ELEMENTOR_VERSION') ? ELEMENTOR_VERSION : null;
        $pro = defined('ELEMENTOR_PRO_VERSION') || class_exists('\\ElementorPro\\Plugin');

        // Elementor's own getter for editable post types — fall back
        // to the conventional defaults if the API isn't reachable.
        $post_types = ['page', 'post'];
        if (class_exists('\\Elementor\\Plugin') && method_exists('\\Elementor\\Plugin', 'instance')) {
            try {
                $plugin = \Elementor\Plugin::instance();
                if (isset($plugin->documents) && method_exists($plugin->documents, 'get_cpt_support')) {
                    $cpt = $plugin->documents->get_cpt_support();
                    if (is_array($cpt) && !empty($cpt)) {
                        $post_types = array_values(array_unique(array_map('strval', $cpt)));
                    }
                }
            } catch (Exception $e) {  // pragma: defensive
                // Fall through to defaults.
            }
        }

        return rest_ensure_response([
            'installed'  => true,
            'version'    => $version,
            'pro'        => $pro,
            'post_types' => $post_types,
        ]);
    }

    /**
     * GET /airano-mcp/v1/admin/elementor/{post_id}
     *
     * Returns the parsed _elementor_data JSON. Elementor stores the
     * data as escaped JSON in post meta; we slash-strip and decode
     * server-side so the client always sees a plain array.
     */
    public function handle_admin_elementor_get(WP_REST_Request $request) {
        $post_id = $this->_resolve_post_id($request['post_id']);
        if (is_wp_error($post_id)) {
            return $post_id;
        }
        $raw = get_post_meta($post_id, '_elementor_data', true);
        if ($raw === '' || $raw === null) {
            return rest_ensure_response([
                'post_id' => $post_id,
                'edited_with_elementor' => false,
                'data' => [],
            ]);
        }
        $json = is_string($raw) ? wp_unslash($raw) : $raw;
        $data = is_string($json) ? json_decode($json, true) : $json;
        if (!is_array($data)) {
            return new WP_Error(
                'elementor_invalid',
                __( 'Stored Elementor data is not a JSON array.', 'airano-mcp-bridge' ),
                ['status' => 500]
            );
        }
        return rest_ensure_response([
            'post_id' => $post_id,
            'edited_with_elementor' => true,
            'data' => $data,
        ]);
    }

    /**
     * POST /airano-mcp/v1/admin/elementor/{post_id}
     *
     * Body: { "data": array }   ← top-level Elementor sections array.
     * Validates shape (every node has id/elType/settings), enforces
     * the 5,000-node cap (S-14), writes via update_post_meta, and
     * fires `elementor/document/after_save` so caches and CSS clear.
     */
    public function handle_admin_elementor_set(WP_REST_Request $request) {
        $post_id = $this->_resolve_post_id($request['post_id']);
        if (is_wp_error($post_id)) {
            return $post_id;
        }
        $params = $request->get_json_params();
        if (!is_array($params) || !isset($params['data']) || !is_array($params['data'])) {
            return new WP_Error('invalid_body', __( '`data` array is required.', 'airano-mcp-bridge' ), ['status' => 400]);
        }
        $tree = $params['data'];
        $check = $this->_validate_elementor_tree($tree);
        if (is_wp_error($check)) {
            return $check;
        }
        $encoded = wp_slash(wp_json_encode($tree));
        if ($encoded === false) {
            return new WP_Error(
                'elementor_encode_failed',
                __( 'Could not encode Elementor data as JSON.', 'airano-mcp-bridge' ),
                ['status' => 500]
            );
        }
        update_post_meta($post_id, '_elementor_data', $encoded);
        update_post_meta($post_id, '_elementor_edit_mode', 'builder');

        // Fire the Elementor save hook so cache/CSS clears match the
        // editor's own write path.
        if (class_exists('\\Elementor\\Plugin') && method_exists('\\Elementor\\Plugin', 'instance')) {
            try {
                $plugin = \Elementor\Plugin::instance();
                if (isset($plugin->documents) && method_exists($plugin->documents, 'get')) {
                    $document = $plugin->documents->get($post_id);
                    if ($document && method_exists($document, 'save')) {
                        do_action('elementor/document/after_save', $document, $tree);
                    }
                }
            } catch (Exception $e) {  // pragma: defensive
                // Swallow — write succeeded; cache regen is best-effort.
            }
        }
        return rest_ensure_response([
            'post_id'   => $post_id,
            'node_count' => $this->_count_elementor_nodes($tree),
            'saved'     => true,
        ]);
    }

    /**
     * Recursive node counter (mirrors _validate_elementor_tree's walker).
     */
    private function _count_elementor_nodes(array $tree): int {
        $count = 0;
        foreach ($tree as $node) {
            if (is_array($node)) {
                $count++;
                if (!empty($node['elements']) && is_array($node['elements'])) {
                    $count += $this->_count_elementor_nodes($node['elements']);
                }
            }
        }
        return $count;
    }

    /**
     * POST /airano-mcp/v1/admin/elementor/{post_id}/regen-css
     *
     * Triggers Elementor's per-post CSS regeneration. Equivalent to
     * "Regenerate CSS" on the Elementor → Tools → Regenerate Files
     * page, scoped to one post.
     */
    public function handle_admin_elementor_render_css(WP_REST_Request $request) {
        $post_id = $this->_resolve_post_id($request['post_id']);
        if (is_wp_error($post_id)) {
            return $post_id;
        }
        if (!class_exists('\\Elementor\\Plugin')) {
            return new WP_Error(
                'elementor_missing',
                __( 'Elementor is not active on this site.', 'airano-mcp-bridge' ),
                ['status' => 409]
            );
        }
        try {
            $plugin = \Elementor\Plugin::instance();
            // Elementor exposes Files_Manager::clear_cache() on $plugin->files_manager.
            // Per-post regeneration is best handled by deleting the
            // Post_CSS file and letting the next render rebuild it.
            if (isset($plugin->files_manager) && method_exists($plugin->files_manager, 'clear_cache')) {
                $plugin->files_manager->clear_cache();
            }
            if (class_exists('\\Elementor\\Core\\Files\\CSS\\Post')) {
                $css_file = new \Elementor\Core\Files\CSS\Post($post_id);
                if (method_exists($css_file, 'update')) {
                    $css_file->update();
                }
            }
        } catch (Exception $e) {
            return new WP_Error(
                'elementor_render_failed',
                $e->getMessage(),
                ['status' => 500]
            );
        }
        return rest_ensure_response([
            'post_id' => $post_id,
            'regenerated' => true,
        ]);
    }

    /**
     * GET /airano-mcp/v1/admin/elementor/templates
     *
     * Lists saved Elementor templates (the `elementor_library` CPT).
     */
    public function handle_admin_elementor_template_list(WP_REST_Request $request) {
        if (!post_type_exists('elementor_library')) {
            return rest_ensure_response([
                'installed' => false,
                'templates' => [],
            ]);
        }
        $posts = get_posts([
            'post_type'      => 'elementor_library',
            'post_status'    => ['publish', 'private'],
            'posts_per_page' => 200,
            'orderby'        => 'title',
            'order'          => 'ASC',
        ]);
        $templates = [];
        foreach ($posts as $post) {
            $templates[] = [
                'id'    => (int) $post->ID,
                'title' => get_the_title($post),
                'type'  => get_post_meta($post->ID, '_elementor_template_type', true),
                'modified_gmt' => $post->post_modified_gmt,
            ];
        }
        return rest_ensure_response([
            'installed' => true,
            'templates' => $templates,
            'total' => count($templates),
        ]);
    }

    /**
     * POST /airano-mcp/v1/admin/elementor/templates/apply
     *
     * Body: { "template_id": int, "post_id": int }
     * Copies the template's _elementor_data into the target post,
     * subject to the same S-12 (edit_post on target) and S-14 caps as
     * elementor/set.
     */
    public function handle_admin_elementor_template_apply(WP_REST_Request $request) {
        $params = $request->get_json_params();
        if (!is_array($params)) {
            return new WP_Error('invalid_body', __( 'Expected JSON body.', 'airano-mcp-bridge' ), ['status' => 400]);
        }
        if (!isset($params['template_id']) || !is_numeric($params['template_id'])) {
            return new WP_Error('invalid_template_id', __( '`template_id` is required.', 'airano-mcp-bridge' ), ['status' => 400]);
        }
        $template_id = (int) $params['template_id'];
        $template_post = get_post($template_id);
        if (!$template_post || $template_post->post_type !== 'elementor_library') {
            return new WP_Error(
                'template_not_found',
                sprintf(
                    /* translators: %d is the template id. */
                    __( 'No Elementor template with id %d.', 'airano-mcp-bridge' ),
                    $template_id
                ),
                ['status' => 404]
            );
        }
        $target_id = $this->_resolve_post_id($params['post_id'] ?? null);
        if (is_wp_error($target_id)) {
            return $target_id;
        }
        $raw = get_post_meta($template_id, '_elementor_data', true);
        $json = is_string($raw) ? wp_unslash($raw) : $raw;
        $data = is_string($json) ? json_decode($json, true) : $json;
        if (!is_array($data)) {
            return new WP_Error(
                'template_invalid',
                __( 'Source template has no Elementor data.', 'airano-mcp-bridge' ),
                ['status' => 409]
            );
        }
        $check = $this->_validate_elementor_tree($data);
        if (is_wp_error($check)) {
            return $check;
        }
        $encoded = wp_slash(wp_json_encode($data));
        update_post_meta($target_id, '_elementor_data', $encoded);
        update_post_meta($target_id, '_elementor_edit_mode', 'builder');
        return rest_ensure_response([
            'post_id'     => $target_id,
            'template_id' => $template_id,
            'applied'     => true,
            'node_count'  => $this->_count_elementor_nodes($data),
        ]);
    }

    /**
     * POST /airano-mcp/v1/admin/classic/{post_id}/replace
     *
     * Body: { "html": string, "raw_html"?: bool }
     * Pure post_content swap for sites still on the Classic editor
     * (S-13: wp_kses_post by default).
     */
    public function handle_admin_classic_html_replace(WP_REST_Request $request) {
        $post_id = $this->_resolve_post_id($request['post_id']);
        if (is_wp_error($post_id)) {
            return $post_id;
        }
        $params = $request->get_json_params();
        if (!is_array($params) || !isset($params['html']) || !is_string($params['html'])) {
            return new WP_Error('invalid_body', __( '`html` string is required.', 'airano-mcp-bridge' ), ['status' => 400]);
        }
        $allow_raw = !empty($params['raw_html']) && current_user_can('unfiltered_html');
        $content = $allow_raw ? $params['html'] : wp_kses_post($params['html']);
        $update = wp_update_post([
            'ID'           => $post_id,
            'post_content' => $content,
        ], true);
        if (is_wp_error($update)) {
            return $update;
        }
        return rest_ensure_response([
            'post_id' => $post_id,
            'length'  => strlen($content),
            'sanitised' => !$allow_raw,
        ]);
    }

    // ================================================================
    // F.19.7 — Theme dev surface (install + activate + delete + file CRUD)
    // ================================================================
    //
    // Security ruleset (extends F.19.5 S-12…S-14):
    //
    //   * S-15 — `theme_slug` must match a key in `wp_get_themes()`.
    //            Companion rejects anything else with `theme_not_found`
    //            (404). Structural pre-check via the route regex
    //            ([A-Za-z0-9][A-Za-z0-9_\-]{0,63}); the wp_get_themes()
    //            membership check is the binding gate.
    //   * S-16 — Path canonicalisation. File routes resolve
    //            `wp-content/themes/{slug}/{path}` via realpath() and
    //            reject any result outside the slug directory. Blocks
    //            `..`, symlinks, absolute paths, null bytes.
    //   * S-17 — PHP file writes require `current_user_can('edit_themes')`
    //            AND `!defined('DISALLOW_FILE_EDIT') || !DISALLOW_FILE_EDIT`.
    //            Non-PHP files (CSS/JSON/MO/PO/JS/images/fonts) skip the
    //            DISALLOW_FILE_EDIT check but still require edit_themes.
    //   * S-18 — Per-call caps: 5 MB per file, 1000 files per list,
    //            50 MB per theme install zip.
    //   * S-19 — Optimistic concurrency. When `expected_sha256` is
    //            supplied on write, compare against the current file's
    //            sha256 and return `sha_mismatch` (409) on drift.

    /** Hard cap for theme file payloads (S-18). */
    const THEME_FILE_MAX_BYTES = 5242880; // 5 MB

    /** Hard cap for theme install zip payloads (S-18). */
    const THEME_ZIP_MAX_BYTES = 52428800; // 50 MB

    /** Hard cap for files per `theme_file_list` call (S-18). */
    const THEME_LIST_MAX_FILES = 1000;

    /**
     * S-15 — Validate a theme slug against wp_get_themes().
     *
     * @param mixed $slug Raw input (URL param).
     * @return string|WP_Error The slug on success, WP_Error on failure.
     */
    private function _validate_theme_slug($slug) {
        if (!is_string($slug) || $slug === '') {
            return new WP_Error(
                'invalid_theme_slug',
                __( 'theme_slug must be a non-empty string.', 'airano-mcp-bridge' ),
                ['status' => 400]
            );
        }
        if (!preg_match('/^[A-Za-z0-9][A-Za-z0-9_\-]{0,63}$/', $slug)) {
            return new WP_Error(
                'invalid_theme_slug',
                __( 'theme_slug must be alphanumerics + dashes + underscores (<=64 chars).', 'airano-mcp-bridge' ),
                ['status' => 400]
            );
        }
        $themes = wp_get_themes();
        if (!isset($themes[$slug])) {
            return new WP_Error(
                'theme_not_found',
                sprintf(
                    /* translators: %s is the theme slug. */
                    __( 'No theme with slug %s installed.', 'airano-mcp-bridge' ),
                    $slug
                ),
                ['status' => 404]
            );
        }
        return $slug;
    }

    /**
     * S-16 — Resolve a theme-relative path under wp-content/themes/{slug}.
     *
     * Returns the absolute path (real-resolved when the file exists,
     * structurally validated when the file may not yet exist for
     * write+create_dirs). Rejects any traversal that escapes the slug
     * directory.
     *
     * @param string $slug   Theme slug (already validated by S-15).
     * @param mixed  $path   Caller-supplied relative path.
     * @param bool   $must_exist If true (default) the resolved path must
     *                           exist; otherwise the parent directory
     *                           tree is canonicalised and the candidate
     *                           is returned for create-then-write.
     * @return array|WP_Error On success: [
     *     'absolute' => absolute path,
     *     'relative' => normalised relative path,
     *     'base'     => absolute slug directory,
     *     'exists'   => bool,
     * ].
     */
    private function _resolve_theme_file_path($slug, $path, $must_exist = true) {
        if (!is_string($path) || $path === '') {
            return new WP_Error(
                'path_invalid',
                __( 'path must be a non-empty string.', 'airano-mcp-bridge' ),
                ['status' => 400]
            );
        }
        if (strpos($path, "\0") !== false) {
            return new WP_Error(
                'path_invalid',
                __( 'path must not contain null bytes.', 'airano-mcp-bridge' ),
                ['status' => 400]
            );
        }
        // Reject backslashes (Windows-style escapes) and absolute paths.
        if (strpos($path, '\\') !== false) {
            return new WP_Error(
                'path_invalid',
                __( 'path must use forward slashes only.', 'airano-mcp-bridge' ),
                ['status' => 400]
            );
        }
        if ($path[0] === '/') {
            return new WP_Error(
                'path_invalid',
                __( 'path must be theme-relative.', 'airano-mcp-bridge' ),
                ['status' => 400]
            );
        }
        $segments = array_values(array_filter(explode('/', $path), function ($p) {
            return $p !== '';
        }));
        foreach ($segments as $seg) {
            if ($seg === '..') {
                return new WP_Error(
                    'path_invalid',
                    __( 'path must not contain `..` segments.', 'airano-mcp-bridge' ),
                    ['status' => 400]
                );
            }
        }
        if (empty($segments)) {
            return new WP_Error(
                'path_invalid',
                __( 'path must reference a file, not the theme root.', 'airano-mcp-bridge' ),
                ['status' => 400]
            );
        }
        $relative = implode('/', $segments);
        $themes_root = WP_CONTENT_DIR . '/themes';
        $base = realpath($themes_root . '/' . $slug);
        if ($base === false) {
            return new WP_Error(
                'theme_not_found',
                __( 'Theme directory does not exist on disk.', 'airano-mcp-bridge' ),
                ['status' => 404]
            );
        }
        $candidate = $base . DIRECTORY_SEPARATOR . str_replace('/', DIRECTORY_SEPARATOR, $relative);
        $real = realpath($candidate);
        if ($real !== false) {
            // Path exists — confirm it stays inside $base.
            $base_with_sep = rtrim($base, DIRECTORY_SEPARATOR) . DIRECTORY_SEPARATOR;
            if (strpos($real, $base_with_sep) !== 0 && $real !== $base) {
                return new WP_Error(
                    'path_invalid',
                    __( 'path resolves outside the theme directory.', 'airano-mcp-bridge' ),
                    ['status' => 400]
                );
            }
            return [
                'absolute' => $real,
                'relative' => $relative,
                'base'     => $base,
                'exists'   => !is_dir($real),  // we want files; mark dirs as non-existent so callers reject them
                'is_dir'   => is_dir($real),
            ];
        }
        if ($must_exist) {
            return new WP_Error(
                'file_not_found',
                __( 'No file at that path.', 'airano-mcp-bridge' ),
                ['status' => 404]
            );
        }
        // For writes the candidate may not exist yet — we must validate
        // the deepest existing ancestor and confirm it is inside $base.
        $ancestor = dirname($candidate);
        $real_ancestor = realpath($ancestor);
        while ($real_ancestor === false && $ancestor !== '.' && $ancestor !== DIRECTORY_SEPARATOR) {
            $parent = dirname($ancestor);
            if ($parent === $ancestor) {
                break;
            }
            $ancestor = $parent;
            $real_ancestor = realpath($ancestor);
        }
        if ($real_ancestor === false) {
            return new WP_Error(
                'path_invalid',
                __( 'path does not resolve to a real ancestor.', 'airano-mcp-bridge' ),
                ['status' => 400]
            );
        }
        $base_with_sep = rtrim($base, DIRECTORY_SEPARATOR) . DIRECTORY_SEPARATOR;
        if ($real_ancestor !== $base && strpos($real_ancestor, $base_with_sep) !== 0) {
            return new WP_Error(
                'path_invalid',
                __( 'path resolves outside the theme directory.', 'airano-mcp-bridge' ),
                ['status' => 400]
            );
        }
        return [
            'absolute' => $candidate,
            'relative' => $relative,
            'base'     => $base,
            'exists'   => false,
            'is_dir'   => false,
        ];
    }

    /**
     * Best-effort mime detection — uses fileinfo when available, falls
     * back to the WP-supplied list which keys off the extension.
     */
    private function _theme_file_mime($absolute) {
        if (function_exists('mime_content_type')) {
            $detected = @mime_content_type($absolute);
            if (is_string($detected) && $detected !== '') {
                return $detected;
            }
        }
        $info = wp_check_filetype(basename($absolute));
        if (!empty($info['type'])) {
            return $info['type'];
        }
        return 'application/octet-stream';
    }

    /**
     * Translate an fnmatch glob (with leading `**` support) into a
     * suffix-aware predicate compatible with PHP's fnmatch().
     *
     * `**\/*.php`   → match every .php file at any depth
     * `**\/*`       → match every file at any depth
     * `*.css`       → match .css at any depth (interpreted permissively)
     * literal       → exact relative-path match
     */
    private function _theme_glob_match($pattern, $relative) {
        if ($pattern === '' || $pattern === '**/*') {
            return true;
        }
        // fnmatch only handles a single `*` segment — strip a leading
        // `**/` so the remaining pattern matches against any tail.
        $tail = $pattern;
        if (strpos($tail, '**/') === 0) {
            $tail = substr($tail, 3);
        } elseif ($tail === '**') {
            return true;
        }
        // If `tail` has no slashes, match the basename anywhere; else
        // match the full relative path.
        if (strpos($tail, '/') === false) {
            return fnmatch($tail, basename($relative));
        }
        return fnmatch($pattern, $relative) || fnmatch($tail, $relative);
    }

    /**
     * Recursively walk a directory and append matching entries to
     * &$entries until the cap is reached. Returns the (possibly
     * truncated) entries array via reference; the boolean return value
     * indicates whether the walk was truncated.
     */
    private function _theme_walk(
        $dir,
        $base,
        $glob,
        $max_files,
        &$entries
    ) {
        $iter = @scandir($dir);
        if ($iter === false) {
            return false;
        }
        sort($iter);
        foreach ($iter as $name) {
            if ($name === '.' || $name === '..') {
                continue;
            }
            if (count($entries) >= $max_files) {
                return true;
            }
            $abs = $dir . DIRECTORY_SEPARATOR . $name;
            if (is_link($abs)) {
                // S-16 — never follow a symlink that escapes the base
                // (defensive; theme dirs rarely contain symlinks).
                $target = realpath($abs);
                if ($target === false) {
                    continue;
                }
                $base_with_sep = rtrim($base, DIRECTORY_SEPARATOR) . DIRECTORY_SEPARATOR;
                if (strpos($target, $base_with_sep) !== 0 && $target !== $base) {
                    continue;
                }
            }
            if (is_dir($abs)) {
                $truncated = $this->_theme_walk($abs, $base, $glob, $max_files, $entries);
                if ($truncated) {
                    return true;
                }
                continue;
            }
            if (!is_file($abs)) {
                continue;
            }
            $relative = ltrim(
                str_replace(DIRECTORY_SEPARATOR, '/', substr($abs, strlen($base))),
                '/'
            );
            if (!$this->_theme_glob_match($glob, $relative)) {
                continue;
            }
            $size = @filesize($abs);
            $modified = @filemtime($abs);
            $sha = @hash_file('sha256', $abs);
            $entries[] = [
                'path'        => $relative,
                'size'        => $size === false ? null : (int) $size,
                'mime'        => $this->_theme_file_mime($abs),
                'sha256'      => $sha === false ? null : $sha,
                'modified_at' => $modified === false ? null : (int) $modified,
            ];
        }
        return count($entries) >= $max_files;
    }

    /**
     * S-17 — Decide whether a write to $relative is permitted given
     * `edit_themes` (already checked by caller) plus the
     * `DISALLOW_FILE_EDIT` constant for PHP files.
     */
    private function _theme_write_allowed($relative) {
        $is_php = preg_match('/\.php$/i', $relative) === 1;
        if ($is_php && defined('DISALLOW_FILE_EDIT') && DISALLOW_FILE_EDIT) {
            return new WP_Error(
                'file_edit_disabled',
                __( 'PHP file edits are disabled (DISALLOW_FILE_EDIT) on this site.', 'airano-mcp-bridge' ),
                ['status' => 403]
            );
        }
        return true;
    }

    /**
     * Lazy-load WP_Filesystem (Direct transport). Returns the global on
     * success or a WP_Error if it could not be initialised.
     */
    private function _theme_filesystem() {
        global $wp_filesystem;
        if (!empty($wp_filesystem)) {
            return $wp_filesystem;
        }
        require_once ABSPATH . 'wp-admin/includes/file.php';
        WP_Filesystem();
        if (empty($wp_filesystem) || !is_object($wp_filesystem)) {
            return new WP_Error(
                'filesystem_unavailable',
                __( 'WP_Filesystem could not be initialised.', 'airano-mcp-bridge' ),
                ['status' => 500]
            );
        }
        return $wp_filesystem;
    }

    /**
     * POST /airano-mcp/v1/admin/themes/install
     *
     * Body: { zip_url? | zip_base64?, activate?, overwrite? }
     */
    public function handle_admin_theme_install(WP_REST_Request $request) {
        if (!current_user_can('install_themes')) {
            return new WP_Error('rest_forbidden', __( 'install_themes capability required.', 'airano-mcp-bridge' ), ['status' => 403]);
        }
        $params = $request->get_json_params();
        if (!is_array($params)) {
            return new WP_Error('invalid_body', __( 'Expected JSON body.', 'airano-mcp-bridge' ), ['status' => 400]);
        }
        $zip_url = isset($params['zip_url']) && is_string($params['zip_url']) ? $params['zip_url'] : '';
        $zip_b64 = isset($params['zip_base64']) && is_string($params['zip_base64']) ? $params['zip_base64'] : '';
        if ($zip_url === '' && $zip_b64 === '') {
            return new WP_Error('invalid_body', __( 'zip_url or zip_base64 is required.', 'airano-mcp-bridge' ), ['status' => 400]);
        }
        if ($zip_url !== '' && $zip_b64 !== '') {
            return new WP_Error('invalid_body', __( 'pass exactly one of zip_url or zip_base64.', 'airano-mcp-bridge' ), ['status' => 400]);
        }
        $activate = !empty($params['activate']);
        $overwrite = !empty($params['overwrite']);

        require_once ABSPATH . 'wp-admin/includes/file.php';
        require_once ABSPATH . 'wp-admin/includes/misc.php';
        require_once ABSPATH . 'wp-admin/includes/theme.php';
        require_once ABSPATH . 'wp-admin/includes/class-wp-upgrader.php';
        if (!class_exists('WP_Ajax_Upgrader_Skin')) {
            require_once ABSPATH . 'wp-admin/includes/class-wp-ajax-upgrader-skin.php';
        }

        $tmp_path = '';
        if ($zip_url !== '') {
            $download = download_url($zip_url);
            if (is_wp_error($download)) {
                return $download;
            }
            $tmp_path = $download;
        } else {
            // S-18 — base64 decode size cap. Strict mode rejects invalid
            // input rather than silently dropping bad characters.
            $decoded = base64_decode($zip_b64, true);
            if ($decoded === false) {
                return new WP_Error('invalid_zip', __( 'zip_base64 is not valid base64.', 'airano-mcp-bridge' ), ['status' => 400]);
            }
            if (strlen($decoded) > self::THEME_ZIP_MAX_BYTES) {
                return new WP_Error(
                    'zip_too_large',
                    sprintf(
                        /* translators: %d is the byte cap. */
                        __( 'Zip exceeds %d byte cap.', 'airano-mcp-bridge' ),
                        self::THEME_ZIP_MAX_BYTES
                    ),
                    ['status' => 413]
                );
            }
            $tmp_path = wp_tempnam('theme-install-');
            if (!$tmp_path) {
                return new WP_Error('tmpnam_failed', __( 'Could not allocate a temp file.', 'airano-mcp-bridge' ), ['status' => 500]);
            }
            $fs = $this->_theme_filesystem();
            if (is_wp_error($fs)) {
                @unlink($tmp_path);
                return $fs;
            }
            if (!$fs->put_contents($tmp_path, $decoded, FS_CHMOD_FILE)) {
                @unlink($tmp_path);
                return new WP_Error('write_failed', __( 'Could not write temp zip.', 'airano-mcp-bridge' ), ['status' => 500]);
            }
        }

        $skin = new WP_Ajax_Upgrader_Skin();
        $upgrader = new Theme_Upgrader($skin);
        $result = $upgrader->install($tmp_path, [
            'overwrite_package' => (bool) $overwrite,
        ]);
        @unlink($tmp_path);

        if (is_wp_error($result)) {
            return $result;
        }
        if ($result === false) {
            $errors = $skin->get_errors();
            $msg = is_object($errors) && method_exists($errors, 'get_error_message')
                ? $errors->get_error_message()
                : __( 'Theme install failed.', 'airano-mcp-bridge' );
            return new WP_Error('install_failed', $msg ?: __( 'Theme install failed.', 'airano-mcp-bridge' ), ['status' => 500]);
        }

        $info = $upgrader->theme_info();
        $slug = '';
        if ($info && is_object($info) && method_exists($info, 'get_stylesheet')) {
            $slug = (string) $info->get_stylesheet();
        }

        $activated = false;
        if ($activate && $slug !== '') {
            if (!current_user_can('switch_themes')) {
                return new WP_Error('rest_forbidden', __( 'switch_themes capability required to activate.', 'airano-mcp-bridge' ), ['status' => 403]);
            }
            switch_theme($slug);
            $activated = (string) get_option('stylesheet') === $slug;
        }

        return rest_ensure_response([
            'installed' => true,
            'slug'      => $slug,
            'activated' => $activated,
        ]);
    }

    /**
     * POST /airano-mcp/v1/admin/themes/{slug}/activate
     */
    public function handle_admin_theme_activate(WP_REST_Request $request) {
        if (!current_user_can('switch_themes')) {
            return new WP_Error('rest_forbidden', __( 'switch_themes capability required.', 'airano-mcp-bridge' ), ['status' => 403]);
        }
        $slug = $this->_validate_theme_slug($request['slug']);
        if (is_wp_error($slug)) {
            return $slug;
        }
        switch_theme($slug);
        $stylesheet = (string) get_option('stylesheet');
        $template = (string) get_option('template');
        if ($stylesheet !== $slug) {
            return new WP_Error(
                'activation_failed',
                __( 'Activation did not stick — check the theme has a valid style.css header.', 'airano-mcp-bridge' ),
                ['status' => 500]
            );
        }
        return rest_ensure_response([
            'activated'  => true,
            'stylesheet' => $stylesheet,
            'template'   => $template,
        ]);
    }

    /**
     * DELETE /airano-mcp/v1/admin/themes/{slug}
     */
    public function handle_admin_theme_delete(WP_REST_Request $request) {
        if (!current_user_can('delete_themes')) {
            return new WP_Error('rest_forbidden', __( 'delete_themes capability required.', 'airano-mcp-bridge' ), ['status' => 403]);
        }
        $slug = $this->_validate_theme_slug($request['slug']);
        if (is_wp_error($slug)) {
            return $slug;
        }
        if ($slug === (string) get_option('stylesheet')) {
            return new WP_Error('theme_active', __( 'Refusing to delete the active theme.', 'airano-mcp-bridge' ), ['status' => 409]);
        }
        if ($slug === (string) get_option('template')) {
            return new WP_Error('theme_active', __( 'Refusing to delete the active parent theme.', 'airano-mcp-bridge' ), ['status' => 409]);
        }
        require_once ABSPATH . 'wp-admin/includes/file.php';
        require_once ABSPATH . 'wp-admin/includes/theme.php';
        $deleted = delete_theme($slug);
        if (is_wp_error($deleted)) {
            return $deleted;
        }
        if ($deleted === false) {
            return new WP_Error('delete_failed', __( 'Theme delete failed.', 'airano-mcp-bridge' ), ['status' => 500]);
        }
        return rest_ensure_response([
            'deleted' => true,
            'slug'    => $slug,
        ]);
    }

    /**
     * GET /airano-mcp/v1/admin/themes/files/{slug}
     */
    public function handle_admin_theme_file_list(WP_REST_Request $request) {
        $slug = $this->_validate_theme_slug($request['slug']);
        if (is_wp_error($slug)) {
            return $slug;
        }
        $glob = $request->get_param('glob');
        if (!is_string($glob) || $glob === '') {
            $glob = '**/*';
        }
        $max_files = (int) $request->get_param('max_files');
        if ($max_files <= 0) {
            $max_files = self::THEME_LIST_MAX_FILES;
        }
        if ($max_files > self::THEME_LIST_MAX_FILES) {
            $max_files = self::THEME_LIST_MAX_FILES;
        }
        $base = realpath(WP_CONTENT_DIR . '/themes/' . $slug);
        if ($base === false) {
            return new WP_Error('theme_not_found', __( 'Theme directory missing.', 'airano-mcp-bridge' ), ['status' => 404]);
        }
        $entries = [];
        $truncated = $this->_theme_walk($base, $base, $glob, $max_files, $entries);
        return rest_ensure_response([
            'theme_slug' => $slug,
            'count'      => count($entries),
            'truncated'  => (bool) $truncated,
            'glob'       => $glob,
            'files'      => $entries,
        ]);
    }

    /**
     * GET /airano-mcp/v1/admin/themes/files/{slug}/{path}
     */
    public function handle_admin_theme_file_read(WP_REST_Request $request) {
        $slug = $this->_validate_theme_slug($request['slug']);
        if (is_wp_error($slug)) {
            return $slug;
        }
        $resolved = $this->_resolve_theme_file_path($slug, $request['path'], true);
        if (is_wp_error($resolved)) {
            return $resolved;
        }
        if (!empty($resolved['is_dir'])) {
            return new WP_Error('path_invalid', __( 'path refers to a directory.', 'airano-mcp-bridge' ), ['status' => 400]);
        }
        $absolute = $resolved['absolute'];
        $size = filesize($absolute);
        if ($size === false) {
            return new WP_Error('read_failed', __( 'Could not stat file.', 'airano-mcp-bridge' ), ['status' => 500]);
        }
        if ($size > self::THEME_FILE_MAX_BYTES) {
            return new WP_Error(
                'file_too_large',
                sprintf(
                    /* translators: %d is the byte cap. */
                    __( 'File exceeds %d byte cap.', 'airano-mcp-bridge' ),
                    self::THEME_FILE_MAX_BYTES
                ),
                ['status' => 413]
            );
        }
        $body = file_get_contents($absolute);
        if ($body === false) {
            return new WP_Error('read_failed', __( 'Could not read file.', 'airano-mcp-bridge' ), ['status' => 500]);
        }
        $sha = hash('sha256', $body);
        $modified = filemtime($absolute);
        return rest_ensure_response([
            'theme_slug'      => $slug,
            'path'            => $resolved['relative'],
            'size'            => (int) $size,
            'mime'            => $this->_theme_file_mime($absolute),
            'sha256'          => $sha,
            'modified_at'     => $modified === false ? null : (int) $modified,
            'content_base64'  => base64_encode($body),
        ]);
    }

    /**
     * PUT /airano-mcp/v1/admin/themes/files/{slug}/{path}
     */
    public function handle_admin_theme_file_write(WP_REST_Request $request) {
        if (!current_user_can('edit_themes')) {
            return new WP_Error('rest_forbidden', __( 'edit_themes capability required.', 'airano-mcp-bridge' ), ['status' => 403]);
        }
        $slug = $this->_validate_theme_slug($request['slug']);
        if (is_wp_error($slug)) {
            return $slug;
        }
        $params = $request->get_json_params();
        if (!is_array($params) || !isset($params['content_base64']) || !is_string($params['content_base64'])) {
            return new WP_Error('invalid_body', __( 'content_base64 string is required.', 'airano-mcp-bridge' ), ['status' => 400]);
        }
        $create_dirs = !array_key_exists('create_dirs', $params) || !empty($params['create_dirs']);
        $resolved = $this->_resolve_theme_file_path($slug, $request['path'], false);
        if (is_wp_error($resolved)) {
            return $resolved;
        }
        if (!empty($resolved['is_dir'])) {
            return new WP_Error('path_invalid', __( 'path refers to a directory.', 'airano-mcp-bridge' ), ['status' => 400]);
        }
        $allowed = $this->_theme_write_allowed($resolved['relative']);
        if (is_wp_error($allowed)) {
            return $allowed;
        }
        $decoded = base64_decode($params['content_base64'], true);
        if ($decoded === false) {
            return new WP_Error('invalid_body', __( 'content_base64 is not valid base64.', 'airano-mcp-bridge' ), ['status' => 400]);
        }
        if (strlen($decoded) > self::THEME_FILE_MAX_BYTES) {
            return new WP_Error(
                'file_too_large',
                sprintf(
                    /* translators: %d is the byte cap. */
                    __( 'Decoded body exceeds %d byte cap.', 'airano-mcp-bridge' ),
                    self::THEME_FILE_MAX_BYTES
                ),
                ['status' => 413]
            );
        }
        // S-19 — optimistic concurrency.
        if (isset($params['expected_sha256']) && is_string($params['expected_sha256']) && $params['expected_sha256'] !== '') {
            $expected = strtolower($params['expected_sha256']);
            if (!preg_match('/^[0-9a-f]{64}$/', $expected)) {
                return new WP_Error('invalid_body', __( 'expected_sha256 must be 64 hex chars.', 'airano-mcp-bridge' ), ['status' => 400]);
            }
            if ($resolved['exists']) {
                $current = @hash_file('sha256', $resolved['absolute']);
                if ($current === false || $current !== $expected) {
                    return new WP_Error(
                        'sha_mismatch',
                        __( 'On-disk sha256 does not match expected_sha256.', 'airano-mcp-bridge' ),
                        ['status' => 409]
                    );
                }
            } else {
                // Caller expected an existing file but none exists.
                return new WP_Error(
                    'sha_mismatch',
                    __( 'expected_sha256 supplied but file does not exist.', 'airano-mcp-bridge' ),
                    ['status' => 409]
                );
            }
        }
        // Create parent directories if requested.
        $absolute = $resolved['absolute'];
        $parent = dirname($absolute);
        if (!is_dir($parent)) {
            if (!$create_dirs) {
                return new WP_Error('parent_missing', __( 'Parent directory does not exist; pass create_dirs=true to auto-create.', 'airano-mcp-bridge' ), ['status' => 409]);
            }
            if (!wp_mkdir_p($parent)) {
                return new WP_Error('mkdir_failed', __( 'Could not create parent directories.', 'airano-mcp-bridge' ), ['status' => 500]);
            }
        }
        $fs = $this->_theme_filesystem();
        if (is_wp_error($fs)) {
            return $fs;
        }
        if (!$fs->put_contents($absolute, $decoded, FS_CHMOD_FILE)) {
            return new WP_Error('write_failed', __( 'Theme file write failed.', 'airano-mcp-bridge' ), ['status' => 500]);
        }
        $new_sha = hash('sha256', $decoded);
        $modified = @filemtime($absolute);
        return rest_ensure_response([
            'theme_slug'  => $slug,
            'path'        => $resolved['relative'],
            'size'        => strlen($decoded),
            'sha256'      => $new_sha,
            'modified_at' => $modified === false ? null : (int) $modified,
            'created'     => !$resolved['exists'],
        ]);
    }

    /**
     * DELETE /airano-mcp/v1/admin/themes/files/{slug}/{path}
     */
    public function handle_admin_theme_file_delete(WP_REST_Request $request) {
        if (!current_user_can('edit_themes')) {
            return new WP_Error('rest_forbidden', __( 'edit_themes capability required.', 'airano-mcp-bridge' ), ['status' => 403]);
        }
        $slug = $this->_validate_theme_slug($request['slug']);
        if (is_wp_error($slug)) {
            return $slug;
        }
        $resolved = $this->_resolve_theme_file_path($slug, $request['path'], true);
        if (is_wp_error($resolved)) {
            return $resolved;
        }
        if (!empty($resolved['is_dir'])) {
            return new WP_Error('path_invalid', __( 'path refers to a directory; refusing to recurse.', 'airano-mcp-bridge' ), ['status' => 400]);
        }
        // Refuse to delete style.css of the active theme — it would
        // break the front-end immediately.
        $is_active = $slug === (string) get_option('stylesheet');
        if ($is_active && strtolower($resolved['relative']) === 'style.css') {
            return new WP_Error('refused', __( 'Refusing to delete style.css of the active theme.', 'airano-mcp-bridge' ), ['status' => 409]);
        }
        $allowed = $this->_theme_write_allowed($resolved['relative']);
        if (is_wp_error($allowed)) {
            return $allowed;
        }
        if (!@unlink($resolved['absolute'])) {
            return new WP_Error('delete_failed', __( 'Theme file delete failed.', 'airano-mcp-bridge' ), ['status' => 500]);
        }
        return rest_ensure_response([
            'deleted'    => true,
            'theme_slug' => $slug,
            'path'       => $resolved['relative'],
        ]);
    }

    // ================================================================
    // F.19.2.1 — Plugin write management
    // ================================================================
    //
    // Security ruleset (extends F.19.7's S-15..S-19):
    //
    //   * S-15 (reused) — slug must match a key in get_plugins() for
    //                     activate/deactivate/update/delete.
    //   * S-18 (reused) — 50 MB cap on install zip payloads.
    //   * S-20 — refuses to deactivate/delete the airano-mcp-bridge
    //            companion itself. Doing so would brick the MCP
    //            connection; operators must use the WP-Admin Plugins
    //            page instead.
    //   * S-21 — refuses to deactivate/delete plugins whose `Required`
    //            header is `yes` (must-use plugins shipped by some
    //            managed hosts).

    /** Hard cap for plugin install zip payloads (S-18, mirrors theme zip). */
    const PLUGIN_ZIP_MAX_BYTES = 52428800; // 50 MB

    /** Slug of the companion itself — never deactivate/delete via this surface (S-20). */
    const COMPANION_SLUG = 'airano-mcp-bridge';

    /**
     * Resolve a plugin slug to its plugin_file (e.g. "akismet/akismet.php").
     *
     * S-15 — also acts as the wp_get_themes() equivalent: a slug that
     * doesn't appear in get_plugins() is rejected with `plugin_not_found`.
     *
     * @param mixed $slug Raw slug from URL/body.
     * @return string|WP_Error plugin_file on success, WP_Error otherwise.
     */
    private function _resolve_plugin_file($slug) {
        if (!is_string($slug) || $slug === '' || !preg_match('/^[A-Za-z0-9][A-Za-z0-9_\-]{0,63}$/', $slug)) {
            return new WP_Error(
                'invalid_plugin_slug',
                __( 'slug must be alphanumerics + dashes + underscores (<=64 chars).', 'airano-mcp-bridge' ),
                ['status' => 400]
            );
        }
        if (!function_exists('get_plugins')) {
            require_once ABSPATH . 'wp-admin/includes/plugin.php';
        }
        $plugins = get_plugins();
        // Two valid forms: dir/main.php (most common) or main.php (rare,
        // for single-file plugins like Hello Dolly).
        foreach ($plugins as $file => $_meta) {
            $file_slug = (dirname($file) === '.') ? basename($file, '.php') : dirname($file);
            if ($file_slug === $slug) {
                return $file;
            }
        }
        return new WP_Error(
            'plugin_not_found',
            sprintf(
                /* translators: %s is the plugin slug. */
                __( 'No installed plugin with slug %s.', 'airano-mcp-bridge' ),
                $slug
            ),
            ['status' => 404]
        );
    }

    /**
     * S-21 — fetch plugin meta and refuse if `Required: yes`.
     * Returns true on allow, WP_Error on refusal.
     */
    private function _plugin_not_required($plugin_file) {
        $path = WP_PLUGIN_DIR . '/' . $plugin_file;
        if (!is_file($path)) {
            return true;  // can't read; let downstream handlers fail with the real reason
        }
        $data = get_plugin_data($path, false, false);
        if (!empty($data['Required']) && strtolower((string) $data['Required']) === 'yes') {
            return new WP_Error(
                'plugin_required',
                __( 'Plugin marked Required by this site; refusing to deactivate or delete.', 'airano-mcp-bridge' ),
                ['status' => 409]
            );
        }
        return true;
    }

    /**
     * POST /airano-mcp/v1/admin/plugins/install
     *
     * Body shape A (slug install — install_plugins, install tier on MCPHub):
     *   { "slug": "akismet", "activate"?: bool }
     *
     * Body shape B (zip install — install_plugins, admin tier on MCPHub):
     *   { "zip_url"?: str | "zip_base64"?: str, "activate"?: bool, "overwrite"?: bool }
     */
    public function handle_admin_plugin_install(WP_REST_Request $request) {
        if (!current_user_can('install_plugins')) {
            return new WP_Error('rest_forbidden', __( 'install_plugins capability required.', 'airano-mcp-bridge' ), ['status' => 403]);
        }
        $params = $request->get_json_params();
        if (!is_array($params)) {
            return new WP_Error('invalid_body', __( 'Expected JSON body.', 'airano-mcp-bridge' ), ['status' => 400]);
        }

        $slug = isset($params['slug']) && is_string($params['slug']) ? $params['slug'] : '';
        $zip_url = isset($params['zip_url']) && is_string($params['zip_url']) ? $params['zip_url'] : '';
        $zip_b64 = isset($params['zip_base64']) && is_string($params['zip_base64']) ? $params['zip_base64'] : '';
        $modes = (int) ($slug !== '') + (int) ($zip_url !== '') + (int) ($zip_b64 !== '');
        if ($modes !== 1) {
            return new WP_Error(
                'invalid_body',
                __( 'pass exactly one of slug, zip_url, or zip_base64.', 'airano-mcp-bridge' ),
                ['status' => 400]
            );
        }
        $activate = !empty($params['activate']);
        $overwrite = !empty($params['overwrite']);

        require_once ABSPATH . 'wp-admin/includes/file.php';
        require_once ABSPATH . 'wp-admin/includes/misc.php';
        require_once ABSPATH . 'wp-admin/includes/plugin.php';
        require_once ABSPATH . 'wp-admin/includes/plugin-install.php';
        require_once ABSPATH . 'wp-admin/includes/class-wp-upgrader.php';
        if (!class_exists('WP_Ajax_Upgrader_Skin')) {
            require_once ABSPATH . 'wp-admin/includes/class-wp-ajax-upgrader-skin.php';
        }

        $tmp_path = '';

        if ($slug !== '') {
            // Slug install — resolve the wp.org package URL and download.
            if (!preg_match('/^[A-Za-z0-9][A-Za-z0-9_\-]{0,63}$/', $slug)) {
                return new WP_Error('invalid_plugin_slug', __( 'invalid slug.', 'airano-mcp-bridge' ), ['status' => 400]);
            }
            $info = plugins_api('plugin_information', [
                'slug'   => $slug,
                'fields' => ['short_description' => false, 'sections' => false, 'icons' => false],
            ]);
            if (is_wp_error($info)) {
                return $info;
            }
            if (empty($info->download_link)) {
                return new WP_Error(
                    'wporg_no_download',
                    __( 'wp.org returned no download link for that slug.', 'airano-mcp-bridge' ),
                    ['status' => 502]
                );
            }
            $download = download_url($info->download_link);
            if (is_wp_error($download)) {
                return $download;
            }
            $tmp_path = $download;
        } elseif ($zip_url !== '') {
            $download = download_url($zip_url);
            if (is_wp_error($download)) {
                return $download;
            }
            $tmp_path = $download;
        } else {
            // base64 install
            $decoded = base64_decode($zip_b64, true);
            if ($decoded === false) {
                return new WP_Error('invalid_zip', __( 'zip_base64 is not valid base64.', 'airano-mcp-bridge' ), ['status' => 400]);
            }
            if (strlen($decoded) > self::PLUGIN_ZIP_MAX_BYTES) {
                return new WP_Error(
                    'zip_too_large',
                    sprintf(
                        /* translators: %d is the byte cap. */
                        __( 'Zip exceeds %d byte cap.', 'airano-mcp-bridge' ),
                        self::PLUGIN_ZIP_MAX_BYTES
                    ),
                    ['status' => 413]
                );
            }
            $tmp_path = wp_tempnam('plugin-install-');
            if (!$tmp_path) {
                return new WP_Error('tmpnam_failed', __( 'Could not allocate a temp file.', 'airano-mcp-bridge' ), ['status' => 500]);
            }
            $fs = $this->_theme_filesystem();  // reuse helper from F.19.7
            if (is_wp_error($fs)) {
                @unlink($tmp_path);
                return $fs;
            }
            if (!$fs->put_contents($tmp_path, $decoded, FS_CHMOD_FILE)) {
                @unlink($tmp_path);
                return new WP_Error('write_failed', __( 'Could not write temp zip.', 'airano-mcp-bridge' ), ['status' => 500]);
            }
        }

        $skin = new WP_Ajax_Upgrader_Skin();
        $upgrader = new Plugin_Upgrader($skin);
        $result = $upgrader->install($tmp_path, [
            'overwrite_package' => (bool) $overwrite,
        ]);
        @unlink($tmp_path);

        if (is_wp_error($result)) {
            return $result;
        }
        if ($result === false) {
            $errors = $skin->get_errors();
            $msg = is_object($errors) && method_exists($errors, 'get_error_message')
                ? $errors->get_error_message()
                : __( 'Plugin install failed.', 'airano-mcp-bridge' );
            return new WP_Error('install_failed', $msg ?: __( 'Plugin install failed.', 'airano-mcp-bridge' ), ['status' => 500]);
        }

        // Resolve the installed plugin file so callers can chain.
        $installed_file = (string) $upgrader->plugin_info();
        $installed_slug = $installed_file !== ''
            ? ((dirname($installed_file) === '.') ? basename($installed_file, '.php') : dirname($installed_file))
            : '';

        $activated = false;
        if ($activate && $installed_file !== '') {
            if (!current_user_can('activate_plugins')) {
                return new WP_Error('rest_forbidden', __( 'activate_plugins capability required to activate.', 'airano-mcp-bridge' ), ['status' => 403]);
            }
            $err = activate_plugin($installed_file);
            $activated = !is_wp_error($err);
        }

        return rest_ensure_response([
            'installed'   => true,
            'slug'        => $installed_slug,
            'plugin_file' => $installed_file,
            'activated'   => $activated,
        ]);
    }

    /**
     * POST /airano-mcp/v1/admin/plugins/{slug}/activate
     */
    public function handle_admin_plugin_activate(WP_REST_Request $request) {
        if (!current_user_can('activate_plugins')) {
            return new WP_Error('rest_forbidden', __( 'activate_plugins capability required.', 'airano-mcp-bridge' ), ['status' => 403]);
        }
        $plugin_file = $this->_resolve_plugin_file($request['slug']);
        if (is_wp_error($plugin_file)) {
            return $plugin_file;
        }
        $params = $request->get_json_params();
        $network_wide = is_array($params) && !empty($params['network_wide']);
        if ($network_wide && is_multisite() && !current_user_can('manage_network_plugins')) {
            return new WP_Error('rest_forbidden', __( 'manage_network_plugins required for network-wide activation.', 'airano-mcp-bridge' ), ['status' => 403]);
        }
        if (!function_exists('activate_plugin')) {
            require_once ABSPATH . 'wp-admin/includes/plugin.php';
        }
        $err = activate_plugin($plugin_file, '', $network_wide);
        if (is_wp_error($err)) {
            return $err;
        }
        return rest_ensure_response([
            'activated'    => is_plugin_active($plugin_file) || ($network_wide && is_plugin_active_for_network($plugin_file)),
            'slug'         => (string) $request['slug'],
            'plugin_file'  => $plugin_file,
            'network_wide' => (bool) $network_wide,
        ]);
    }

    /**
     * POST /airano-mcp/v1/admin/plugins/{slug}/deactivate
     */
    public function handle_admin_plugin_deactivate(WP_REST_Request $request) {
        if (!current_user_can('activate_plugins')) {
            return new WP_Error('rest_forbidden', __( 'activate_plugins capability required.', 'airano-mcp-bridge' ), ['status' => 403]);
        }
        $slug = (string) $request['slug'];
        // S-20: guard against deactivating the companion itself.
        if ($slug === self::COMPANION_SLUG) {
            return new WP_Error(
                'companion_self',
                __( 'Refusing to deactivate the Airano MCP Bridge companion via its own route — would brick the MCP connection. Use WP-Admin → Plugins instead.', 'airano-mcp-bridge' ),
                ['status' => 409]
            );
        }
        $plugin_file = $this->_resolve_plugin_file($slug);
        if (is_wp_error($plugin_file)) {
            return $plugin_file;
        }
        // S-21: refuse if header marks this plugin Required.
        $req_check = $this->_plugin_not_required($plugin_file);
        if (is_wp_error($req_check)) {
            return $req_check;
        }
        $params = $request->get_json_params();
        $network_wide = is_array($params) && !empty($params['network_wide']);
        if (!function_exists('deactivate_plugins')) {
            require_once ABSPATH . 'wp-admin/includes/plugin.php';
        }
        deactivate_plugins([$plugin_file], false, $network_wide);
        return rest_ensure_response([
            'deactivated'  => !is_plugin_active($plugin_file),
            'slug'         => $slug,
            'plugin_file'  => $plugin_file,
            'network_wide' => (bool) $network_wide,
        ]);
    }

    /**
     * POST /airano-mcp/v1/admin/plugins/{slug}/update
     */
    public function handle_admin_plugin_update(WP_REST_Request $request) {
        if (!current_user_can('update_plugins')) {
            return new WP_Error('rest_forbidden', __( 'update_plugins capability required.', 'airano-mcp-bridge' ), ['status' => 403]);
        }
        $plugin_file = $this->_resolve_plugin_file($request['slug']);
        if (is_wp_error($plugin_file)) {
            return $plugin_file;
        }
        require_once ABSPATH . 'wp-admin/includes/file.php';
        require_once ABSPATH . 'wp-admin/includes/plugin.php';
        require_once ABSPATH . 'wp-admin/includes/class-wp-upgrader.php';
        if (!class_exists('WP_Ajax_Upgrader_Skin')) {
            require_once ABSPATH . 'wp-admin/includes/class-wp-ajax-upgrader-skin.php';
        }

        // Refresh the cached update_plugins transient so the upgrader
        // sees the latest available version.
        wp_update_plugins();
        $update_data = get_site_transient('update_plugins');
        $has_update = isset($update_data->response[$plugin_file]);

        if (!$has_update) {
            return rest_ensure_response([
                'up_to_date'  => true,
                'updated'     => false,
                'slug'        => (string) $request['slug'],
                'plugin_file' => $plugin_file,
            ]);
        }

        $skin = new WP_Ajax_Upgrader_Skin();
        $upgrader = new Plugin_Upgrader($skin);
        $result = $upgrader->upgrade($plugin_file);
        if (is_wp_error($result)) {
            return $result;
        }
        if ($result === false) {
            $errors = $skin->get_errors();
            $msg = is_object($errors) && method_exists($errors, 'get_error_message')
                ? $errors->get_error_message()
                : __( 'Plugin update failed.', 'airano-mcp-bridge' );
            return new WP_Error('update_failed', $msg ?: __( 'Plugin update failed.', 'airano-mcp-bridge' ), ['status' => 500]);
        }

        // After upgrade, re-read the plugin meta for the new version.
        $new_data = get_plugin_data(WP_PLUGIN_DIR . '/' . $plugin_file, false, false);
        return rest_ensure_response([
            'up_to_date'  => false,
            'updated'     => true,
            'slug'        => (string) $request['slug'],
            'plugin_file' => $plugin_file,
            'new_version' => isset($new_data['Version']) ? (string) $new_data['Version'] : null,
        ]);
    }

    /**
     * DELETE /airano-mcp/v1/admin/plugins/{slug}
     */
    // ================================================================
    // F.19.6.A — Site config (identity + reading + permalinks)
    // ================================================================

    /**
     * Validate that an attachment id refers to an existing media item.
     * 0 is valid (means "clear"). Returns true on allow, WP_Error otherwise.
     */
    private function _validate_attachment_id($id, $field) {
        if (!is_int($id) || $id < 0) {
            return new WP_Error(
                'invalid_attachment',
                sprintf(
                    /* translators: %s is the field name. */
                    __( '%s must be a non-negative integer.', 'airano-mcp-bridge' ),
                    $field
                ),
                ['status' => 400]
            );
        }
        if ($id === 0) {
            return true;
        }
        $post = get_post($id);
        if (!$post || $post->post_type !== 'attachment') {
            return new WP_Error(
                'invalid_attachment',
                sprintf(
                    /* translators: %d is the attachment id. */
                    __( 'No attachment with id %d.', 'airano-mcp-bridge' ),
                    $id
                ),
                ['status' => 404]
            );
        }
        return true;
    }

    /**
     * Validate a page id refers to a published Page (or 0 to clear).
     */
    private function _validate_page_id($id, $field) {
        if (!is_int($id) || $id < 0) {
            return new WP_Error(
                'invalid_page',
                sprintf(
                    __( '%s must be a non-negative integer.', 'airano-mcp-bridge' ),
                    $field
                ),
                ['status' => 400]
            );
        }
        if ($id === 0) {
            return true;
        }
        $post = get_post($id);
        if (!$post || $post->post_type !== 'page' || $post->post_status !== 'publish') {
            return new WP_Error(
                'invalid_page',
                sprintf(
                    __( '%s must reference a published Page (got id %d).', 'airano-mcp-bridge' ),
                    $field,
                    $id
                ),
                ['status' => 400]
            );
        }
        return true;
    }

    /**
     * GET /airano-mcp/v1/admin/site/identity
     */
    public function handle_admin_site_identity_get(WP_REST_Request $request) {
        return rest_ensure_response([
            'title'          => (string) get_option('blogname', ''),
            'tagline'        => (string) get_option('blogdescription', ''),
            'site_icon'      => (int) get_option('site_icon', 0),
            'custom_logo'    => (int) get_theme_mod('custom_logo', 0),
            'admin_email'    => (string) get_option('admin_email', ''),
            'blog_charset'   => (string) get_option('blog_charset', 'UTF-8'),
            'wp_version'     => function_exists('get_bloginfo') ? (string) get_bloginfo('version') : null,
            'language'       => (string) get_option('WPLANG', get_locale()),
            'timezone'       => (string) get_option('timezone_string', ''),
            'siteurl'        => (string) get_option('siteurl', ''),
            'home'           => (string) get_option('home', ''),
        ]);
    }

    /**
     * POST /airano-mcp/v1/admin/site/identity
     * Body: { title?, tagline?, site_icon_id?, custom_logo_id? }
     */
    public function handle_admin_site_identity_set(WP_REST_Request $request) {
        $params = $request->get_json_params();
        if (!is_array($params) || empty($params)) {
            return new WP_Error('invalid_body', __( 'Expected a non-empty JSON body.', 'airano-mcp-bridge' ), ['status' => 400]);
        }
        $changed = [];
        if (array_key_exists('title', $params)) {
            if (!is_string($params['title'])) {
                return new WP_Error('invalid_title', __( 'title must be a string.', 'airano-mcp-bridge' ), ['status' => 400]);
            }
            update_option('blogname', sanitize_text_field($params['title']));
            $changed[] = 'title';
        }
        if (array_key_exists('tagline', $params)) {
            if (!is_string($params['tagline'])) {
                return new WP_Error('invalid_tagline', __( 'tagline must be a string.', 'airano-mcp-bridge' ), ['status' => 400]);
            }
            update_option('blogdescription', sanitize_text_field($params['tagline']));
            $changed[] = 'tagline';
        }
        if (array_key_exists('site_icon_id', $params)) {
            $check = $this->_validate_attachment_id($params['site_icon_id'], 'site_icon_id');
            if (is_wp_error($check)) {
                return $check;
            }
            update_option('site_icon', (int) $params['site_icon_id']);
            $changed[] = 'site_icon';
        }
        if (array_key_exists('custom_logo_id', $params)) {
            $check = $this->_validate_attachment_id($params['custom_logo_id'], 'custom_logo_id');
            if (is_wp_error($check)) {
                return $check;
            }
            $logo_id = (int) $params['custom_logo_id'];
            if ($logo_id === 0) {
                remove_theme_mod('custom_logo');
            } else {
                set_theme_mod('custom_logo', $logo_id);
            }
            $changed[] = 'custom_logo';
        }
        if (empty($changed)) {
            return new WP_Error('invalid_body', __( 'No supported fields supplied.', 'airano-mcp-bridge' ), ['status' => 400]);
        }
        return rest_ensure_response([
            'updated' => $changed,
            'identity' => [
                'title'       => (string) get_option('blogname', ''),
                'tagline'     => (string) get_option('blogdescription', ''),
                'site_icon'   => (int) get_option('site_icon', 0),
                'custom_logo' => (int) get_theme_mod('custom_logo', 0),
            ],
        ]);
    }

    /**
     * GET /airano-mcp/v1/admin/site/reading
     */
    public function handle_admin_site_reading_get(WP_REST_Request $request) {
        return rest_ensure_response([
            'show_on_front'   => (string) get_option('show_on_front', 'posts'),
            'page_on_front'   => (int) get_option('page_on_front', 0),
            'page_for_posts'  => (int) get_option('page_for_posts', 0),
            'posts_per_page'  => (int) get_option('posts_per_page', 10),
            'posts_per_rss'   => (int) get_option('posts_per_rss', 10),
            'blog_public'     => ((int) get_option('blog_public', 1)) === 1,
        ]);
    }

    /**
     * POST /airano-mcp/v1/admin/site/reading
     */
    public function handle_admin_site_reading_set(WP_REST_Request $request) {
        $params = $request->get_json_params();
        if (!is_array($params) || empty($params)) {
            return new WP_Error('invalid_body', __( 'Expected a non-empty JSON body.', 'airano-mcp-bridge' ), ['status' => 400]);
        }
        $changed = [];
        if (array_key_exists('show_on_front', $params)) {
            if (!in_array($params['show_on_front'], ['posts', 'page'], true)) {
                return new WP_Error(
                    'invalid_show_on_front',
                    __( "show_on_front must be 'posts' or 'page'.", 'airano-mcp-bridge' ),
                    ['status' => 400]
                );
            }
            update_option('show_on_front', $params['show_on_front']);
            $changed[] = 'show_on_front';
        }
        if (array_key_exists('page_on_front', $params)) {
            $check = $this->_validate_page_id($params['page_on_front'], 'page_on_front');
            if (is_wp_error($check)) {
                return $check;
            }
            update_option('page_on_front', (int) $params['page_on_front']);
            $changed[] = 'page_on_front';
        }
        if (array_key_exists('page_for_posts', $params)) {
            $check = $this->_validate_page_id($params['page_for_posts'], 'page_for_posts');
            if (is_wp_error($check)) {
                return $check;
            }
            update_option('page_for_posts', (int) $params['page_for_posts']);
            $changed[] = 'page_for_posts';
        }
        if (array_key_exists('posts_per_page', $params)) {
            if (!is_int($params['posts_per_page']) || $params['posts_per_page'] < 1 || $params['posts_per_page'] > 100) {
                return new WP_Error(
                    'invalid_posts_per_page',
                    __( 'posts_per_page must be an integer between 1 and 100.', 'airano-mcp-bridge' ),
                    ['status' => 400]
                );
            }
            update_option('posts_per_page', (int) $params['posts_per_page']);
            $changed[] = 'posts_per_page';
        }
        if (array_key_exists('posts_per_rss', $params)) {
            if (!is_int($params['posts_per_rss']) || $params['posts_per_rss'] < 1 || $params['posts_per_rss'] > 100) {
                return new WP_Error(
                    'invalid_posts_per_rss',
                    __( 'posts_per_rss must be an integer between 1 and 100.', 'airano-mcp-bridge' ),
                    ['status' => 400]
                );
            }
            update_option('posts_per_rss', (int) $params['posts_per_rss']);
            $changed[] = 'posts_per_rss';
        }
        if (array_key_exists('blog_public', $params)) {
            if (!is_bool($params['blog_public'])) {
                return new WP_Error(
                    'invalid_blog_public',
                    __( 'blog_public must be a boolean.', 'airano-mcp-bridge' ),
                    ['status' => 400]
                );
            }
            update_option('blog_public', $params['blog_public'] ? 1 : 0);
            $changed[] = 'blog_public';
        }
        if (empty($changed)) {
            return new WP_Error('invalid_body', __( 'No supported fields supplied.', 'airano-mcp-bridge' ), ['status' => 400]);
        }
        // Re-emit the freshly-stored values so the caller can verify.
        return rest_ensure_response([
            'updated'  => $changed,
            'reading'  => [
                'show_on_front'  => (string) get_option('show_on_front', 'posts'),
                'page_on_front'  => (int) get_option('page_on_front', 0),
                'page_for_posts' => (int) get_option('page_for_posts', 0),
                'posts_per_page' => (int) get_option('posts_per_page', 10),
                'posts_per_rss'  => (int) get_option('posts_per_rss', 10),
                'blog_public'    => ((int) get_option('blog_public', 1)) === 1,
            ],
        ]);
    }

    /**
     * GET /airano-mcp/v1/admin/permalinks
     */
    public function handle_admin_permalinks_get(WP_REST_Request $request) {
        return rest_ensure_response([
            'structure'     => (string) get_option('permalink_structure', ''),
            'category_base' => (string) get_option('category_base', ''),
            'tag_base'      => (string) get_option('tag_base', ''),
        ]);
    }

    /**
     * POST /airano-mcp/v1/admin/permalinks
     * Body: { structure, category_base?, tag_base? }
     * Calls flush_rewrite_rules() after option writes.
     */
    public function handle_admin_permalinks_set(WP_REST_Request $request) {
        $params = $request->get_json_params();
        if (!is_array($params) || !array_key_exists('structure', $params)) {
            return new WP_Error('invalid_body', __( 'structure is required (use "" for plain).', 'airano-mcp-bridge' ), ['status' => 400]);
        }
        if (!is_string($params['structure'])) {
            return new WP_Error('invalid_structure', __( 'structure must be a string.', 'airano-mcp-bridge' ), ['status' => 400]);
        }

        // Ensure the rewrite-rule flush helpers are loaded.
        require_once ABSPATH . 'wp-admin/includes/misc.php';

        global $wp_rewrite;

        $wp_rewrite->set_permalink_structure($params['structure']);

        if (array_key_exists('category_base', $params)) {
            if (!is_string($params['category_base']) || strlen($params['category_base']) > 64) {
                return new WP_Error('invalid_category_base', __( 'category_base must be a string up to 64 chars.', 'airano-mcp-bridge' ), ['status' => 400]);
            }
            $wp_rewrite->set_category_base($params['category_base']);
        }
        if (array_key_exists('tag_base', $params)) {
            if (!is_string($params['tag_base']) || strlen($params['tag_base']) > 64) {
                return new WP_Error('invalid_tag_base', __( 'tag_base must be a string up to 64 chars.', 'airano-mcp-bridge' ), ['status' => 400]);
            }
            $wp_rewrite->set_tag_base($params['tag_base']);
        }

        // Hard flush so the rules table is rebuilt from scratch — same
        // as clicking "Save Changes" on Settings → Permalinks.
        flush_rewrite_rules(true);

        return rest_ensure_response([
            'flushed'       => true,
            'structure'     => (string) get_option('permalink_structure', ''),
            'category_base' => (string) get_option('category_base', ''),
            'tag_base'      => (string) get_option('tag_base', ''),
        ]);
    }

    public function handle_admin_plugin_delete(WP_REST_Request $request) {
        if (!current_user_can('delete_plugins')) {
            return new WP_Error('rest_forbidden', __( 'delete_plugins capability required.', 'airano-mcp-bridge' ), ['status' => 403]);
        }
        $slug = (string) $request['slug'];
        // S-20: never delete the companion via its own route.
        if ($slug === self::COMPANION_SLUG) {
            return new WP_Error(
                'companion_self',
                __( 'Refusing to delete the Airano MCP Bridge companion via its own route. Use WP-Admin → Plugins instead.', 'airano-mcp-bridge' ),
                ['status' => 409]
            );
        }
        $plugin_file = $this->_resolve_plugin_file($slug);
        if (is_wp_error($plugin_file)) {
            return $plugin_file;
        }
        if (!function_exists('is_plugin_active')) {
            require_once ABSPATH . 'wp-admin/includes/plugin.php';
        }
        if (is_plugin_active($plugin_file) || is_plugin_active_for_network($plugin_file)) {
            return new WP_Error(
                'plugin_active',
                __( 'Refusing to delete an active plugin. Deactivate it first.', 'airano-mcp-bridge' ),
                ['status' => 409]
            );
        }
        // S-21: header-marked Required plugins are off-limits for delete.
        $req_check = $this->_plugin_not_required($plugin_file);
        if (is_wp_error($req_check)) {
            return $req_check;
        }
        $deleted = delete_plugins([$plugin_file]);
        if (is_wp_error($deleted)) {
            return $deleted;
        }
        if ($deleted === false || $deleted === null) {
            return new WP_Error('delete_failed', __( 'Plugin delete failed.', 'airano-mcp-bridge' ), ['status' => 500]);
        }
        return rest_ensure_response([
            'deleted'     => true,
            'slug'        => $slug,
            'plugin_file' => $plugin_file,
        ]);
    }

    // ================================================================
    // F.19.6.B — Site layout (menus + widgets + customizer)
    // ================================================================

    /**
     * S-22: validate a nav-menu item's object reference.
     *
     * Dispatch by item ``type``:
     *   - ``post_type`` → ``current_user_can('read_post', $object_id)``.
     *     Refuses items pointing at posts the caller can't read.
     *   - ``taxonomy``  → resolve term + taxonomy. Public taxonomies
     *     are readable by everyone; non-public requires the taxonomy's
     *     ``assign_terms`` cap. Deliberately NOT ``manage_categories``
     *     (that's a write cap and would refuse routine editor flows).
     *   - ``custom``    → no object_id; URL is sanitised separately.
     */
    private function _validate_menu_object_ref($type, $object, $object_id) {
        if ($type === 'custom') {
            return true;
        }
        $object_id = (int) $object_id;
        if ($object_id <= 0) {
            return new WP_Error(
                'forbidden_object_id',
                sprintf(__( 'object_id is required for %s items.', 'airano-mcp-bridge' ), $type),
                ['status' => 400]
            );
        }
        if ($type === 'post_type') {
            $post = get_post($object_id);
            if (!$post) {
                return new WP_Error(
                    'forbidden_object_id',
                    sprintf(__( 'Post %d not found.', 'airano-mcp-bridge' ), $object_id),
                    ['status' => 404]
                );
            }
            if (!current_user_can('read_post', $object_id)) {
                return new WP_Error(
                    'forbidden_object_id',
                    sprintf(__( 'Cannot read post %d.', 'airano-mcp-bridge' ), $object_id),
                    ['status' => 403]
                );
            }
            return true;
        }
        if ($type === 'taxonomy') {
            $taxonomy = is_string($object) && $object !== '' ? $object : 'category';
            $tax = get_taxonomy($taxonomy);
            if (!$tax) {
                return new WP_Error(
                    'forbidden_object_id',
                    sprintf(__( 'Unknown taxonomy %s.', 'airano-mcp-bridge' ), $taxonomy),
                    ['status' => 400]
                );
            }
            $term = get_term($object_id, $taxonomy);
            if (is_wp_error($term) || !$term) {
                return new WP_Error(
                    'forbidden_object_id',
                    sprintf(__( 'Term %d not found in taxonomy %s.', 'airano-mcp-bridge' ), $object_id, $taxonomy),
                    ['status' => 404]
                );
            }
            if (!empty($tax->public)) {
                return true;
            }
            $cap = isset($tax->cap->assign_terms) ? $tax->cap->assign_terms : 'edit_posts';
            if (!current_user_can($cap)) {
                return new WP_Error(
                    'forbidden_object_id',
                    sprintf(__( 'Cannot reference term %d in non-public taxonomy %s.', 'airano-mcp-bridge' ), $object_id, $taxonomy),
                    ['status' => 403]
                );
            }
            return true;
        }
        return new WP_Error(
            'forbidden_object_id',
            sprintf(__( 'Unsupported menu item type %s.', 'airano-mcp-bridge' ), $type),
            ['status' => 400]
        );
    }

    /**
     * GET /airano-mcp/v1/admin/menus
     */
    public function handle_admin_menus_list(WP_REST_Request $request) {
        $menus = wp_get_nav_menus();
        if (is_wp_error($menus)) {
            return $menus;
        }
        $locations = get_nav_menu_locations();
        $menu_to_location = [];
        foreach ($locations as $loc => $mid) {
            if (!isset($menu_to_location[$mid])) {
                $menu_to_location[$mid] = [];
            }
            $menu_to_location[$mid][] = $loc;
        }
        $out = [];
        foreach ($menus as $menu) {
            $items = wp_get_nav_menu_items($menu->term_id);
            $out[] = [
                'id'         => (int) $menu->term_id,
                'name'       => (string) $menu->name,
                'slug'       => (string) $menu->slug,
                'locations'  => isset($menu_to_location[$menu->term_id]) ? $menu_to_location[$menu->term_id] : [],
                'item_count' => is_array($items) ? count($items) : 0,
            ];
        }
        return rest_ensure_response(['menus' => $out]);
    }

    /**
     * GET /airano-mcp/v1/admin/menus/{menu_id}
     */
    public function handle_admin_menu_get(WP_REST_Request $request) {
        $menu_id = (int) $request['menu_id'];
        $menu = wp_get_nav_menu_object($menu_id);
        if (!$menu) {
            return new WP_Error('menu_not_found', __( 'Menu not found.', 'airano-mcp-bridge' ), ['status' => 404]);
        }
        $items_raw = wp_get_nav_menu_items($menu_id);
        if ($items_raw === false || $items_raw === null) {
            $items_raw = [];
        }
        $items = [];
        foreach ($items_raw as $it) {
            $items[] = [
                'id'        => (int) $it->ID,
                'title'     => (string) $it->title,
                'type'      => (string) $it->type,
                'object'    => (string) $it->object,
                'object_id' => (int) $it->object_id,
                'parent'    => (int) $it->menu_item_parent,
                'order'     => (int) $it->menu_order,
                'url'       => (string) $it->url,
                'target'    => (string) $it->target,
                'classes'   => is_array($it->classes) ? array_values($it->classes) : [],
                'xfn'       => (string) $it->xfn,
            ];
        }
        return rest_ensure_response([
            'id'    => (int) $menu->term_id,
            'name'  => (string) $menu->name,
            'slug'  => (string) $menu->slug,
            'items' => $items,
        ]);
    }

    /**
     * PUT /airano-mcp/v1/admin/menus/{menu_id}
     * Body: { items: [...], name? } — full replace, slug frozen.
     * Two-pass: validate every item against S-22 first, then mutate.
     */
    public function handle_admin_menu_set(WP_REST_Request $request) {
        $menu_id = (int) $request['menu_id'];
        $menu = wp_get_nav_menu_object($menu_id);
        if (!$menu) {
            return new WP_Error('menu_not_found', __( 'Menu not found.', 'airano-mcp-bridge' ), ['status' => 404]);
        }
        $params = $request->get_json_params();
        if (!is_array($params) || !isset($params['items']) || !is_array($params['items'])) {
            return new WP_Error('invalid_body', __( 'items array is required.', 'airano-mcp-bridge' ), ['status' => 400]);
        }
        $items = $params['items'];
        // ── Pass 1: validate every item up-front (S-22).
        foreach ($items as $idx => $it) {
            if (!is_array($it)) {
                return new WP_Error('invalid_item', sprintf(__( 'items[%d] must be an object.', 'airano-mcp-bridge' ), $idx), ['status' => 400]);
            }
            $type = isset($it['type']) ? (string) $it['type'] : 'custom';
            $object = isset($it['object']) ? (string) $it['object'] : '';
            $object_id = isset($it['object_id']) ? (int) $it['object_id'] : 0;
            $check = $this->_validate_menu_object_ref($type, $object, $object_id);
            if (is_wp_error($check)) {
                return $check;
            }
        }
        // ── Optional rename (slug stays frozen — theme_location maps via slug).
        if (array_key_exists('name', $params)) {
            if (!is_string($params['name']) || trim($params['name']) === '') {
                return new WP_Error('invalid_name', __( 'name must be a non-empty string.', 'airano-mcp-bridge' ), ['status' => 400]);
            }
            $rename = wp_update_nav_menu_object($menu_id, ['menu-name' => sanitize_text_field($params['name'])]);
            if (is_wp_error($rename)) {
                return $rename;
            }
        }
        // ── Pass 2: write items.
        require_once ABSPATH . 'wp-admin/includes/nav-menu.php';
        $existing = wp_get_nav_menu_items($menu_id);
        if ($existing === false || $existing === null) {
            $existing = [];
        }
        $existing_ids = [];
        foreach ($existing as $e) {
            $existing_ids[(int) $e->ID] = true;
        }
        $kept_ids = [];
        $created = 0;
        $updated = 0;
        foreach ($items as $idx => $it) {
            $type = isset($it['type']) ? (string) $it['type'] : 'custom';
            $object = isset($it['object']) ? (string) $it['object'] : '';
            $object_id = isset($it['object_id']) ? (int) $it['object_id'] : 0;
            $title = isset($it['title']) ? (string) $it['title'] : '';
            $url = isset($it['url']) ? esc_url_raw($it['url']) : '';
            $parent = isset($it['parent']) ? (int) $it['parent'] : 0;
            $order = isset($it['order']) ? (int) $it['order'] : ($idx + 1);
            $target = isset($it['target']) ? (string) $it['target'] : '';
            $existing_item_id = isset($it['id']) ? (int) $it['id'] : 0;
            $menu_item_data = [
                'menu-item-title'      => sanitize_text_field($title),
                'menu-item-type'       => $type,
                'menu-item-object'     => $object,
                'menu-item-object-id'  => $object_id,
                'menu-item-parent-id'  => $parent,
                'menu-item-position'   => $order,
                'menu-item-url'        => $url,
                'menu-item-target'     => $target,
                'menu-item-status'     => 'publish',
            ];
            if ($existing_item_id > 0 && isset($existing_ids[$existing_item_id])) {
                $rid = wp_update_nav_menu_item($menu_id, $existing_item_id, $menu_item_data);
                if (is_wp_error($rid)) {
                    return $rid;
                }
                $kept_ids[(int) $rid] = true;
                $updated++;
            } else {
                $rid = wp_update_nav_menu_item($menu_id, 0, $menu_item_data);
                if (is_wp_error($rid)) {
                    return $rid;
                }
                $kept_ids[(int) $rid] = true;
                $created++;
            }
        }
        // ── Delete items no longer in the array.
        $deleted = 0;
        foreach (array_keys($existing_ids) as $eid) {
            if (!isset($kept_ids[$eid])) {
                $r = wp_delete_post($eid, true);
                if ($r) {
                    $deleted++;
                }
            }
        }
        return rest_ensure_response([
            'id'      => $menu_id,
            'created' => $created,
            'updated' => $updated,
            'deleted' => $deleted,
            'total'   => count($items),
        ]);
    }

    /**
     * Detect whether a sidebar's existing widgets are all `block-N` (block-kind)
     * or contain at least one legacy widget. Empty area falls back to the
     * global ``wp_use_widgets_block_editor()`` signal.
     */
    private function _detect_widget_area_kind($widget_ids) {
        if (is_array($widget_ids) && !empty($widget_ids)) {
            foreach ($widget_ids as $wid) {
                if (strpos((string) $wid, 'block-') !== 0) {
                    return 'legacy';
                }
            }
            return 'block';
        }
        return (function_exists('wp_use_widgets_block_editor') && wp_use_widgets_block_editor()) ? 'block' : 'legacy';
    }

    /**
     * GET /airano-mcp/v1/admin/widgets/areas
     */
    public function handle_admin_widget_areas_list(WP_REST_Request $request) {
        global $wp_registered_sidebars;
        $sidebars_widgets = wp_get_sidebars_widgets();
        $out = [];
        if (is_array($wp_registered_sidebars)) {
            foreach ($wp_registered_sidebars as $sidebar_id => $sidebar) {
                $widget_ids = isset($sidebars_widgets[$sidebar_id]) ? $sidebars_widgets[$sidebar_id] : [];
                $out[] = [
                    'id'             => (string) $sidebar_id,
                    'name'           => (string) (isset($sidebar['name']) ? $sidebar['name'] : $sidebar_id),
                    'description'    => (string) (isset($sidebar['description']) ? $sidebar['description'] : ''),
                    'theme_location' => (string) $sidebar_id,
                    'widget_count'   => is_array($widget_ids) ? count($widget_ids) : 0,
                    'kind'           => $this->_detect_widget_area_kind($widget_ids),
                ];
            }
        }
        return rest_ensure_response(['areas' => $out]);
    }

    /**
     * GET /airano-mcp/v1/admin/widgets/{area_id}
     */
    public function handle_admin_widget_get(WP_REST_Request $request) {
        $area_id = (string) $request['area_id'];
        global $wp_registered_sidebars;
        if (!is_array($wp_registered_sidebars) || !isset($wp_registered_sidebars[$area_id])) {
            return new WP_Error('area_not_found', __( 'Widget area not found.', 'airano-mcp-bridge' ), ['status' => 404]);
        }
        $sidebars_widgets = wp_get_sidebars_widgets();
        $widget_ids = isset($sidebars_widgets[$area_id]) ? $sidebars_widgets[$area_id] : [];
        $kind = $this->_detect_widget_area_kind($widget_ids);
        $widgets = [];
        if (is_array($widget_ids)) {
            foreach ($widget_ids as $wid) {
                $wid_str = (string) $wid;
                $parts = preg_split('/-(?=\d+$)/', $wid_str);
                $base = isset($parts[0]) ? $parts[0] : $wid_str;
                $num = isset($parts[1]) ? (int) $parts[1] : 0;
                $opt = get_option('widget_' . $base, []);
                $instance = is_array($opt) && isset($opt[$num]) ? $opt[$num] : [];
                if ($base === 'block') {
                    $raw = isset($instance['content']) ? (string) $instance['content'] : '';
                    $widgets[] = [
                        'id'     => $wid_str,
                        'type'   => 'block',
                        'blocks' => function_exists('parse_blocks') ? parse_blocks($raw) : [],
                        'raw'    => $raw,
                    ];
                } else {
                    $widgets[] = [
                        'id'       => $wid_str,
                        'type'     => $base,
                        'settings' => is_array($instance) ? $instance : [],
                    ];
                }
            }
        }
        return rest_ensure_response([
            'area_id' => $area_id,
            'kind'    => $kind,
            'widgets' => $widgets,
        ]);
    }

    /**
     * Walk every other sidebar and collect the widget instances (keyed
     * by integer index) currently in use. We need this to avoid orphaning
     * shared widget instances when we rewrite a single area.
     */
    private function _other_sidebars_used_instances($sidebars_widgets, $skip_area_id, $base_prefix, $existing_option) {
        $out = [];
        $prefix_len = strlen($base_prefix);
        foreach ($sidebars_widgets as $sid => $wids) {
            if ($sid === $skip_area_id) continue;
            if (!is_array($wids)) continue;
            foreach ($wids as $wid) {
                if (strpos((string) $wid, $base_prefix) === 0) {
                    $n = (int) substr((string) $wid, $prefix_len);
                    if (isset($existing_option[$n])) {
                        $out[$n] = $existing_option[$n];
                    }
                }
            }
        }
        return $out;
    }

    /**
     * PUT /airano-mcp/v1/admin/widgets/{area_id}
     * Body: { widgets: [...] } — full replace. Block-kind areas accept
     * any widget with ``raw`` (block HTML, sanitised via wp_kses_post per
     * S-23 unless caller has unfiltered_html). Legacy-kind areas accept
     * ``text`` widget settings only this round; other legacy types are
     * read-only and return ``unsupported_legacy_widget``. Any caller-side
     * ``kind`` field in the body is ignored — area kind is determined by
     * the area itself, not the request.
     */
    public function handle_admin_widget_set(WP_REST_Request $request) {
        $area_id = (string) $request['area_id'];
        global $wp_registered_sidebars;
        if (!is_array($wp_registered_sidebars) || !isset($wp_registered_sidebars[$area_id])) {
            return new WP_Error('area_not_found', __( 'Widget area not found.', 'airano-mcp-bridge' ), ['status' => 404]);
        }
        $params = $request->get_json_params();
        if (!is_array($params) || !isset($params['widgets']) || !is_array($params['widgets'])) {
            return new WP_Error('invalid_body', __( 'widgets array is required.', 'airano-mcp-bridge' ), ['status' => 400]);
        }
        $widgets_in = $params['widgets'];
        $sidebars_widgets = wp_get_sidebars_widgets();
        $existing_ids = isset($sidebars_widgets[$area_id]) ? $sidebars_widgets[$area_id] : [];
        $area_kind = $this->_detect_widget_area_kind($existing_ids);
        $can_raw_html = current_user_can('unfiltered_html');
        // ── Pass 1: validate every widget shape up-front.
        foreach ($widgets_in as $idx => $w) {
            if (!is_array($w)) {
                return new WP_Error('invalid_widget', sprintf(__( 'widgets[%d] must be an object.', 'airano-mcp-bridge' ), $idx), ['status' => 400]);
            }
            $type = isset($w['type']) ? (string) $w['type'] : '';
            if ($area_kind === 'block') {
                if ($type !== '' && $type !== 'block') {
                    return new WP_Error('invalid_widget', sprintf(__( 'Block-kind area accepts only `block` widgets (widgets[%d] has type=%s).', 'airano-mcp-bridge' ), $idx, $type), ['status' => 400]);
                }
            } else {
                if ($type !== 'text') {
                    return new WP_Error('unsupported_legacy_widget', sprintf(__( 'F.19.6.B writes legacy widgets of type `text` only (widgets[%d] has type=%s). Other legacy types are read-only.', 'airano-mcp-bridge' ), $idx, $type), ['status' => 400]);
                }
            }
        }
        // ── Pass 2: write.
        if ($area_kind === 'block') {
            $existing_block = get_option('widget_block', []);
            if (!is_array($existing_block)) {
                $existing_block = [];
            }
            $next_num = 2;
            foreach (array_keys($existing_block) as $k) {
                if (is_int($k) && $k >= $next_num) {
                    $next_num = $k + 1;
                }
            }
            $new_widget_ids = [];
            $new_block_option = [];
            foreach ($widgets_in as $w) {
                $raw = isset($w['raw']) ? (string) $w['raw'] : '';
                if ($raw === '' && isset($w['blocks']) && is_array($w['blocks']) && function_exists('serialize_blocks')) {
                    $raw = serialize_blocks($w['blocks']);
                }
                $sanitised = $can_raw_html ? $raw : wp_kses_post($raw);
                $new_block_option[$next_num] = ['content' => $sanitised];
                $new_widget_ids[] = 'block-' . $next_num;
                $next_num++;
            }
            $other_used = $this->_other_sidebars_used_instances($sidebars_widgets, $area_id, 'block-', $existing_block);
            $final_block = $other_used + $new_block_option;
            $final_block['_multiwidget'] = 1;
            update_option('widget_block', $final_block);
            $sidebars_widgets[$area_id] = $new_widget_ids;
            wp_set_sidebars_widgets($sidebars_widgets);
            return rest_ensure_response([
                'area_id' => $area_id,
                'kind'    => 'block',
                'count'   => count($new_widget_ids),
            ]);
        }
        // Legacy text-only path.
        $existing_text = get_option('widget_text', []);
        if (!is_array($existing_text)) {
            $existing_text = [];
        }
        $next_num = 2;
        foreach (array_keys($existing_text) as $k) {
            if (is_int($k) && $k >= $next_num) {
                $next_num = $k + 1;
            }
        }
        $new_widget_ids = [];
        $new_text_option = [];
        foreach ($widgets_in as $w) {
            $settings = isset($w['settings']) && is_array($w['settings']) ? $w['settings'] : [];
            $title = isset($settings['title']) ? sanitize_text_field((string) $settings['title']) : '';
            $text = isset($settings['text']) ? (string) $settings['text'] : '';
            $sanitised_text = $can_raw_html ? $text : wp_kses_post($text);
            $filter = isset($settings['filter']) ? (bool) $settings['filter'] : false;
            $visual = isset($settings['visual']) ? (bool) $settings['visual'] : true;
            $new_text_option[$next_num] = [
                'title'  => $title,
                'text'   => $sanitised_text,
                'filter' => $filter,
                'visual' => $visual,
            ];
            $new_widget_ids[] = 'text-' . $next_num;
            $next_num++;
        }
        $other_used = $this->_other_sidebars_used_instances($sidebars_widgets, $area_id, 'text-', $existing_text);
        $final_text = $other_used + $new_text_option;
        $final_text['_multiwidget'] = 1;
        update_option('widget_text', $final_text);
        $sidebars_widgets[$area_id] = $new_widget_ids;
        wp_set_sidebars_widgets($sidebars_widgets);
        return rest_ensure_response([
            'area_id' => $area_id,
            'kind'    => 'legacy',
            'count'   => count($new_widget_ids),
        ]);
    }

    /**
     * POST /airano-mcp/v1/admin/customizer/changeset
     * Body: { action: get|apply|discard }
     *
     * S-24: ``apply`` requires the ``customize`` cap (not just
     * ``manage_options`` — same bar as /wp-admin/customize.php).
     * Empty changeset returns ``status: empty`` 200, not 404 — easier
     * for callers that poll without first probing existence.
     */
    public function handle_admin_customizer_changeset(WP_REST_Request $request) {
        $params = $request->get_json_params();
        $action = isset($params['action']) ? (string) $params['action'] : '';
        if (!in_array($action, ['get', 'apply', 'discard'], true)) {
            return new WP_Error('invalid_action', __( 'action must be one of get|apply|discard.', 'airano-mcp-bridge' ), ['status' => 400]);
        }
        if ($action === 'apply' && !current_user_can('customize')) {
            return new WP_Error('rest_forbidden', __( 'customize capability required to apply a customizer changeset.', 'airano-mcp-bridge' ), ['status' => 403]);
        }
        $posts = get_posts([
            'post_type'   => 'customize_changeset',
            'post_status' => ['draft', 'auto-draft', 'pending', 'future'],
            'numberposts' => 1,
            'orderby'     => 'modified',
            'order'       => 'DESC',
        ]);
        if (empty($posts)) {
            return rest_ensure_response(['status' => 'empty', 'changeset' => null]);
        }
        $changeset = $posts[0];
        if ($action === 'get') {
            $data = json_decode($changeset->post_content, true);
            if (!is_array($data)) {
                $data = [];
            }
            return rest_ensure_response([
                'status'   => 'pending',
                'id'       => (int) $changeset->ID,
                'uuid'     => (string) $changeset->post_name,
                'modified' => (string) $changeset->post_modified_gmt,
                'data'     => $data,
            ]);
        }
        if ($action === 'discard') {
            $deleted = wp_delete_post($changeset->ID, true);
            if (!$deleted) {
                return new WP_Error('discard_failed', __( 'Failed to delete changeset.', 'airano-mcp-bridge' ), ['status' => 500]);
            }
            return rest_ensure_response([
                'status' => 'discarded',
                'id'     => (int) $changeset->ID,
            ]);
        }
        // action === 'apply'
        require_once ABSPATH . WPINC . '/class-wp-customize-manager.php';
        $manager = new WP_Customize_Manager(['changeset_uuid' => $changeset->post_name]);
        $result = $manager->save_changeset_post(['status' => 'publish']);
        if (is_wp_error($result)) {
            return $result;
        }
        return rest_ensure_response([
            'status' => 'applied',
            'id'     => (int) $changeset->ID,
        ]);
    }

    /**
     * GET /airano-mcp/v1/admin/db/size
     *
     * Single ``information_schema.TABLES`` aggregation scoped to the
     * current WP database + the WP table prefix. Returns
     * ``{database_bytes, table_count, row_count_estimate}`` — caller
     * never picks the SQL, so there is no injection surface (S-25).
     * ``row_count_estimate`` mirrors MySQL's own caveat: InnoDB row
     * counts are estimates, not exact. F.19.3.2.
     */
    public function handle_admin_db_size(WP_REST_Request $request) {
        global $wpdb;
        $like = $wpdb->esc_like($wpdb->prefix) . '%';
        $row = $wpdb->get_row(
            $wpdb->prepare(
                "SELECT
                    COALESCE(SUM(data_length + index_length), 0) AS total_bytes,
                    COUNT(*)                                     AS table_count,
                    COALESCE(SUM(table_rows), 0)                 AS row_count
                 FROM information_schema.TABLES
                 WHERE table_schema = %s
                   AND table_name LIKE %s",
                DB_NAME,
                $like
            ),
            ARRAY_A
        );
        if (!is_array($row)) {
            return new WP_Error(
                'db_size_query_failed',
                __( 'Failed to read information_schema.TABLES.', 'airano-mcp-bridge' ),
                ['status' => 500]
            );
        }
        return rest_ensure_response([
            'database_bytes'      => (int) $row['total_bytes'],
            'table_count'         => (int) $row['table_count'],
            'row_count_estimate'  => (int) $row['row_count'],
            'database_name'       => DB_NAME,
            'table_prefix'        => $wpdb->prefix,
        ]);
    }

    /**
     * GET /airano-mcp/v1/admin/db/tables
     *
     * Per-WP-table breakdown from ``information_schema.TABLES``. Same
     * source as ``/admin/db/size`` but one row per table. Useful for
     * "which table is the bloat?" debugging. ``rows`` is an estimate
     * for InnoDB. F.19.3.2.
     */
    public function handle_admin_db_tables(WP_REST_Request $request) {
        global $wpdb;
        $like = $wpdb->esc_like($wpdb->prefix) . '%';
        $rows = $wpdb->get_results(
            $wpdb->prepare(
                "SELECT
                    table_name,
                    engine,
                    table_rows,
                    data_length,
                    index_length,
                    (data_length + index_length) AS total_bytes,
                    table_collation
                 FROM information_schema.TABLES
                 WHERE table_schema = %s
                   AND table_name LIKE %s
                 ORDER BY (data_length + index_length) DESC",
                DB_NAME,
                $like
            ),
            ARRAY_A
        );
        if (!is_array($rows)) {
            return new WP_Error(
                'db_tables_query_failed',
                __( 'Failed to read information_schema.TABLES.', 'airano-mcp-bridge' ),
                ['status' => 500]
            );
        }
        $out = [];
        foreach ($rows as $r) {
            $out[] = [
                'name'        => (string) $r['table_name'],
                'engine'      => $r['engine'] !== null ? (string) $r['engine'] : null,
                'rows'        => (int) $r['table_rows'],
                'data_bytes'  => (int) $r['data_length'],
                'index_bytes' => (int) $r['index_length'],
                'total_bytes' => (int) $r['total_bytes'],
                'collation'   => $r['table_collation'] !== null ? (string) $r['table_collation'] : null,
            ];
        }
        return rest_ensure_response([
            'database_name' => DB_NAME,
            'table_prefix'  => $wpdb->prefix,
            'tables'        => $out,
        ]);
    }

    /**
     * POST /airano-mcp/v1/admin/db/search
     * Body: { query, post_type?, status?, limit? }
     *
     * Wraps ``WP_Query`` with ``s=$query`` — never raw SQL (S-25).
     * ``query`` is sanitised via ``sanitize_text_field`` and capped at
     * 200 chars; ``limit`` is capped at 100. ``WP_Query``'s own
     * ``posts_clauses`` filter (the same one the WP search page uses)
     * keeps non-readable posts (private/draft from other authors) out
     * of the result set. F.19.3.3.
     */
    public function handle_admin_db_search(WP_REST_Request $request) {
        $params = $request->get_json_params();
        if (!is_array($params)) {
            $params = [];
        }
        $query_raw = isset($params['query']) ? (string) $params['query'] : '';
        $query     = sanitize_text_field(wp_unslash($query_raw));
        if (strlen($query) > 200) {
            $query = substr($query, 0, 200);
        }
        if ($query === '') {
            return new WP_Error(
                'invalid_query',
                __( 'query is required and must be a non-empty string after sanitisation.', 'airano-mcp-bridge' ),
                ['status' => 400]
            );
        }

        $limit = isset($params['limit']) ? (int) $params['limit'] : 20;
        if ($limit < 1) {
            $limit = 1;
        }
        if ($limit > 100) {
            $limit = 100;
        }

        $args = [
            's'              => $query,
            'posts_per_page' => $limit,
            'post_status'    => 'any',
            'no_found_rows'  => true,
        ];
        if (isset($params['post_type']) && $params['post_type'] !== '') {
            $pt_in = $params['post_type'];
            if (is_array($pt_in)) {
                $pt = array_values(array_filter(array_map('sanitize_key', $pt_in)));
            } else {
                $pt = sanitize_key((string) $pt_in);
            }
            $args['post_type'] = $pt;
        } else {
            $args['post_type'] = 'any';
        }
        if (isset($params['status']) && $params['status'] !== '') {
            $st_in = $params['status'];
            if (is_array($st_in)) {
                $args['post_status'] = array_values(array_filter(array_map('sanitize_key', $st_in)));
            } else {
                $args['post_status'] = sanitize_key((string) $st_in);
            }
        }

        $q = new WP_Query($args);
        $hits = [];
        foreach ($q->posts as $p) {
            $excerpt = has_excerpt($p) ? $p->post_excerpt : wp_trim_words(wp_strip_all_tags($p->post_content), 30, '…');
            $hits[] = [
                'id'        => (int) $p->ID,
                'post_type' => (string) $p->post_type,
                'status'    => (string) $p->post_status,
                'title'     => (string) $p->post_title,
                'snippet'   => (string) $excerpt,
                'url'       => (string) get_permalink($p),
                'modified'  => (string) $p->post_modified_gmt,
            ];
        }
        return rest_ensure_response([
            'query' => $query,
            'limit' => $limit,
            'count' => count($hits),
            'hits'  => $hits,
        ]);
    }
}

// Initialize the plugin
new SEO_API_Bridge();
