#!/usr/bin/env python3
"""
Test authentication logic for different tool types
"""


def test_tool_detection():
    """Test tool type detection logic"""

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
        # (tool_name, expected_is_unified, expected_is_system, expected_skip_check, expected_project_id)
        ("wordpress_list_posts", True, False, True, "*"),
        ("woocommerce_list_products", True, False, True, "*"),
        ("mcp__coolify-projects__wordpress_get_post", True, False, True, "*"),
        ("mcp__coolify-projects__woocommerce_create_order", True, False, True, "*"),
        ("mcp__coolify-projects__list_projects", False, True, False, "*"),
        ("mcp__coolify-projects__get_system_metrics", False, True, False, "*"),
        ("mcp__coolify-projects__check_all_projects_health", False, True, False, "*"),
        ("list_projects", False, True, False, "*"),
        ("get_system_uptime", False, True, False, "*"),
        (
            "some_unknown_tool",
            False,
            False,
            True,
            "*",
        ),  # Unknown - allow for backward compatibility
    ]

    print("Testing tool detection logic:\n")
    print(
        f"{'Tool Name':<50} {'Unified':<10} {'System':<10} {'Skip Check':<12} {'Project ID':<12} {'Result'}"
    )
    print("-" * 110)

    all_passed = True
    for tool_name, exp_unified, exp_system, exp_skip, exp_project in test_cases:
        # Apply the logic
        is_unified_tool = (
            tool_name.startswith("wordpress_")
            or tool_name.startswith("woocommerce_")
            or tool_name.startswith("mcp__coolify-projects__wordpress_")
            or tool_name.startswith("mcp__coolify-projects__woocommerce_")
        )
        is_system_tool = any(tool_name.endswith(st) for st in SYSTEM_TOOLS)

        if is_unified_tool:
            skip_project_check = True
            project_id = "*"
        elif is_system_tool:
            skip_project_check = False
            project_id = "*"
        else:
            skip_project_check = True
            project_id = "*"

        # Check results
        passed = (
            is_unified_tool == exp_unified
            and is_system_tool == exp_system
            and skip_project_check == exp_skip
            and project_id == exp_project
        )

        status = "✅ PASS" if passed else "❌ FAIL"
        if not passed:
            all_passed = False

        print(
            f"{tool_name:<50} {str(is_unified_tool):<10} {str(is_system_tool):<10} "
            f"{str(skip_project_check):<12} {project_id:<12} {status}"
        )

    print("\n" + "=" * 110)
    if all_passed:
        print("✅ All tests passed!")
    else:
        print("❌ Some tests failed!")

    return all_passed


def test_auth_scenarios():
    """Test authentication scenarios"""

    print("\n\nTesting authentication scenarios:\n")
    print(f"{'Scenario':<60} {'Expected Result':<30} {'Status'}")
    print("-" * 110)

    scenarios = [
        # (description, key_project_id, tool_is_unified, tool_is_system, expected_result)
        (
            "Per-project key + Unified WP tool",
            "wordpress_site1",
            True,
            False,
            "✅ Allow (skip_project_check=True)",
        ),
        (
            "Per-project key + System tool",
            "wordpress_site1",
            False,
            True,
            "❌ Reject (key.project_id != '*')",
        ),
        (
            "Global key (*) + Unified WP tool",
            "*",
            True,
            False,
            "✅ Allow (skip_project_check=True)",
        ),
        ("Global key (*) + System tool", "*", False, True, "✅ Allow (key.project_id == '*')"),
        (
            "Per-project key + Unknown tool",
            "wordpress_site1",
            False,
            False,
            "✅ Allow (backward compatibility)",
        ),
        ("Global key (*) + Unknown tool", "*", False, False, "✅ Allow"),
    ]

    for desc, key_project_id, is_unified, is_system, expected in scenarios:
        # Determine skip_project_check based on tool type
        if is_unified:
            skip_project_check = True
        elif is_system:
            skip_project_check = False
        else:
            skip_project_check = True

        # Simulate validate_key check
        project_id = "*"  # Always "*" in our new logic

        # Check if key would be validated
        if skip_project_check:
            # Skip project check - key is valid regardless
            would_pass_validate = True
            reason = "skip_project_check=True"
        else:
            # Check project access
            if key_project_id == "*" or key_project_id == project_id:
                would_pass_validate = True
                reason = f"key.project_id={key_project_id} matches project_id={project_id}"
            else:
                would_pass_validate = False
                reason = f"key.project_id={key_project_id} != project_id={project_id}"

        # Additional check for system tools
        if is_system and key_project_id != "*":
            would_pass_validate = False
            reason = "System tools require global key (additional check)"

        result = "✅ Allow" if would_pass_validate else "❌ Reject"
        status = "✅ PASS" if (result in expected) else "❌ FAIL"

        print(f"{desc:<60} {result:<30} {status}")
        if status == "❌ FAIL":
            print(f"  └─ Expected: {expected}")
            print(f"  └─ Reason: {reason}")

    print("\n" + "=" * 110)


if __name__ == "__main__":
    test_tool_detection()
    test_auth_scenarios()
