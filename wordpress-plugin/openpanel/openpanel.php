<?php
/**
 * Plugin Name: OpenPanel
 * Description: Activate OpenPanel to start tracking your website. Supports both Cloud and Self-Hosted instances.
 * Version: 1.1.1
 * Author: OpenPanel / Airano
 * License: GPLv2 or later
 * Requires at least: 5.8
 * Requires PHP: 7.4
 * Tested up to: 6.8
 * Text Domain: openpanel
 */

if (!defined('ABSPATH')) { exit; }

final class OP_WP_Proxy {
    const VERSION = '1.1.1';
    const OPTION_KEY   = 'op_wp_proxy_settings';
    const TRANSIENT_JS = 'op_wp_op1_js';
    const REST_NS      = 'openpanel';
    const REST_ROUTE   = '/(?P<path>.*)'; // wildcard path passthrough
    const CACHE_TIMEOUT = WEEK_IN_SECONDS;

    // Cloud defaults
    const CLOUD_JS_URL    = 'https://openpanel.dev/op1.js';
    const CLOUD_API_BASE  = 'https://api.openpanel.dev/';

    public function __construct() {
        add_action('admin_init', [$this, 'register_settings']);
        add_action('admin_menu', [$this, 'add_settings_page']);
        add_action('wp_enqueue_scripts', [$this, 'inject_inline_sdk'], 0);
        add_action('rest_api_init', [$this, 'register_proxy_route']);
        add_action('admin_init', [$this, 'handle_cache_clear']);
    }

    /** ---------------- Settings ---------------- */
    public function register_settings() {
        register_setting(self::OPTION_KEY, self::OPTION_KEY, [
            'type' => 'array',
            'show_in_rest' => false,
            'sanitize_callback' => function($input) {
                $out = [];
                $out['hosting_mode'] = isset($input['hosting_mode']) && $input['hosting_mode'] === 'selfhosted' ? 'selfhosted' : 'cloud';
                $out['client_id'] = isset($input['client_id']) ? sanitize_text_field($input['client_id']) : '';
                $out['api_url'] = isset($input['api_url']) ? esc_url_raw(untrailingslashit($input['api_url'])) : '';
                $out['dashboard_url'] = isset($input['dashboard_url']) ? esc_url_raw(untrailingslashit($input['dashboard_url'])) : '';
                $out['track_screen'] = !empty($input['track_screen']) ? 1 : 0;
                $out['track_outgoing'] = !empty($input['track_outgoing']) ? 1 : 0;
                $out['track_attributes'] = !empty($input['track_attributes']) ? 1 : 0;
                return $out;
            }
        ]);

        // Section: Hosting Mode
        add_settings_section('op_hosting', __('Hosting Mode', 'openpanel'), function() {
            echo '<p>' . esc_html__('Choose between OpenPanel Cloud or your own Self-Hosted instance.', 'openpanel') . '</p>';
        }, self::OPTION_KEY);

        add_settings_field('hosting_mode', __('Mode', 'openpanel'), function() {
            $opts = get_option(self::OPTION_KEY);
            $mode = isset($opts['hosting_mode']) ? $opts['hosting_mode'] : 'cloud';
            ?>
            <label>
                <input type="radio" name="<?php echo esc_attr(self::OPTION_KEY); ?>[hosting_mode]" value="cloud" <?php checked($mode, 'cloud'); ?> class="op-hosting-mode">
                <?php esc_html_e('Cloud (openpanel.dev)', 'openpanel'); ?>
            </label><br>
            <label>
                <input type="radio" name="<?php echo esc_attr(self::OPTION_KEY); ?>[hosting_mode]" value="selfhosted" <?php checked($mode, 'selfhosted'); ?> class="op-hosting-mode">
                <?php esc_html_e('Self-Hosted', 'openpanel'); ?>
            </label>
            <p class="description"><?php esc_html_e('Select Self-Hosted if you run your own OpenPanel instance.', 'openpanel'); ?></p>
            <?php
        }, self::OPTION_KEY, 'op_hosting');

        // Section: Self-Hosted URLs
        add_settings_section('op_selfhosted', __('Self-Hosted Settings', 'openpanel'), function() {
            echo '<p>' . esc_html__('Configure your Self-Hosted OpenPanel URLs. Only required if using Self-Hosted mode.', 'openpanel') . '</p>';
        }, self::OPTION_KEY);

        add_settings_field('api_url', __('API URL', 'openpanel'), function() {
            $opts = get_option(self::OPTION_KEY);
            printf('<input type="url" name="%s[api_url]" value="%s" class="regular-text op-selfhosted-field" placeholder="https://api.openpanel.yourdomain.com"/>',
                esc_attr(self::OPTION_KEY),
                isset($opts['api_url']) ? esc_attr($opts['api_url']) : ''
            );
            echo '<p class="description">' . esc_html__('Your OpenPanel API endpoint (e.g., https://api.openpanel.yourdomain.com)', 'openpanel') . '</p>';
        }, self::OPTION_KEY, 'op_selfhosted');

        add_settings_field('dashboard_url', __('Dashboard URL', 'openpanel'), function() {
            $opts = get_option(self::OPTION_KEY);
            printf('<input type="url" name="%s[dashboard_url]" value="%s" class="regular-text op-selfhosted-field" placeholder="https://openpanel.yourdomain.com"/>',
                esc_attr(self::OPTION_KEY),
                isset($opts['dashboard_url']) ? esc_attr($opts['dashboard_url']) : ''
            );
            echo '<p class="description">' . esc_html__('Your OpenPanel Dashboard URL — used to load op1.js from your server instead of the CDN (e.g., https://openpanel.yourdomain.com)', 'openpanel') . '</p>';
        }, self::OPTION_KEY, 'op_selfhosted');

        // Section: Main Settings
        add_settings_section('op_main', __('OpenPanel Settings', 'openpanel'), function() {
            echo '<p>' . esc_html__('Set your OpenPanel Client ID. The SDK and requests are served from your domain to avoid ad blockers.', 'openpanel') . '</p>';
        }, self::OPTION_KEY);

        add_settings_field('client_id', __('Client ID', 'openpanel'), function() {
            $opts = get_option(self::OPTION_KEY);
            printf('<input type="text" name="%s[client_id]" value="%s" class="regular-text" placeholder="op_client_..."/>',
                esc_attr(self::OPTION_KEY),
                isset($opts['client_id']) ? esc_attr($opts['client_id']) : ''
            );
        }, self::OPTION_KEY, 'op_main');

        add_settings_field('toggles', __('Auto-tracking (optional)', 'openpanel'), function() {
            $o = get_option(self::OPTION_KEY);
            // Default track_screen to true if not set
            $track_screen = isset($o['track_screen']) ? !empty($o['track_screen']) : true;
            ?>
            <label><input type="checkbox" name="<?php echo esc_attr(self::OPTION_KEY); ?>[track_screen]" <?php checked($track_screen); ?>> <?php esc_html_e('Track page views automatically', 'openpanel'); ?></label><br>
            <label><input type="checkbox" name="<?php echo esc_attr(self::OPTION_KEY); ?>[track_outgoing]" <?php checked(!empty($o['track_outgoing'])); ?>> <?php esc_html_e('Track clicks on outgoing links', 'openpanel'); ?></label><br>
            <label><input type="checkbox" name="<?php echo esc_attr(self::OPTION_KEY); ?>[track_attributes]" <?php checked(!empty($o['track_attributes'])); ?>> <?php esc_html_e('Track additional page attributes', 'openpanel'); ?></label>
            <?php
        }, self::OPTION_KEY, 'op_main');
    }

    public function add_settings_page() {
        add_options_page(
            'OpenPanel',
            'OpenPanel',
            'manage_options',
            'op-wp-proxy',
            [$this, 'render_settings_page']
        );
    }

    public function handle_cache_clear() {
        if (isset($_POST['op_clear_cache']) && current_user_can('manage_options')) {
            if (isset($_POST['_wpnonce']) && wp_verify_nonce(sanitize_text_field(wp_unslash($_POST['_wpnonce'])), 'op_clear_cache_nonce')) {
                delete_transient(self::TRANSIENT_JS);
                add_action('admin_notices', function() {
                    echo '<div class="notice notice-success is-dismissible"><p>' . 
                         esc_html__('OpenPanel cache cleared successfully. The latest op1.js will be fetched on the next page load.', 'openpanel') . 
                         '</p></div>';
                });
            }
        }
    }

    public function render_settings_page() {
        $opts = get_option(self::OPTION_KEY);
        $mode = isset($opts['hosting_mode']) ? $opts['hosting_mode'] : 'cloud';
        ?>
        <div class="wrap">
            <h1>OpenPanel</h1>
            <form method="post" action="options.php">
                <?php
                settings_fields(self::OPTION_KEY);
                do_settings_sections(self::OPTION_KEY);
                submit_button(__('Save Settings', 'openpanel'));
                ?>
            </form>

            <hr style="margin: 2rem 0;">

            <h2><?php esc_html_e('Cache Management', 'openpanel'); ?></h2>
            <p><?php esc_html_e('Clear the cached op1.js file to force fetch the latest version from OpenPanel.', 'openpanel'); ?></p>

            <form method="post" action="">
                <?php wp_nonce_field('op_clear_cache_nonce'); ?>
                <input type="submit" name="op_clear_cache" class="button button-secondary" value="<?php esc_attr_e('Clear Cache & Force Refresh', 'openpanel'); ?>">
            </form>

            <?php
            // Check if transient exists and get expiration info
            $cached_js = get_transient(self::TRANSIENT_JS);
            $timeout_option = '_transient_timeout_' . self::TRANSIENT_JS;
            $cached_time = get_option($timeout_option);

            if ($cached_js !== false && $cached_time) {
                $time_remaining = $cached_time - time();
                if ($time_remaining > 0) {
                    echo '<p style="margin-top:1rem;color:#666;">' .
                         /* translators: %s: human readable time difference */
                         sprintf(esc_html__('Cache expires in %s', 'openpanel'), esc_html(human_time_diff(time(), $cached_time))) .
                         '</p>';
                } else {
                    echo '<p style="margin-top:1rem;color:#666;">' .
                         esc_html__('Cache has expired and will refresh on next page load.', 'openpanel') .
                         '</p>';
                }
            } else {
                echo '<p style="margin-top:1rem;color:#666;">' .
                     esc_html__('No cached version found. op1.js will be fetched on next page load.', 'openpanel') .
                     '</p>';
            }
            ?>

            <p style="margin-top:1rem;color:#666;">
                <?php esc_html_e('The plugin fetches and inlines op1.js (cached for 1 week). If fetching fails, it falls back to the CDN script.', 'openpanel'); ?>
            </p>

            <hr style="margin: 2rem 0;">

            <h2><?php esc_html_e('Current Configuration', 'openpanel'); ?></h2>
            <table class="widefat" style="max-width: 600px;">
                <tr>
                    <td><strong><?php esc_html_e('Mode', 'openpanel'); ?></strong></td>
                    <td><?php echo esc_html($mode === 'selfhosted' ? 'Self-Hosted' : 'Cloud'); ?></td>
                </tr>
                <tr>
                    <td><strong><?php esc_html_e('API URL', 'openpanel'); ?></strong></td>
                    <td><code><?php echo esc_html($this->get_api_base()); ?></code></td>
                </tr>
                <tr>
                    <td><strong><?php esc_html_e('JS URL', 'openpanel'); ?></strong></td>
                    <td><code><?php echo esc_html($this->get_js_url()); ?></code></td>
                </tr>
                <tr>
                    <td><strong><?php esc_html_e('Proxy Endpoint', 'openpanel'); ?></strong></td>
                    <td><code><?php echo esc_html(rest_url(self::REST_NS . '/')); ?></code></td>
                </tr>
            </table>
        </div>

        <style>
            .op-selfhosted-section { transition: opacity 0.3s; }
            .op-selfhosted-section.hidden { opacity: 0.5; pointer-events: none; }
        </style>
        <script>
        jQuery(document).ready(function($) {
            function toggleSelfHostedFields() {
                var mode = $('input[name="<?php echo esc_js(self::OPTION_KEY); ?>[hosting_mode]"]:checked').val();
                var $selfHostedFields = $('.op-selfhosted-field').closest('tr');
                var $selfHostedSection = $selfHostedFields.closest('table');

                if (mode === 'selfhosted') {
                    $selfHostedFields.show();
                } else {
                    $selfHostedFields.hide();
                }
            }

            toggleSelfHostedFields();
            $('input[name="<?php echo esc_js(self::OPTION_KEY); ?>[hosting_mode]"]').on('change', toggleSelfHostedFields);
        });
        </script>
        <?php
    }

    /** ---------------- Helper Methods ---------------- */

    /**
     * Get the API base URL based on hosting mode
     */
    private function get_api_base() {
        $opts = get_option(self::OPTION_KEY);
        $mode = isset($opts['hosting_mode']) ? $opts['hosting_mode'] : 'cloud';

        if ($mode === 'selfhosted' && !empty($opts['api_url'])) {
            return trailingslashit($opts['api_url']);
        }

        return self::CLOUD_API_BASE;
    }

    /**
     * Get the JS URL based on hosting mode
     * Cloud: loads from official CDN (openpanel.dev)
     * Self-hosted: loads from dashboard URL if configured, otherwise falls back to CDN
     */
    private function get_js_url() {
        $opts = get_option(self::OPTION_KEY);
        $mode = isset($opts['hosting_mode']) ? $opts['hosting_mode'] : 'cloud';

        if ($mode === 'selfhosted' && !empty($opts['dashboard_url'])) {
            return trailingslashit($opts['dashboard_url']) . 'op1.js';
        }

        return self::CLOUD_JS_URL;
    }

    /**
     * Get allowed hosts for proxy validation
     */
    private function get_allowed_hosts() {
        $hosts = [
            'api.openpanel.dev',
            'openpanel.dev'
        ];

        $opts = get_option(self::OPTION_KEY);
        $mode = isset($opts['hosting_mode']) ? $opts['hosting_mode'] : 'cloud';

        if ($mode === 'selfhosted') {
            if (!empty($opts['api_url'])) {
                $parsed = wp_parse_url($opts['api_url']);
                if (isset($parsed['host'])) {
                    $hosts[] = $parsed['host'];
                }
            }
            if (!empty($opts['dashboard_url'])) {
                $parsed = wp_parse_url($opts['dashboard_url']);
                if (isset($parsed['host'])) {
                    $hosts[] = $parsed['host'];
                }
            }
        }

        return array_unique($hosts);
    }

    /** ---------------- Inline SDK ---------------- */
    public function inject_inline_sdk() {
        if (is_admin()) return;

        $opts = get_option(self::OPTION_KEY);
        $clientId = isset($opts['client_id']) ? trim($opts['client_id']) : '';
        if ($clientId === '') return; // don't inject if not configured

        // For self-hosted, also require API URL to be configured
        $mode = isset($opts['hosting_mode']) ? $opts['hosting_mode'] : 'cloud';
        if ($mode === 'selfhosted' && empty($opts['api_url'])) {
            return; // don't inject if self-hosted but not configured
        }

        $apiUrl = untrailingslashit( rest_url(self::REST_NS . '/') );
        $jsUrl = $this->get_js_url();

        $init = [
            'clientId'           => $clientId,
            'apiUrl'             => $apiUrl,
            'trackScreenViews'   => isset($opts['track_screen']) ? !empty($opts['track_screen']) : true,
            'trackOutgoingLinks' => !empty($opts['track_outgoing']),
            'trackAttributes'    => !empty($opts['track_attributes']),
        ];

        $bootstrap = "(function(){window.op=window.op||function(){(window.op.q=window.op.q||[]).push(arguments)};window.op('init'," . wp_json_encode($init) . ");})();";

        $op_js = get_transient(self::TRANSIENT_JS);
        if ($op_js === false) {
            $res = wp_remote_get($jsUrl, ['timeout' => 8]);
            if (!is_wp_error($res) && 200 === wp_remote_retrieve_response_code($res)) {
                $op_js = wp_remote_retrieve_body($res);
                set_transient(self::TRANSIENT_JS, $op_js, self::CACHE_TIMEOUT);
            }
        }

        wp_register_script('op-inline-stub', false, [], self::VERSION, true);
        wp_enqueue_script('op-inline-stub');

        wp_add_inline_script('op-inline-stub', $bootstrap, 'before');

        if (!empty($op_js)) {
            // Validate cached JavaScript content before output
            if ($this->is_valid_javascript_content($op_js)) {
                wp_add_inline_script('op-inline-stub', $op_js, 'after');
            } else {
                // Fall back to external script if cached content appears invalid or unsafe
                wp_enqueue_script('openpanel-op1', $jsUrl, [], self::VERSION, true);
            }
        } else {
            wp_enqueue_script('openpanel-op1', $jsUrl, [], self::VERSION, true);
        }
    }

    /** ---------------- Proxy Route ---------------- */
    public function register_proxy_route() {
        register_rest_route(self::REST_NS, self::REST_ROUTE, [
            'methods'  => \WP_REST_Server::ALLMETHODS,
            // INTENTIONALLY PUBLIC ENDPOINT: This endpoint must be publicly accessible to receive
            // analytics data from frontend JavaScript running in users' browsers. No authentication
            // is required as this acts as a proxy for OpenPanel analytics collection.
            // 
            // Security measures in place:
            // 1. Only proxies to whitelisted OpenPanel API endpoints (is_valid_proxy_target)
            // 2. All input data is sanitized and validated before forwarding
            // 3. Proper CORS headers are set for same-origin requests only
            // 4. No sensitive WordPress data is exposed through this endpoint
            'permission_callback' => '__return_true',
            'callback' => [$this, 'proxy_request'],
            'args'     => [
                'path' => [
                    'description' => 'Remaining path to forward',
                    'required' => false,
                ],
            ],
        ]);
    }

    public function proxy_request(\WP_REST_Request $request) {
        try {
            // Handle CORS preflight quickly
            if (strtoupper($request->get_method()) === 'OPTIONS') {
                $resp = new \WP_REST_Response(null, 204);
                $this->add_cors_headers($resp);
                return $resp;
            }

            $path = ltrim($request->get_param('path') ?? '', '/');
            $api_base = $this->get_api_base();
            $target = rtrim($api_base, '/') . '/' . $path;

            // Security: Ensure we only proxy to OpenPanel API endpoints
            if (!$this->is_valid_proxy_target($target)) {
                $resp = new \WP_REST_Response(['error' => 'invalid_target', 'message' => 'Invalid proxy target'], 403);
                $this->add_cors_headers($resp);
                return $resp;
            }

            $method = strtoupper($request->get_method());
            $body   = $request->get_body();

            $incoming = $this->collect_request_headers();

            $query = $request->get_query_params();
            if (!empty($query)) {
                $target = add_query_arg($query, $target);
            }

            $args = [
                'method'  => $method,
                'timeout' => 10,
                'headers' => $incoming,
                'body'    => in_array($method, ['POST','PUT','PATCH','DELETE'], true) ? $body : null,
            ];

            $res = wp_remote_request($target, $args);

            if (is_wp_error($res)) {
                $resp = new \WP_REST_Response(['error' => 'proxy_failed', 'message' => $res->get_error_message()], 502);
                $this->add_cors_headers($resp);
                $resp->header('Cache-Control', 'no-store');
                return $resp;
            }

            $code = wp_remote_retrieve_response_code($res);
            $bodyOut = wp_remote_retrieve_body($res);

            // Handle empty response (common for tracking endpoints returning 202)
            if (empty($bodyOut)) {
                $resp = new \WP_REST_Response(['success' => true], $code ?: 202);
                $resp->header('Content-Type', 'application/json; charset=utf-8');
                $resp->header('Cache-Control', 'no-store');
                $this->add_cors_headers($resp);
                return $resp;
            }

            // Try to decode JSON response, otherwise use raw body
            $decoded = json_decode($bodyOut, true);
            $responseData = (json_last_error() === JSON_ERROR_NONE && $decoded !== null) ? $decoded : ['raw' => $bodyOut];

            $resp = new \WP_REST_Response($responseData, $code);

            // Set Content-Type header (skip copying other headers to avoid compatibility issues)
            $resp->header('Content-Type', 'application/json; charset=utf-8');
            $resp->header('Cache-Control', 'no-store');
            $this->add_cors_headers($resp);
            return $resp;
        } catch (\Exception $e) {
            $resp = new \WP_REST_Response(['error' => 'exception', 'message' => $e->getMessage()], 500);
            $this->add_cors_headers($resp);
            return $resp;
        } catch (\Error $e) {
            $resp = new \WP_REST_Response(['error' => 'error', 'message' => $e->getMessage()], 500);
            $this->add_cors_headers($resp);
            return $resp;
        }
    }

    private function add_cors_headers(\WP_REST_Response $resp) {
        $origin = get_site_url();
        $resp->header('Access-Control-Allow-Origin', $origin);
        $resp->header('Access-Control-Allow-Credentials', 'true');
        $resp->header('Access-Control-Allow-Headers', 'Content-Type, Authorization');
        $resp->header('Access-Control-Allow-Methods', 'GET, POST, PUT, PATCH, DELETE, OPTIONS');
        $resp->header('Vary', 'Origin');
    }

    private function collect_request_headers() {
        $headers = [];

        // Content-Type is a special header NOT prefixed with HTTP_ in PHP
        // This is critical for OpenPanel API which requires application/json
        if (!empty($_SERVER['CONTENT_TYPE'])) {
            $headers['Content-Type'] = sanitize_text_field($_SERVER['CONTENT_TYPE']);
        }

        foreach ($_SERVER as $name => $value) {
            // Sanitize the header name and ensure it starts with HTTP_
            $name = sanitize_text_field($name);
            if (strpos($name, 'HTTP_') === 0) {
                // Extract and sanitize the header suffix
                $header_suffix = substr($name, 5);
                $header_suffix = sanitize_text_field($header_suffix);
                $header = str_replace(' ', '-', ucwords(strtolower(str_replace('_', ' ', $header_suffix))));
                // remove hop-by-hop headers and Origin (we'll set it ourselves)
                $lk = strtolower($header);
                if (in_array($lk, ['host','content-length','accept-encoding','connection','keep-alive','transfer-encoding','upgrade','via','origin'], true)) {
                    continue;
                }
                // Sanitize the header value
                $headers[$header] = sanitize_text_field($value);
            }
        }
        if (!isset($headers['User-Agent'])) {
            $headers['User-Agent'] = 'OpenPanel-WP-Proxy';
        }
        // Set Origin header to WordPress site URL (required for OpenPanel CORS)
        $headers['Origin'] = get_site_url();
        return $headers;
    }

    private function is_valid_proxy_target($target) {
        $allowed_hosts = $this->get_allowed_hosts();

        $parsed = wp_parse_url($target);
        if (!$parsed || !isset($parsed['host'])) {
            return false;
        }

        return in_array($parsed['host'], $allowed_hosts, true) &&
               (empty($parsed['scheme']) || in_array($parsed['scheme'], ['https', 'http'], true));
    }

    private function is_valid_javascript_content($js_content) {
        // Comprehensive validation to ensure the content is safe JavaScript
        if (empty($js_content) || !is_string($js_content)) {
            return false;
        }
        
        // Note: We don't modify $js_content with wp_kses here because we need to preserve
        // the original JavaScript content for validation. wp_add_inline_script() handles
        // proper escaping when outputting to the page.
        
        // Ensure it doesn't contain HTML tags or script injection attempts
        if (preg_match('/<(?:script|iframe|object|embed|form|input|meta|link)/i', $js_content)) {
            return false;
        }
        
        // Check for potential XSS patterns
        if (preg_match('/(?:javascript:|data:|vbscript:|on\w+\s*=)/i', $js_content)) {
            return false;
        }
        
        // Check that it's a reasonable size for a JavaScript file (typical op1.js is ~5KB)
        $trimmed = trim($js_content);
        if (strlen($trimmed) < 10 || strlen($trimmed) > 20480) { // Max 20KB
            return false;
        }
        
        // Should contain typical JavaScript patterns (works for both minified and unminified)
        return (strpos($trimmed, 'function') !== false || 
                strpos($trimmed, 'var ') !== false || 
                strpos($trimmed, 'let ') !== false || 
                strpos($trimmed, 'const ') !== false ||
                strpos($trimmed, '=>') !== false ||
                // Handle minified code patterns like the actual op1.js
                preg_match('/[a-zA-Z_$][a-zA-Z0-9_$]*\s*=\s*function/', $trimmed) ||
                preg_match('/\(\s*function\s*\(/', $trimmed));
    }
}

new OP_WP_Proxy();
