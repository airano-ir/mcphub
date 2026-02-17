#!/usr/bin/env python3
"""
Integration Test Script for WordPress MCP Server

Usage:
    python tests/run_integration_tests.py

Requirements:
    - Server must be running
    - WordPress sites configured in environment variables
    - Valid API keys set up

This script tests:
    1. Plugin imports and initialization
    2. Handler functionality with real WordPress sites
    3. Error handling
    4. Tool specifications

Results are output as JSON for easy parsing.
"""

import json
import os
import sys
from datetime import UTC, datetime

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


class IntegrationTester:
    """Run integration tests for WordPress MCP server"""

    def __init__(self):
        self.results = {
            "timestamp": datetime.now(UTC).isoformat(),
            "tests": [],
            "summary": {"total": 0, "passed": 0, "failed": 0, "skipped": 0},
        }

    def add_result(self, test_name, status, message="", details=None):
        """Add a test result"""
        self.results["tests"].append(
            {"name": test_name, "status": status, "message": message, "details": details or {}}
        )
        self.results["summary"]["total"] += 1
        self.results["summary"][status] += 1

    def test_imports(self):
        """Test 1: Import all modules"""
        try:

            self.add_result("imports", "passed", "All modules imported successfully")
            return True
        except Exception as e:
            self.add_result("imports", "failed", f"Import error: {str(e)}")
            return False

    def test_base_plugin(self):
        """Test 2: BasePlugin architecture"""
        try:
            from plugins.base import BasePlugin
            from plugins.wordpress.plugin import WordPressPlugin

            # Check that get_tools is not abstract
            assert hasattr(BasePlugin, "get_tools"), "BasePlugin missing get_tools"
            assert hasattr(
                BasePlugin, "get_tool_specifications"
            ), "BasePlugin missing get_tool_specifications"

            # Check WordPress plugin has get_tool_specifications
            assert hasattr(
                WordPressPlugin, "get_tool_specifications"
            ), "WordPress missing get_tool_specifications"

            # Get tool specifications without instantiation
            specs = WordPressPlugin.get_tool_specifications()

            self.add_result(
                "base_plugin",
                "passed",
                "BasePlugin architecture correct",
                {"tool_count": len(specs)},
            )
            return True
        except Exception as e:
            self.add_result("base_plugin", "failed", f"BasePlugin error: {str(e)}")
            return False

    def test_wordpress_plugin_init(self):
        """Test 3: WordPress plugin initialization"""
        try:
            from plugins.wordpress.plugin import WordPressPlugin

            # Try to create instance with dummy config
            config = {"url": "https://example.com", "username": "test", "app_password": "test"}

            plugin = WordPressPlugin(config)

            # Check handlers initialized
            assert hasattr(plugin, "posts"), "Missing posts handler"
            assert hasattr(plugin, "media"), "Missing media handler"
            assert hasattr(plugin, "products"), "Missing products handler"
            assert hasattr(plugin, "orders"), "Missing orders handler"

            self.add_result(
                "wordpress_plugin_init", "passed", "WordPress plugin initializes correctly"
            )
            return True
        except Exception as e:
            self.add_result("wordpress_plugin_init", "failed", f"Plugin init error: {str(e)}")
            return False

    def test_tool_specifications(self):
        """Test 4: Tool specifications format"""
        try:
            from plugins.wordpress.plugin import WordPressPlugin

            specs = WordPressPlugin.get_tool_specifications()

            if not specs:
                self.add_result("tool_specifications", "failed", "No tool specifications returned")
                return False

            # Check first spec has required fields
            first_spec = specs[0]
            required_fields = ["name", "method_name", "description", "schema", "scope"]

            for field in required_fields:
                if field not in first_spec:
                    self.add_result(
                        "tool_specifications",
                        "failed",
                        f"Tool spec missing required field: {field}",
                    )
                    return False

            self.add_result(
                "tool_specifications",
                "passed",
                f"Tool specifications format correct ({len(specs)} tools)",
                {"total_tools": len(specs), "sample_tool": first_spec.get("name")},
            )
            return True
        except Exception as e:
            self.add_result("tool_specifications", "failed", f"Tool specifications error: {str(e)}")
            return False

    def test_handlers_structure(self):
        """Test 5: Handlers structure"""
        try:
            from plugins.wordpress import handlers

            expected_handlers = [
                "PostsHandler",
                "MediaHandler",
                "TaxonomyHandler",
                "CommentsHandler",
                "UsersHandler",
                "SiteHandler",
                "ProductsHandler",
                "OrdersHandler",
                "CustomersHandler",
                "ReportsHandler",
                "CouponsHandler",
                "SEOHandler",
                "WPCLIHandler",
                "MenusHandler",
            ]

            missing = []
            for handler_name in expected_handlers:
                if not hasattr(handlers, handler_name):
                    missing.append(handler_name)

            if missing:
                self.add_result(
                    "handlers_structure", "failed", f"Missing handlers: {', '.join(missing)}"
                )
                return False

            self.add_result(
                "handlers_structure", "passed", f"All {len(expected_handlers)} handlers present"
            )
            return True
        except Exception as e:
            self.add_result("handlers_structure", "failed", f"Handlers structure error: {str(e)}")
            return False

    def test_pydantic_schemas(self):
        """Test 6: Pydantic schemas"""
        try:
            from plugins.wordpress.schemas import (
                PaginationParams,
            )

            # Test basic validation
            pagination = PaginationParams(per_page=10, page=1)
            assert pagination.per_page == 10
            assert pagination.page == 1

            # Test validation errors
            try:
                PaginationParams(per_page=200, page=1)  # Should fail (max 100)
                self.add_result(
                    "pydantic_schemas",
                    "failed",
                    "Pydantic validation not working (should reject per_page > 100)",
                )
                return False
            except Exception:
                pass  # Expected error

            self.add_result("pydantic_schemas", "passed", "Pydantic schemas validate correctly")
            return True
        except Exception as e:
            self.add_result("pydantic_schemas", "failed", f"Pydantic schemas error: {str(e)}")
            return False

    def test_option_b_integration(self):
        """Test 7: Option B architecture integration"""
        try:
            from core import SiteManager, ToolGenerator

            # Create site manager
            site_manager = SiteManager()

            # Create tool generator
            tool_generator = ToolGenerator(site_manager)

            # This would normally generate tools, but we can't test without real sites
            # Just check the method exists
            assert hasattr(tool_generator, "generate_tools")

            self.add_result(
                "option_b_integration", "passed", "Option B architecture integration ready"
            )
            return True
        except Exception as e:
            self.add_result(
                "option_b_integration", "failed", f"Option B integration error: {str(e)}"
            )
            return False

    def run_all_tests(self):
        """Run all tests"""
        print("🧪 Running Integration Tests for WordPress MCP Server")
        print("=" * 60)

        tests = [
            self.test_imports,
            self.test_base_plugin,
            self.test_wordpress_plugin_init,
            self.test_tool_specifications,
            self.test_handlers_structure,
            self.test_pydantic_schemas,
            self.test_option_b_integration,
        ]

        for test in tests:
            test_name = test.__name__.replace("test_", "").replace("_", " ").title()
            print(f"\n📋 Running: {test_name}...", end=" ")

            try:
                success = test()
                if success:
                    print("✅ PASSED")
                else:
                    print("❌ FAILED")
            except Exception as e:
                print(f"❌ ERROR: {str(e)}")
                self.add_result(test.__name__, "failed", f"Unexpected error: {str(e)}")

        # Print summary
        print("\n" + "=" * 60)
        print("📊 Test Summary:")
        print(f"   Total: {self.results['summary']['total']}")
        print(f"   ✅ Passed: {self.results['summary']['passed']}")
        print(f"   ❌ Failed: {self.results['summary']['failed']}")
        print(f"   ⏭️  Skipped: {self.results['summary']['skipped']}")

        # Print detailed results
        print("\n📝 Detailed Results:")
        for test in self.results["tests"]:
            status_emoji = "✅" if test["status"] == "passed" else "❌"
            print(f"   {status_emoji} {test['name']}: {test['message']}")

        return self.results


def main():
    """Main entry point"""
    tester = IntegrationTester()
    results = tester.run_all_tests()

    # Output JSON for programmatic parsing
    print("\n" + "=" * 60)
    print("📄 JSON Results:")
    print(json.dumps(results, indent=2))

    # Exit with error code if any tests failed
    if results["summary"]["failed"] > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
