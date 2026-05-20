<?php
/**
 * Standalone tests for require_upload_and_attach_capability without a
 * full WordPress bootstrap. Stubs the few WP globals/functions the
 * permission method touches and walks every gate.
 *
 * Run from the repo root:
 *   php wordpress-plugin/airano-mcp-bridge-wporg/tests/test_permission_callback.php
 *
 * Exit code is non-zero on any FAIL.
 */

// --- Minimal WP shims ----------------------------------------------------
if (!class_exists('WP_Error')) {
    class WP_Error {
        public $code; public $message; public $data;
        public function __construct($code = '', $message = '', $data = '') {
            $this->code = $code; $this->message = $message; $this->data = $data;
        }
    }
}

if (!function_exists('rest_authorization_required_code')) {
    function rest_authorization_required_code() { return 401; }
}

// __() / esc_html__ / etc. just return the string unchanged.
foreach (['__', '_e', '_x', 'esc_html__', 'esc_attr__', 'esc_html_e', 'esc_attr_e'] as $fn) {
    if (!function_exists($fn)) {
        eval("function $fn(\$s, \$d = '') { return \$s; }");
    }
}

// Capability + post-edit lookup is driven by globals so each test can
// configure the scenario.
$GLOBALS['__caps']  = []; // ['upload_files' => true, 'manage_options' => false, ...]
$GLOBALS['__edits'] = []; // [42 => true, 99 => false]

if (!function_exists('current_user_can')) {
    function current_user_can($cap, $object_id = null) {
        if ($cap === 'edit_post' && $object_id !== null) {
            return !empty($GLOBALS['__edits'][$object_id]);
        }
        return !empty($GLOBALS['__caps'][$cap]);
    }
}

// Tiny WP_REST_Request stub — only ->get_param() is used by the gate.
if (!class_exists('WP_REST_Request')) {
    class WP_REST_Request {
        private $params;
        public function __construct(array $params = []) { $this->params = $params; }
        public function get_param($k) { return $this->params[$k] ?? null; }
    }
}

// --- Load just the Airano_MCP_Bridge class -------------------------------
// We can't require the whole plugin (it calls add_action()/add_filter() in
// the global scope on load), so we extract the class body and eval it.
// Strip the two add_action() lines at the bottom.
$src = file_get_contents(__DIR__ . '/../airano-mcp-bridge/airano-mcp-bridge.php');
$src = preg_replace('/<\?php/', '', $src, 1);
$src = preg_replace('/^.*?(if\s*\(!\s*defined.*?ABSPATH.*?\)\s*\{[^}]*\})/s', '', $src, 1);
// Remove any add_action / add_filter calls outside the class.
$src = preg_replace('/^\s*(add_action|add_filter)\s*\([^;]+;\s*$/m', '', $src);
// Remove `new Airano_MCP_Bridge();` invocation.
$src = preg_replace('/^\s*new\s+Airano_MCP_Bridge\s*\(\s*\)\s*;\s*$/m', '', $src);

// WP function shims so the class file can be loaded without bootstrapping
// WordPress. Each returns a benign default — the tests only exercise the
// permission method, not the rest of the plugin.
$_wp_voids = [
    'add_action', 'add_filter', 'do_action', 'register_activation_hook',
    'register_deactivation_hook', 'register_uninstall_hook',
    'load_plugin_textdomain', 'wp_schedule_event', 'wp_clear_scheduled_hook',
];
foreach ($_wp_voids as $fn) {
    if (!function_exists($fn)) {
        eval("function $fn() { return true; }");
    }
}
$_wp_returns_first = ['apply_filters', 'sanitize_text_field', 'sanitize_key', 'wp_unslash'];
foreach ($_wp_returns_first as $fn) {
    if (!function_exists($fn)) {
        eval("function $fn(\$a) { return \$a; }");
    }
}
if (!function_exists('get_option'))    { function get_option($k, $d = false) { return $d; } }
if (!function_exists('update_option')) { function update_option() { return true; } }
if (!function_exists('add_option'))    { function add_option() { return true; } }
if (!function_exists('delete_option')) { function delete_option() { return true; } }
if (!function_exists('wp_next_scheduled')) { function wp_next_scheduled() { return false; } }
if (!function_exists('plugin_dir_path')) { function plugin_dir_path($f) { return dirname($f); } }
if (!function_exists('plugin_basename')) { function plugin_basename($f) { return basename($f); } }
if (!function_exists('untrailingslashit')) { function untrailingslashit($s) { return rtrim($s, '/\\'); } }
if (!function_exists('trailingslashit'))   { function trailingslashit($s) { return rtrim($s, '/\\') . '/'; } }
if (!function_exists('wp_parse_url'))      { function wp_parse_url($u, $c = -1) { return $c === -1 ? parse_url($u) : parse_url($u, $c); } }

eval($src);

// --- Tests ---------------------------------------------------------------
$pass = 0; $fail = 0;
function check($label, $ok, $detail = '') {
    global $pass, $fail;
    if ($ok) { echo "  \033[32mPASS\033[0m $label\n"; $pass++; }
    else     { echo "  \033[31mFAIL\033[0m $label" . ($detail ? " — $detail" : '') . "\n"; $fail++; }
}

$bridge = new Airano_MCP_Bridge();

echo "\n\033[1mrequire_upload_and_attach_capability — gate semantics\033[0m\n";

// 1. No upload_files + no manage_options → forbidden
$GLOBALS['__caps'] = ['upload_files' => false, 'manage_options' => false];
$GLOBALS['__edits'] = [];
$res = $bridge->require_upload_and_attach_capability(new WP_REST_Request([]));
check('caller without upload_files/manage_options is rejected',
    $res instanceof WP_Error && $res->code === 'rest_forbidden');

// 2. Has upload_files, no attach_to_post → allowed (no per-target check)
$GLOBALS['__caps'] = ['upload_files' => true];
$res = $bridge->require_upload_and_attach_capability(new WP_REST_Request([]));
check('upload_files alone, no attach_to_post → true', $res === true,
    is_object($res) ? "got " . $res->code : "got " . var_export($res, true));

// 3. Has upload_files, attach_to_post=42, no edit_post → forbidden
$GLOBALS['__caps'] = ['upload_files' => true];
$GLOBALS['__edits'] = [42 => false];
$res = $bridge->require_upload_and_attach_capability(new WP_REST_Request(['attach_to_post' => 42]));
check('attach_to_post supplied, edit_post denied → rest_cannot_edit',
    $res instanceof WP_Error && $res->code === 'rest_cannot_edit',
    is_object($res) ? "got code: " . $res->code : "got: " . var_export($res, true));

// 4. Has upload_files, attach_to_post=42, edit_post granted → allowed
$GLOBALS['__caps'] = ['upload_files' => true];
$GLOBALS['__edits'] = [42 => true];
$res = $bridge->require_upload_and_attach_capability(new WP_REST_Request(['attach_to_post' => 42]));
check('attach_to_post + edit_post → true', $res === true,
    is_object($res) ? "got " . $res->code : "got " . var_export($res, true));

// 5. set_featured=true without attach_to_post → invalid_param
$GLOBALS['__caps'] = ['upload_files' => true];
$res = $bridge->require_upload_and_attach_capability(new WP_REST_Request(['set_featured' => 'true']));
check('set_featured without attach_to_post → rest_invalid_param',
    $res instanceof WP_Error && $res->code === 'rest_invalid_param');

// 6. set_featured=1 without attach_to_post → invalid_param (numeric string)
$res = $bridge->require_upload_and_attach_capability(new WP_REST_Request(['set_featured' => '1']));
check("set_featured='1' without attach_to_post → rest_invalid_param",
    $res instanceof WP_Error && $res->code === 'rest_invalid_param');

// 7. set_featured=false → does NOT trigger the invalid_param branch
$res = $bridge->require_upload_and_attach_capability(new WP_REST_Request(['set_featured' => 'false']));
check("set_featured='false' (no attach_to_post) → allowed",
    $res === true,
    is_object($res) ? "got " . $res->code : "got " . var_export($res, true));

// 8. set_featured=true + attach_to_post=42 + edit_post=true → allowed
$GLOBALS['__edits'] = [42 => true];
$res = $bridge->require_upload_and_attach_capability(
    new WP_REST_Request(['attach_to_post' => 42, 'set_featured' => 'true']));
check('set_featured=true + attach_to_post + edit_post → true', $res === true);

// 9. manage_options-only caller (no upload_files) is allowed (admins still pass)
$GLOBALS['__caps'] = ['upload_files' => false, 'manage_options' => true];
$GLOBALS['__edits'] = [];
$res = $bridge->require_upload_and_attach_capability(new WP_REST_Request([]));
check('manage_options without upload_files → true', $res === true);

// 10. attach_to_post=0 (defaulted/missing) is treated as "not supplied" — no
// per-target check needed.
$GLOBALS['__caps'] = ['upload_files' => true];
$res = $bridge->require_upload_and_attach_capability(new WP_REST_Request(['attach_to_post' => 0]));
check('attach_to_post=0 → no per-target check, allowed', $res === true);

echo "\n";
if ($fail === 0) {
    echo "\033[32m✓ $pass tests passed\033[0m\n";
    exit(0);
} else {
    echo "\033[31m✗ $fail of " . ($pass + $fail) . " tests failed\033[0m\n";
    exit(1);
}
