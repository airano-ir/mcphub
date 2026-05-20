#!/usr/bin/env bash
# Pre-submission checks for airano-mcp-bridge (wp.org-bound version).
#
# Run from the repo root or from this directory:
#   bash wordpress-plugin/airano-mcp-bridge-wporg/tests/check.sh
#
# Exit code is non-zero on any FAIL. Prints a one-line summary at the end.
set -u

PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/airano-mcp-bridge"
PHP_FILE="${PLUGIN_DIR}/airano-mcp-bridge.php"
README_TXT="${PLUGIN_DIR}/readme.txt"

fail=0
pass() { printf '  \033[32mPASS\033[0m %s\n' "$1"; }
fail() { printf '  \033[31mFAIL\033[0m %s\n' "$1"; fail=$((fail+1)); }
section() { printf '\n\033[1m%s\033[0m\n' "$1"; }

[ -f "$PHP_FILE" ] || { echo "main PHP file not found: $PHP_FILE"; exit 2; }
[ -f "$README_TXT" ] || { echo "readme.txt not found: $README_TXT"; exit 2; }

section "1. PHP syntax (php -l)"
if php -l "$PHP_FILE" > /tmp/phplint.out 2>&1; then
    pass "syntax clean"
else
    fail "php -l reported errors:"
    cat /tmp/phplint.out
fi

section "2. Plugin headers"
ver_php=$(grep -oE '^\s*\*\s*Version:\s*\S+' "$PHP_FILE" | head -1 | awk '{print $NF}')
ver_const=$(grep -oE "const VERSION\s*=\s*'[^']+'" "$PHP_FILE" | head -1 | grep -oE "'[^']+'" | tr -d "'")
stable=$(grep -oE '^Stable tag:\s*\S+' "$README_TXT" | awk '{print $NF}')
tested=$(grep -oE '^Tested up to:\s*\S+' "$README_TXT" | awk '{print $NF}')
plugin_uri=$(grep -oE '^\s*\*\s*Plugin URI:\s*\S+' "$PHP_FILE" | head -1 | awk '{print $NF}')
author_uri=$(grep -oE '^\s*\*\s*Author URI:\s*\S+' "$PHP_FILE" | head -1 | awk '{print $NF}')

[ "$ver_php" = "$ver_const" ] && pass "Version header == const VERSION ($ver_php)" || fail "Version mismatch: header=$ver_php const=$ver_const"
[ "$ver_php" = "$stable" ] && pass "Version header == readme.txt Stable tag ($ver_php)" || fail "Stable tag mismatch: $ver_php vs $stable"
case "$tested" in
    *.*.*) fail "Tested up to has minor version ($tested) — wp.org rejects this. Use major.minor only." ;;
    *.*) pass "Tested up to is major.minor ($tested)" ;;
    *) fail "Tested up to has unexpected format: $tested" ;;
esac
[ -n "$plugin_uri" ] && [ -n "$author_uri" ] && [ "$plugin_uri" != "$author_uri" ] \
    && pass "Plugin URI ($plugin_uri) and Author URI ($author_uri) are distinct" \
    || fail "Plugin URI and Author URI are the same or missing"

section "3. wp.org review issues from review email"
# Class name must use the Airano_MCP_ prefix (no generic SEO_API_Bridge)
if grep -q "^class SEO_API_Bridge" "$PHP_FILE"; then
    fail "main class still named SEO_API_Bridge — wp.org rejects generic prefixes"
else
    pass "main class is not the generic SEO_API_Bridge"
fi
if grep -q "^class Airano_MCP_Bridge" "$PHP_FILE"; then
    pass "main class uses the Airano_MCP_ prefix"
else
    fail "main class is not Airano_MCP_Bridge"
fi
# (a) media.php must NOT be loaded directly outside of the comment/changelog
includes=$(grep -nE "^\s*require(_once)?\s*\(?\s*ABSPATH\s*\.\s*['\"]wp-admin/includes/media\.php" "$PHP_FILE" | wc -l)
if [ "$includes" -eq 0 ]; then
    pass "no direct require of wp-admin/includes/media.php"
else
    fail "found $includes direct require(_once) of wp-admin/includes/media.php"
    grep -nE "^\s*require(_once)?\s*\(?\s*ABSPATH\s*\.\s*['\"]wp-admin/includes/media\.php" "$PHP_FILE"
fi

# (b) /upload-and-attach must use the new dedicated permission_callback
if grep -q "'permission_callback' => \[\$this, 'require_upload_and_attach_capability'\]" "$PHP_FILE"; then
    pass "/upload-and-attach is gated by require_upload_and_attach_capability"
else
    fail "/upload-and-attach does not use require_upload_and_attach_capability"
fi
if grep -q "function require_upload_and_attach_capability" "$PHP_FILE"; then
    pass "require_upload_and_attach_capability method is defined"
else
    fail "require_upload_and_attach_capability method is missing"
fi
# It must call current_user_can('edit_post', $attach_to_post)
if grep -q "current_user_can('edit_post', \$attach_to_post)" "$PHP_FILE"; then
    pass "edit_post per-target check is enforced at the route gate"
else
    fail "edit_post per-target check is missing"
fi

section "4. REST routes — every register_rest_route has a permission_callback"
# Walk the file and check each register_rest_route(...) block individually.
# A block runs from its register_rest_route line up to the matching closing
# `]);` at the same brace depth. We check each block contains
# `permission_callback`.
audit=$(php -r '
$src = file_get_contents($argv[1]);
$lines = preg_split("/\r?\n/", $src);
$total = 0; $missing = 0; $missing_lines = [];
$inBlock = false; $depth = 0; $hasPerm = false; $startLine = 0;
foreach ($lines as $i => $line) {
    $lineNo = $i + 1;
    if (!$inBlock && preg_match("/register_rest_route\s*\(/", $line)) {
        $inBlock = true; $depth = 0; $hasPerm = false; $startLine = $lineNo; $total++;
    }
    if ($inBlock) {
        if (strpos($line, "permission_callback") !== false) $hasPerm = true;
        $depth += substr_count($line, "[") + substr_count($line, "(");
        $depth -= substr_count($line, "]") + substr_count($line, ")");
        if ($depth <= 0 && $lineNo > $startLine) {
            if (!$hasPerm) { $missing++; $missing_lines[] = $startLine; }
            $inBlock = false;
        }
    }
}
echo "$total $missing " . implode(",", $missing_lines);
' "$PHP_FILE")
total=$(echo "$audit" | awk '{print $1}')
missing=$(echo "$audit" | awk '{print $2}')
missing_lines=$(echo "$audit" | awk '{print $3}')
if [ "$missing" -eq 0 ]; then
    pass "all $total REST routes have a permission_callback"
else
    fail "$missing of $total REST routes are missing permission_callback (lines: $missing_lines)"
fi

# No __return_true on routes that change state (POST/PUT/DELETE)
public_writes=$(awk '/register_rest_route/,/\]\s*\)\s*;/' "$PHP_FILE" \
    | grep -B2 "__return_true" \
    | grep -E "'methods'\s*=>\s*'(POST|PUT|DELETE|PATCH)'" \
    | wc -l)
if [ "$public_writes" -eq 0 ]; then
    pass "no public (__return_true) callbacks on POST/PUT/DELETE routes"
else
    fail "$public_writes write routes use __return_true (public) — review needed"
fi

section "5. Output escaping & sanitisation (heuristic — manual review still required)"
# Find raw echo/print of REST request params
raw_echo=$(grep -nE "echo\s+\\\$request->|print\s+\\\$request->" "$PHP_FILE" | wc -l)
[ "$raw_echo" -eq 0 ] && pass "no raw echo of \$request-> values" || fail "$raw_echo raw echoes of \$request->"
# Reject sql concatenation patterns
sql_concat=$(grep -nE '\$wpdb->(query|get_results|get_var|get_row).*\.\s*\$' "$PHP_FILE" | wc -l)
[ "$sql_concat" -eq 0 ] && pass "no obvious SQL concatenation (no \$wpdb-> ... . \$var)" || fail "$sql_concat possible SQL concatenations — manual review"
# eval / system / exec must NOT appear
dangerous=$(grep -nE "\b(eval|exec|system|passthru|popen|shell_exec|proc_open)\s*\(" "$PHP_FILE" | grep -v "^\s*\*" | wc -l)
[ "$dangerous" -eq 0 ] && pass "no eval/exec/system/passthru/popen calls" || fail "$dangerous dangerous function calls"

section "6. Text domain"
td_count=$(grep -cE "(__|_e|_x|_n|esc_html__|esc_attr__|esc_html_e|esc_attr_e)\(\s*['\"]" "$PHP_FILE")
non_plugin_td=$(grep -oE "(__|_e|_x|_n|esc_html__|esc_attr__|esc_html_e|esc_attr_e)\(\s*['\"][^'\"]*['\"]\s*,\s*['\"][^'\"]+['\"]" "$PHP_FILE" \
    | grep -oE "['\"][^'\"]+['\"]\s*\)\s*$" | grep -vc "airano-mcp-bridge" || true)
if [ "$non_plugin_td" -eq 0 ]; then
    pass "$td_count translation calls all use 'airano-mcp-bridge' domain"
else
    fail "$non_plugin_td translation calls use a non-plugin text domain"
fi

section "7. Direct file access guard"
if grep -q "if (!defined('ABSPATH'))" "$PHP_FILE" && grep -q "exit;" "$PHP_FILE"; then
    pass "ABSPATH guard present"
else
    fail "missing 'if (!defined(ABSPATH)) exit;' guard"
fi

section "Summary"
if [ "$fail" -eq 0 ]; then
    printf '\033[32m✓ all checks passed\033[0m — version %s ready for wp.org review reply\n' "$ver_php"
    exit 0
else
    printf '\033[31m✗ %d check(s) failed\033[0m\n' "$fail"
    exit 1
fi
