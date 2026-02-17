#!/usr/bin/env python3
"""
Quick test to verify per-project API key isolation.

This test checks that:
1. Per-project API key can access its own project
2. Per-project API key CANNOT access other projects
3. Global API key can access all projects
"""

import asyncio
import os

# Mock setup
os.environ["MASTER_API_KEY"] = "test_master_key_123"
os.environ["WORDPRESS_SITE1_URL"] = "https://site1.example.com"
os.environ["WORDPRESS_SITE1_USERNAME"] = "admin"
os.environ["WORDPRESS_SITE1_APP_PASSWORD"] = "password1"
os.environ["WORDPRESS_SITE4_URL"] = "https://site4.example.com"
os.environ["WORDPRESS_SITE4_USERNAME"] = "admin"
os.environ["WORDPRESS_SITE4_APP_PASSWORD"] = "password4"

# Import after env setup
from core.api_keys import get_api_key_manager
from core.project_manager import get_project_manager
from core.site_registry import get_site_registry
from core.unified_tools import UnifiedToolGenerator

print("=" * 60)
print("Testing Per-Project API Key Isolation")
print("=" * 60)

# Initialize
api_key_manager = get_api_key_manager()
project_manager = get_project_manager()
site_registry = get_site_registry()

# Discover sites
from plugins import registry as plugin_registry

plugin_types = plugin_registry.get_registered_types()
site_registry.discover_sites(plugin_types)

print(f"\nDiscovered sites: {list(site_registry.sites.keys())}")

# Create API keys
print("\n1. Creating API keys...")

# Global key
global_key = api_key_manager.create_key(
    project_id="*", scope="admin", description="Global test key"
)
print(f"   ✓ Global key created: {global_key}")

# Per-project key for wordpress_site4
site4_key = api_key_manager.create_key(
    project_id="wordpress_site4", scope="admin", description="Site4 only key"
)
print(f"   ✓ Site4 key created: {site4_key}")

# Create unified tool generator
unified_gen = UnifiedToolGenerator(project_manager)
unified_tools = unified_gen.generate_all_unified_tools()
print(f"\n2. Generated {len(unified_tools)} unified tools")

# Find wordpress_list_posts tool
list_posts_tool = None
for tool in unified_tools:
    if tool["name"] == "wordpress_list_posts":
        list_posts_tool = tool
        break

if not list_posts_tool:
    print("   ✗ wordpress_list_posts tool not found!")
    exit(1)

print("   ✓ Found wordpress_list_posts tool")


async def test_access(key_token, site_id, expected_result):
    """Test if a key can access a site"""
    from server import _api_key_context

    # Validate key and set context (simulating middleware)
    key_id = api_key_manager.validate_key(
        key_token, project_id="*", required_scope="read", skip_project_check=True
    )

    if key_id:
        key = api_key_manager.keys.get(key_id)
        _api_key_context.set(
            {
                "key_id": key_id,
                "project_id": key.project_id,
                "scope": key.scope,
                "is_global": key.project_id == "*",
            }
        )

    # Try to call the handler
    handler = list_posts_tool["handler"]
    result = await handler(site=site_id, per_page=1)

    # Check result
    is_error = isinstance(result, str) and result.startswith("Error: Access denied")

    if expected_result == "allowed":
        if not is_error:
            print("   ✓ Access allowed as expected")
            return True
        else:
            print("   ✗ FAIL: Access denied but should be allowed!")
            print(f"     Result: {result[:100]}")
            return False
    else:  # expected_result == "denied"
        if is_error:
            print("   ✓ Access denied as expected")
            return True
        else:
            print("   ✗ FAIL: Access allowed but should be denied!")
            print(f"     Result: {result[:100] if isinstance(result, str) else str(result)[:100]}")
            return False


async def run_tests():
    """Run all test cases"""
    print("\n3. Testing access control...")

    all_pass = True

    # Test 1: Per-project key accessing its own project
    print("\n   Test 1: Per-project key (site4) → site4")
    all_pass &= await test_access(site4_key, "site4", "allowed")

    # Test 2: Per-project key accessing different project
    print("\n   Test 2: Per-project key (site4) → site1")
    all_pass &= await test_access(site4_key, "site1", "denied")

    # Test 3: Global key accessing any project
    print("\n   Test 3: Global key → site1")
    all_pass &= await test_access(global_key, "site1", "allowed")

    print("\n   Test 4: Global key → site4")
    all_pass &= await test_access(global_key, "site4", "allowed")

    return all_pass


# Run tests
result = asyncio.run(run_tests())

print("\n" + "=" * 60)
if result:
    print("✅ All tests PASSED!")
    print("Per-project API key isolation is working correctly!")
else:
    print("❌ Some tests FAILED!")
    print("Per-project API key isolation has issues!")
print("=" * 60)

exit(0 if result else 1)
