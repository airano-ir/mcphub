"""
WooCommerce Plugin - E-commerce Management

Split from WordPress Core in Phase D.1.
Provides 28 tools for WooCommerce store management.

Uses shared WordPress handlers for implementation.
"""

from typing import Any

from plugins.base import BasePlugin
from plugins.wordpress.client import WordPressClient
from plugins.wordpress.handlers import (
    CouponsHandler,
    CustomersHandler,
    OrdersHandler,
    ProductsHandler,
    ReportsHandler,
    get_coupons_specs,
    get_customers_specs,
    get_orders_specs,
    get_products_specs,
    get_reports_specs,
)

class WooCommercePlugin(BasePlugin):
    """
    WooCommerce E-commerce Plugin.

    Provides comprehensive WooCommerce management capabilities:
    - Products (12 tools): CRUD, categories, tags, attributes, variations
    - Orders (5 tools): list, get, create, update_status, delete
    - Customers (4 tools): list, get, create, update
    - Coupons (4 tools): list, create, update, delete
    - Reports (3 tools): sales, top_sellers, customer_report

    Total: 28 tools
    """

    @staticmethod
    def get_plugin_name() -> str:
        """Return plugin type identifier"""
        return "woocommerce"

    @staticmethod
    def get_required_config_keys() -> list[str]:
        """Return required configuration keys"""
        return ["url", "username", "app_password"]

    def __init__(self, config: dict[str, Any], project_id: str | None = None):
        """
        Initialize WooCommerce plugin with handlers.

        Args:
            config: Configuration dictionary containing:
                - url: WordPress site URL
                - username: WordPress username
                - app_password: WordPress application password
            project_id: Optional project ID (auto-generated if not provided)
        """
        super().__init__(config, project_id=project_id)

        # Create WordPress API client (WooCommerce uses WordPress REST API)
        self.client = WordPressClient(
            site_url=config["url"], username=config["username"], app_password=config["app_password"]
        )

        # Initialize WooCommerce handlers
        self.products = ProductsHandler(self.client)
        self.orders = OrdersHandler(self.client)
        self.customers = CustomersHandler(self.client)
        self.coupons = CouponsHandler(self.client)
        self.reports = ReportsHandler(self.client)

    @staticmethod
    def get_tool_specifications() -> list[dict[str, Any]]:
        """
        Return all tool specifications for ToolGenerator.

        This method is called by ToolGenerator to create unified tools
        with site parameter routing.

        Returns:
            List of tool specification dictionaries (28 tools)
        """
        specs = []

        # Products (12 tools)
        specs.extend(get_products_specs())

        # Orders (5 tools)
        specs.extend(get_orders_specs())

        # Customers (4 tools)
        specs.extend(get_customers_specs())

        # Coupons (4 tools)
        specs.extend(get_coupons_specs())

        # Reports (3 tools)
        specs.extend(get_reports_specs())

        return specs

    async def health_check(self) -> dict[str, Any]:
        """
        Check WooCommerce availability and health.

        Returns:
            Dict with health status and WooCommerce version
        """
        try:
            wc_status = await self.client.check_woocommerce()
            if wc_status.get("available"):
                return {
                    "healthy": True,
                    "message": "WooCommerce is available",
                    "version": wc_status.get("version", "unknown"),
                    "plugin_type": "woocommerce",
                }
            else:
                return {
                    "healthy": False,
                    "message": "WooCommerce is not available on this site",
                    "plugin_type": "woocommerce",
                }
        except Exception as e:
            return {
                "healthy": False,
                "message": f"Health check failed: {str(e)}",
                "plugin_type": "woocommerce",
            }

    # ========================================
    # Method Delegation to Handlers
    # ========================================

    # === Products ===
    async def list_products(self, **kwargs):
        return await self.products.list_products(**kwargs)

    async def get_product(self, **kwargs):
        return await self.products.get_product(**kwargs)

    async def create_product(self, **kwargs):
        return await self.products.create_product(**kwargs)

    async def update_product(self, **kwargs):
        return await self.products.update_product(**kwargs)

    async def delete_product(self, **kwargs):
        return await self.products.delete_product(**kwargs)

    async def list_product_categories(self, **kwargs):
        return await self.products.list_product_categories(**kwargs)

    async def create_product_category(self, **kwargs):
        return await self.products.create_product_category(**kwargs)

    async def list_product_tags(self, **kwargs):
        return await self.products.list_product_tags(**kwargs)

    async def list_product_attributes(self, **kwargs):
        return await self.products.list_product_attributes(**kwargs)

    async def create_product_attribute(self, **kwargs):
        return await self.products.create_product_attribute(**kwargs)

    async def list_product_variations(self, **kwargs):
        return await self.products.list_product_variations(**kwargs)

    async def create_product_variation(self, **kwargs):
        return await self.products.create_product_variation(**kwargs)

    # === Orders ===
    async def list_orders(self, **kwargs):
        return await self.orders.list_orders(**kwargs)

    async def get_order(self, **kwargs):
        return await self.orders.get_order(**kwargs)

    async def create_order(self, **kwargs):
        return await self.orders.create_order(**kwargs)

    async def update_order_status(self, **kwargs):
        return await self.orders.update_order_status(**kwargs)

    async def delete_order(self, **kwargs):
        return await self.orders.delete_order(**kwargs)

    # === Customers ===
    async def list_customers(self, **kwargs):
        return await self.customers.list_customers(**kwargs)

    async def get_customer(self, **kwargs):
        return await self.customers.get_customer(**kwargs)

    async def create_customer(self, **kwargs):
        return await self.customers.create_customer(**kwargs)

    async def update_customer(self, **kwargs):
        return await self.customers.update_customer(**kwargs)

    # === Coupons ===
    async def list_coupons(self, **kwargs):
        return await self.coupons.list_coupons(**kwargs)

    async def create_coupon(self, **kwargs):
        return await self.coupons.create_coupon(**kwargs)

    async def update_coupon(self, **kwargs):
        return await self.coupons.update_coupon(**kwargs)

    async def delete_coupon(self, **kwargs):
        return await self.coupons.delete_coupon(**kwargs)

    # === Reports ===
    async def get_sales_report(self, **kwargs):
        return await self.reports.get_sales_report(**kwargs)

    async def get_top_sellers(self, **kwargs):
        return await self.reports.get_top_sellers(**kwargs)

    async def get_customer_report(self, **kwargs):
        return await self.reports.get_customer_report(**kwargs)
