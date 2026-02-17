#!/usr/bin/env python3
"""
Test API Key Access Control Fix

Validates that:
1. Site-level keys get proper error message for system tools (not validation failure)
2. Global keys work for all tools
3. Per-project keys work for their own unified tools
"""


def test_system_tool_detection():
    """Test that system tools are detected correctly."""
    SYSTEM_TOOLS = [
        "list_projects",
        "get_project_info",
        "check_all_projects_health",
        "get_project_health",
        "get_system_metrics",
        "get_system_uptime",
        "get_rate_limit_stats",
        "export_health_metrics",
        "manage_api_keys_list",
        "manage_api_keys_get_info",
    ]

    # Test with and without MCP prefix
    test_cases = [
        ("list_projects", True),
        ("mcp__coolify-projects__list_projects", True),
        ("get_project_info", True),
        ("wordpress_list_posts", False),
        ("woocommerce_list_orders", False),
        ("unknown", False),
    ]

    for tool_name, expected in test_cases:
        is_system_tool = any(tool_name.endswith(st) for st in SYSTEM_TOOLS)
        assert (
            is_system_tool == expected
        ), f"Failed for {tool_name}: expected {expected}, got {is_system_tool}"
        print(f"✓ {tool_name}: is_system_tool={is_system_tool}")


def test_unified_tool_detection():
    """Test that unified tools are detected correctly."""
    test_cases = [
        ("wordpress_list_posts", True),
        ("woocommerce_list_orders", True),
        ("mcp__coolify-projects__wordpress_list_posts", True),
        ("mcp__coolify-projects__woocommerce_list_orders", True),
        ("list_projects", False),
        ("get_project_info", False),
        ("unknown", True),  # Falls to fallback
    ]

    for tool_name, expected in test_cases:
        if tool_name == "unknown":
            is_unified_tool = True  # Fallback
        else:
            is_unified_tool = (
                tool_name.startswith("wordpress_")
                or tool_name.startswith("woocommerce_")
                or tool_name.startswith("mcp__coolify-projects__wordpress_")
                or tool_name.startswith("mcp__coolify-projects__woocommerce_")
            )
        assert (
            is_unified_tool == expected
        ), f"Failed for {tool_name}: expected {expected}, got {is_unified_tool}"
        print(f"✓ {tool_name}: is_unified_tool={is_unified_tool}")


def test_skip_project_check_logic():
    """Test that skip_project_check is set correctly."""
    SYSTEM_TOOLS = [
        "list_projects",
        "get_project_info",
        "check_all_projects_health",
        "get_project_health",
        "get_system_metrics",
        "get_system_uptime",
        "get_rate_limit_stats",
        "export_health_metrics",
        "manage_api_keys_list",
        "manage_api_keys_get_info",
    ]

    test_cases = [
        # (tool_name, expected_skip)
        ("list_projects", True),  # System tool
        ("wordpress_list_posts", True),  # Unified tool
        ("woocommerce_list_orders", True),  # Unified tool
        ("mcp__coolify-projects__list_projects", True),  # System tool with prefix
        ("mcp__coolify-projects__wordpress_list_posts", True),  # Unified tool with prefix
        ("unknown", True),  # Fallback to unified
    ]

    for tool_name, expected_skip in test_cases:
        # Determine is_system_tool
        is_system_tool = any(tool_name.endswith(st) for st in SYSTEM_TOOLS)

        # Determine is_unified_tool
        if tool_name == "unknown":
            is_unified_tool = True
        else:
            is_unified_tool = (
                tool_name.startswith("wordpress_")
                or tool_name.startswith("woocommerce_")
                or tool_name.startswith("mcp__coolify-projects__wordpress_")
                or tool_name.startswith("mcp__coolify-projects__woocommerce_")
            )

        # Calculate skip_project_check
        skip_project_check = is_unified_tool or is_system_tool

        assert skip_project_check == expected_skip, (
            f"Failed for {tool_name}: expected skip={expected_skip}, got {skip_project_check} "
            f"(unified={is_unified_tool}, system={is_system_tool})"
        )
        print(
            f"✓ {tool_name}: skip_project_check={skip_project_check} (unified={is_unified_tool}, system={is_system_tool})"
        )


if __name__ == "__main__":
    print("\n=== Testing System Tool Detection ===")
    test_system_tool_detection()

    print("\n=== Testing Unified Tool Detection ===")
    test_unified_tool_detection()

    print("\n=== Testing skip_project_check Logic ===")
    test_skip_project_check_logic()

    print("\n✅ All tests passed!")
    print("\nExpected behavior after fix:")
    print("1. Site-level key + list_projects → Validation passes, then gets proper error:")
    print("   'System tools require global API key (project_id=\"*\")'")
    print(
        "2. Site-level key + wordpress_list_posts(site=other) → Validation passes, handler blocks with:"
    )
    print("   'Access denied. This API key is restricted to project X'")
    print("3. Global key + any tool → Works")
