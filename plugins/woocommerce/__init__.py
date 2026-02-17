"""
WooCommerce Plugin

E-commerce management plugin for WordPress WooCommerce stores.
Split from WordPress Core in Phase D.1.

Provides:
- Products (12 tools)
- Orders (5 tools)
- Customers (4 tools)
- Coupons (4 tools)
- Reports (3 tools)

Total: 28 tools
"""

from plugins.woocommerce.plugin import WooCommercePlugin

__all__ = ["WooCommercePlugin"]
