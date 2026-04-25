<?php
/**
 * Plugin Name: Airano MCP Bridge
 * Plugin URI: https://github.com/airano-ir/mcphub
 * Description: Companion plugin for MCP Hub. Exposes SEO meta (Rank Math / Yoast), media upload helpers (bypass upload_max_filesize), and site capabilities via the WordPress REST API for AI agents and MCP servers. Supports posts, pages, and WooCommerce products.
 * Version: 2.10.1
 * Author: MCP Hub
 * Author URI: https://github.com/airano-ir
 * License: GPL-2.0-or-later
 * Requires at least: 5.0
 * Requires PHP: 7.4
 * Text Domain: airano-mcp-bridge
 *
 * Changelog:
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
    const VERSION = '2.10.1';

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
        ];
    }

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
            'permission_callback' => [$this, 'require_upload_capability'],
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

        // Stage to tmp + hand off to wp_handle_sideload().
        require_once ABSPATH . 'wp-admin/includes/file.php';
        require_once ABSPATH . 'wp-admin/includes/media.php';
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

        require_once ABSPATH . 'wp-admin/includes/file.php';
        require_once ABSPATH . 'wp-admin/includes/media.php';
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
}

// Initialize the plugin
new SEO_API_Bridge();
