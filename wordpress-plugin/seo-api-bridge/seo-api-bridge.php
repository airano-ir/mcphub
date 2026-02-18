<?php
/**
 * Plugin Name: SEO API Bridge
 * Plugin URI: https://github.com/airano-ir/mcphub
 * Description: Exposes Rank Math SEO and Yoast SEO meta fields via WordPress REST API for use with MCP servers and AI agents. Supports posts, pages, and WooCommerce products with full CRUD operations.
 * Version: 1.3.0
 * Author: MCP Hub
 * Author URI: https://github.com/airano-ir
 * License: GPL-2.0-or-later
 * Requires at least: 5.0
 * Requires PHP: 7.4
 * Text Domain: seo-api-bridge
 *
 * Changelog:
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
 * SEO API Bridge Main Class
 */
class SEO_API_Bridge {

    /**
     * Plugin version
     */
    const VERSION = '1.3.0';

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
    }

    /**
     * Register REST API routes
     */
    public function register_rest_routes() {
        // Status endpoint
        register_rest_route('seo-api-bridge/v1', '/status', [
            'methods' => 'GET',
            'callback' => [$this, 'get_status'],
            'permission_callback' => function() {
                return is_user_logged_in();
            }
        ]);

        // Post SEO endpoints
        register_rest_route('seo-api-bridge/v1', '/posts/(?P<id>\d+)/seo', [
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
        register_rest_route('seo-api-bridge/v1', '/pages/(?P<id>\d+)/seo', [
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
        register_rest_route('seo-api-bridge/v1', '/products/(?P<id>\d+)/seo', [
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
    }

    /**
     * Get plugin status endpoint
     */
    public function get_status() {
        $rank_math_active = $this->is_rank_math_active();
        $yoast_active = $this->is_yoast_active();

        $response = [
            'plugin' => 'SEO API Bridge',
            'version' => self::VERSION,
            'active' => true,
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

        return 'SEO API Bridge is active and working with ' . implode(' and ', $active_plugins) . '.';
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
                register_post_meta($post_type, $meta_key, [
                    'show_in_rest' => true,
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
                sprintf('%s not found', ucfirst($post_type)),
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
                'No supported SEO plugin found (Rank Math or Yoast required)',
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
                sprintf('%s not found', ucfirst($post_type)),
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
                'No supported SEO plugin found',
                ['status' => 500]
            );
        }

        return rest_ensure_response([
            'post_id' => $post_id,
            'post_type' => $post_type,
            'updated_fields' => $updated_fields,
            'message' => 'SEO metadata updated successfully'
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
            echo '<p><strong>SEO API Bridge:</strong> ' . esc_html__( 'Neither Rank Math SEO nor Yoast SEO is detected. Please install and activate one of these plugins to enable SEO meta field access via REST API.', 'seo-api-bridge' ) . '</p>';
            echo '</div>';
        } else {
            $active_plugins = [];
            if ($rank_math_active) $active_plugins[] = 'Rank Math SEO';
            if ($yoast_active) $active_plugins[] = 'Yoast SEO';

            $supported_types = implode(', ', $this->supported_post_types);

            echo '<div class="notice notice-success is-dismissible">';
            echo '<p><strong>SEO API Bridge v' . esc_html( self::VERSION ) . ':</strong> ' . esc_html( sprintf( 'Successfully registered meta fields for %s.', implode( ' and ', $active_plugins ) ) ) . '</p>';
            echo '<p><strong>' . esc_html__( 'Supported post types:', 'seo-api-bridge' ) . '</strong> ' . esc_html( $supported_types ) . '</p>';

            if ($woocommerce_active) {
                echo '<p><strong>WooCommerce:</strong> ' . esc_html__( 'Detected and supported. Product SEO fields are available via REST API.', 'seo-api-bridge' ) . '</p>';
            }
            echo '</div>';
        }
    }
}

// Initialize the plugin
new SEO_API_Bridge();
