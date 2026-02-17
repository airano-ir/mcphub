"""Tests for WooCommerce Plugin (plugins/woocommerce/).

Integration tests covering plugin initialization, configuration validation,
tool specifications, handler delegation, and health checks.
"""

from unittest.mock import AsyncMock

import pytest

from plugins.base import BasePlugin
from plugins.woocommerce.plugin import WooCommercePlugin


# --- WooCommercePlugin Initialization ---


class TestWooCommercePluginInit:
    """Test WooCommerce plugin initialization."""

    VALID_CONFIG = {
        "url": "https://shop.example.com",
        "username": "admin",
        "app_password": "xxxx xxxx xxxx xxxx",
    }

    def test_create_with_valid_config(self):
        """Should initialize with valid credentials."""
        plugin = WooCommercePlugin(self.VALID_CONFIG)
        assert plugin.project_id is not None
        assert plugin.client is not None
        assert isinstance(plugin, BasePlugin)

    def test_handlers_initialized(self):
        """Should initialize all WooCommerce handlers."""
        plugin = WooCommercePlugin(self.VALID_CONFIG)
        assert plugin.products is not None
        assert plugin.orders is not None
        assert plugin.customers is not None
        assert plugin.coupons is not None
        assert plugin.reports is not None

    def test_plugin_name(self):
        """Should return 'woocommerce' as plugin name."""
        assert WooCommercePlugin.get_plugin_name() == "woocommerce"

    def test_required_config_keys(self):
        """Should require url, username, app_password."""
        keys = WooCommercePlugin.get_required_config_keys()
        assert "url" in keys
        assert "username" in keys
        assert "app_password" in keys

    def test_missing_url_raises(self):
        """Should raise ValueError for missing URL."""
        config = {"username": "admin", "app_password": "xxxx"}
        with pytest.raises(ValueError, match="Missing required configuration"):
            WooCommercePlugin(config)

    def test_missing_credentials_raises(self):
        """Should raise ValueError for missing credentials."""
        config = {"url": "https://shop.example.com"}
        with pytest.raises(ValueError, match="Missing required configuration"):
            WooCommercePlugin(config)

    def test_custom_project_id(self):
        """Should accept custom project_id."""
        plugin = WooCommercePlugin(self.VALID_CONFIG, project_id="wc_myshop")
        assert plugin.project_id == "wc_myshop"

    def test_auto_generated_project_id(self):
        """Should auto-generate project_id from config."""
        plugin = WooCommercePlugin(self.VALID_CONFIG)
        assert plugin.project_id.startswith("woocommerce")

    def test_uses_wordpress_client(self):
        """Should create a WordPressClient (shared API client)."""
        from plugins.wordpress.client import WordPressClient

        plugin = WooCommercePlugin(self.VALID_CONFIG)
        assert isinstance(plugin.client, WordPressClient)
        assert plugin.client.site_url == "https://shop.example.com"


# --- Tool Specifications ---


class TestWooCommerceToolSpecs:
    """Test WooCommerce tool specification generation."""

    def test_specs_not_empty(self):
        """Should return non-empty tool specifications."""
        specs = WooCommercePlugin.get_tool_specifications()
        assert len(specs) > 0

    def test_specs_count(self):
        """Should return exactly 28 tool specs."""
        specs = WooCommercePlugin.get_tool_specifications()
        assert len(specs) == 28

    def test_specs_have_required_fields(self):
        """Each spec should have name, method_name, description, schema, scope."""
        specs = WooCommercePlugin.get_tool_specifications()
        for spec in specs:
            assert "name" in spec, f"Missing 'name' in spec"
            assert "method_name" in spec, f"Missing 'method_name' in {spec.get('name')}"
            assert "description" in spec, f"Missing 'description' in {spec.get('name')}"
            assert "schema" in spec, f"Missing 'schema' in {spec.get('name')}"
            assert "scope" in spec, f"Missing 'scope' in {spec.get('name')}"

    def test_specs_scope_values(self):
        """All scopes should be valid (read, write, admin)."""
        specs = WooCommercePlugin.get_tool_specifications()
        valid_scopes = {"read", "write", "admin"}
        for spec in specs:
            assert spec["scope"] in valid_scopes, f"Invalid scope '{spec['scope']}' in {spec['name']}"

    def test_specs_unique_names(self):
        """All tool names should be unique."""
        specs = WooCommercePlugin.get_tool_specifications()
        names = [s["name"] for s in specs]
        assert len(names) == len(set(names)), f"Duplicate names: {[n for n in names if names.count(n) > 1]}"

    def test_product_tools_present(self):
        """Should include product management tools."""
        specs = WooCommercePlugin.get_tool_specifications()
        names = {s["name"] for s in specs}
        expected = {"list_products", "get_product", "create_product", "update_product", "delete_product"}
        assert expected.issubset(names), f"Missing product tools: {expected - names}"

    def test_order_tools_present(self):
        """Should include order management tools."""
        specs = WooCommercePlugin.get_tool_specifications()
        names = {s["name"] for s in specs}
        expected = {"list_orders", "get_order", "create_order", "update_order_status", "delete_order"}
        assert expected.issubset(names), f"Missing order tools: {expected - names}"

    def test_customer_tools_present(self):
        """Should include customer tools."""
        specs = WooCommercePlugin.get_tool_specifications()
        names = {s["name"] for s in specs}
        assert "list_customers" in names
        assert "create_customer" in names

    def test_coupon_tools_present(self):
        """Should include coupon tools."""
        specs = WooCommercePlugin.get_tool_specifications()
        names = {s["name"] for s in specs}
        assert "list_coupons" in names
        assert "create_coupon" in names

    def test_report_tools_present(self):
        """Should include report tools."""
        specs = WooCommercePlugin.get_tool_specifications()
        names = {s["name"] for s in specs}
        assert "get_sales_report" in names
        assert "get_top_sellers" in names

    def test_no_wordpress_tools_leaked(self):
        """Should NOT include WordPress-core tools (posts, pages, etc)."""
        specs = WooCommercePlugin.get_tool_specifications()
        names = {s["name"] for s in specs}
        wp_tools = {"list_posts", "create_post", "list_categories", "list_media"}
        leaked = names & wp_tools
        assert len(leaked) == 0, f"WordPress tools leaked into WooCommerce: {leaked}"


# --- Handler Delegation ---


class TestWooCommerceHandlerDelegation:
    """Test that plugin methods delegate to handlers correctly."""

    VALID_CONFIG = {
        "url": "https://shop.example.com",
        "username": "admin",
        "app_password": "xxxx xxxx xxxx xxxx",
    }

    @pytest.fixture
    def plugin(self):
        return WooCommercePlugin(self.VALID_CONFIG)

    @pytest.mark.asyncio
    async def test_list_products_delegates(self, plugin):
        """list_products should delegate to products handler."""
        plugin.products.list_products = AsyncMock(return_value={"products": []})
        result = await plugin.list_products(per_page=10)
        plugin.products.list_products.assert_called_once_with(per_page=10)
        assert result == {"products": []}

    @pytest.mark.asyncio
    async def test_create_product_delegates(self, plugin):
        """create_product should delegate to products handler."""
        plugin.products.create_product = AsyncMock(return_value={"id": 99})
        result = await plugin.create_product(name="Widget", regular_price="19.99")
        plugin.products.create_product.assert_called_once_with(name="Widget", regular_price="19.99")

    @pytest.mark.asyncio
    async def test_list_orders_delegates(self, plugin):
        """list_orders should delegate to orders handler."""
        plugin.orders.list_orders = AsyncMock(return_value=[])
        await plugin.list_orders(status="processing")
        plugin.orders.list_orders.assert_called_once_with(status="processing")

    @pytest.mark.asyncio
    async def test_get_order_delegates(self, plugin):
        """get_order should delegate to orders handler."""
        plugin.orders.get_order = AsyncMock(return_value={"id": 1, "status": "completed"})
        result = await plugin.get_order(order_id=1)
        plugin.orders.get_order.assert_called_once_with(order_id=1)

    @pytest.mark.asyncio
    async def test_list_customers_delegates(self, plugin):
        """list_customers should delegate to customers handler."""
        plugin.customers.list_customers = AsyncMock(return_value=[])
        await plugin.list_customers()
        plugin.customers.list_customers.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_coupon_delegates(self, plugin):
        """create_coupon should delegate to coupons handler."""
        plugin.coupons.create_coupon = AsyncMock(return_value={"id": 5})
        result = await plugin.create_coupon(code="SAVE10", discount_type="percent")
        plugin.coupons.create_coupon.assert_called_once_with(code="SAVE10", discount_type="percent")

    @pytest.mark.asyncio
    async def test_get_sales_report_delegates(self, plugin):
        """get_sales_report should delegate to reports handler."""
        plugin.reports.get_sales_report = AsyncMock(return_value={"total": 1000})
        result = await plugin.get_sales_report(period="month")
        plugin.reports.get_sales_report.assert_called_once_with(period="month")


# --- Health Check ---


class TestWooCommerceHealthCheck:
    """Test WooCommerce health check."""

    VALID_CONFIG = {
        "url": "https://shop.example.com",
        "username": "admin",
        "app_password": "xxxx xxxx xxxx xxxx",
    }

    @pytest.fixture
    def plugin(self):
        return WooCommercePlugin(self.VALID_CONFIG)

    @pytest.mark.asyncio
    async def test_healthy_when_wc_available(self, plugin):
        """Should report healthy when WooCommerce is available."""
        plugin.client.check_woocommerce = AsyncMock(
            return_value={"available": True, "version": "8.5.0"}
        )
        result = await plugin.health_check()
        assert result["healthy"] is True
        assert result["version"] == "8.5.0"
        assert result["plugin_type"] == "woocommerce"

    @pytest.mark.asyncio
    async def test_unhealthy_when_wc_unavailable(self, plugin):
        """Should report unhealthy when WooCommerce is not available."""
        plugin.client.check_woocommerce = AsyncMock(
            return_value={"available": False, "version": None}
        )
        result = await plugin.health_check()
        assert result["healthy"] is False
        assert "not available" in result["message"]

    @pytest.mark.asyncio
    async def test_unhealthy_on_exception(self, plugin):
        """Should report unhealthy on network errors."""
        plugin.client.check_woocommerce = AsyncMock(side_effect=Exception("Connection refused"))
        result = await plugin.health_check()
        assert result["healthy"] is False
        assert "Connection refused" in result["message"]


# --- Plugin Info ---


class TestWooCommercePluginInfo:
    """Test plugin info methods."""

    VALID_CONFIG = {
        "url": "https://shop.example.com",
        "username": "admin",
        "app_password": "xxxx xxxx xxxx xxxx",
    }

    def test_get_project_info(self):
        """Should return structured project info."""
        plugin = WooCommercePlugin(self.VALID_CONFIG, project_id="wc_shop1")
        info = plugin.get_project_info()
        assert info["project_id"] == "wc_shop1"
        assert info["plugin_type"] == "woocommerce"

    def test_legacy_get_tools_empty(self):
        """Legacy get_tools should return empty list."""
        plugin = WooCommercePlugin(self.VALID_CONFIG)
        assert plugin.get_tools() == []
