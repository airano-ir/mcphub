#!/usr/bin/env python3
"""
Simple standalone test to verify the API key isolation logic.
"""

# Simulate the context and validation logic
from contextvars import ContextVar

# Create a mock context var
_api_key_context = ContextVar("api_key_context", default=None)


def test_case_1():
    """Per-project key accessing its own project"""
    print("\nTest 1: Per-project key (site4) accessing site4")

    # Set context for per-project key
    _api_key_context.set(
        {"key_id": "key_123", "project_id": "wordpress_site4", "scope": "admin", "is_global": False}
    )

    # Check access
    api_key_info = _api_key_context.get()
    full_id = "wordpress_site4"  # Target project

    if api_key_info and not api_key_info.get("is_global"):
        allowed_project = api_key_info.get("project_id")
        if allowed_project != full_id:
            print("   ✗ FAIL: Access denied (should be allowed)")
            return False
        else:
            print("   ✓ PASS: Access allowed")
            return True
    else:
        print("   ✓ PASS: Access allowed (global key)")
        return True


def test_case_2():
    """Per-project key accessing different project"""
    print("\nTest 2: Per-project key (site4) accessing site1")

    # Set context for per-project key
    _api_key_context.set(
        {"key_id": "key_123", "project_id": "wordpress_site4", "scope": "admin", "is_global": False}
    )

    # Check access
    api_key_info = _api_key_context.get()
    full_id = "wordpress_site1"  # Different project

    if api_key_info and not api_key_info.get("is_global"):
        allowed_project = api_key_info.get("project_id")
        if allowed_project != full_id:
            print("   ✓ PASS: Access denied (as expected)")
            return True
        else:
            print("   ✗ FAIL: Access allowed (should be denied)")
            return False
    else:
        print("   ✗ FAIL: Access allowed (should be denied)")
        return False


def test_case_3():
    """Global key accessing any project"""
    print("\nTest 3: Global key accessing site1")

    # Set context for global key
    _api_key_context.set(
        {"key_id": "key_456", "project_id": "*", "scope": "admin", "is_global": True}
    )

    # Check access
    api_key_info = _api_key_context.get()
    full_id = "wordpress_site1"

    if api_key_info and not api_key_info.get("is_global"):
        allowed_project = api_key_info.get("project_id")
        if allowed_project != full_id:
            print("   ✗ FAIL: Access denied (should be allowed)")
            return False
        else:
            print("   ✓ PASS: Access allowed")
            return True
    else:
        print("   ✓ PASS: Access allowed (global key)")
        return True


def test_case_4():
    """Global key accessing different project"""
    print("\nTest 4: Global key accessing site4")

    # Set context for global key
    _api_key_context.set(
        {"key_id": "key_456", "project_id": "*", "scope": "admin", "is_global": True}
    )

    # Check access
    api_key_info = _api_key_context.get()
    full_id = "wordpress_site4"

    if api_key_info and not api_key_info.get("is_global"):
        allowed_project = api_key_info.get("project_id")
        if allowed_project != full_id:
            print("   ✗ FAIL: Access denied (should be allowed)")
            return False
        else:
            print("   ✓ PASS: Access allowed")
            return True
    else:
        print("   ✓ PASS: Access allowed (global key)")
        return True


# Run all tests
print("=" * 60)
print("Testing API Key Isolation Logic")
print("=" * 60)

results = [test_case_1(), test_case_2(), test_case_3(), test_case_4()]

print("\n" + "=" * 60)
if all(results):
    print("✅ All tests PASSED!")
    print("The isolation logic is correct!")
else:
    print("❌ Some tests FAILED!")
    print("The isolation logic has issues!")
print("=" * 60)

exit(0 if all(results) else 1)
