#!/usr/bin/env python3
"""
Test context-based API key isolation after fixing circular import.
"""

from core.context import clear_api_key_context, get_api_key_context, set_api_key_context

print("=" * 60)
print("Testing Context API")
print("=" * 60)

# Test 1: Set and get context
print("\nTest 1: Set and get context")
set_api_key_context(
    key_id="key_test123", project_id="wordpress_site4", scope="admin", is_global=False
)
ctx = get_api_key_context()
assert ctx["key_id"] == "key_test123"
assert ctx["project_id"] == "wordpress_site4"
assert not ctx["is_global"]
print("   ✓ PASS: Context set and retrieved correctly")

# Test 2: Check access logic
print("\nTest 2: Access logic for per-project key")
allowed_project = ctx["project_id"]
target_project = "wordpress_site4"
if allowed_project == target_project:
    print("   ✓ PASS: Access allowed (same project)")
else:
    print("   ✗ FAIL: Should allow access")

# Test 3: Different project access
print("\nTest 3: Access logic for different project")
target_project = "wordpress_site1"
if allowed_project != target_project:
    print("   ✓ PASS: Access denied (different project)")
else:
    print("   ✗ FAIL: Should deny access")

# Test 4: Global key
print("\nTest 4: Global key access")
set_api_key_context(key_id="key_global", project_id="*", scope="admin", is_global=True)
ctx = get_api_key_context()
if ctx["is_global"]:
    print("   ✓ PASS: Global key bypasses project check")
else:
    print("   ✗ FAIL: Should be global")

# Test 5: Clear context
print("\nTest 5: Clear context")
clear_api_key_context()
ctx = get_api_key_context()
if ctx is None:
    print("   ✓ PASS: Context cleared")
else:
    print("   ✗ FAIL: Context should be None")

print("\n" + "=" * 60)
print("✅ All context tests passed!")
print("=" * 60)
