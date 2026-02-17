"""
WordPress Handlers

Modular handlers for WordPress functionality.
Each handler is responsible for a specific domain of WordPress operations.

Part of Option B clean architecture refactoring.
"""

from plugins.wordpress.handlers.comments import CommentsHandler
from plugins.wordpress.handlers.comments import get_tool_specifications as get_comments_specs
from plugins.wordpress.handlers.coupons import CouponsHandler
from plugins.wordpress.handlers.coupons import get_tool_specifications as get_coupons_specs
from plugins.wordpress.handlers.customers import CustomersHandler
from plugins.wordpress.handlers.customers import get_tool_specifications as get_customers_specs
from plugins.wordpress.handlers.media import MediaHandler
from plugins.wordpress.handlers.media import get_tool_specifications as get_media_specs
from plugins.wordpress.handlers.menus import MenusHandler
from plugins.wordpress.handlers.menus import get_tool_specifications as get_menus_specs
from plugins.wordpress.handlers.orders import OrdersHandler
from plugins.wordpress.handlers.orders import get_tool_specifications as get_orders_specs
from plugins.wordpress.handlers.posts import PostsHandler
from plugins.wordpress.handlers.posts import get_tool_specifications as get_posts_specs
from plugins.wordpress.handlers.products import ProductsHandler
from plugins.wordpress.handlers.products import get_tool_specifications as get_products_specs
from plugins.wordpress.handlers.reports import ReportsHandler
from plugins.wordpress.handlers.reports import get_tool_specifications as get_reports_specs
from plugins.wordpress.handlers.seo import SEOHandler
from plugins.wordpress.handlers.seo import get_tool_specifications as get_seo_specs
from plugins.wordpress.handlers.site import SiteHandler
from plugins.wordpress.handlers.site import get_tool_specifications as get_site_specs
from plugins.wordpress.handlers.taxonomy import TaxonomyHandler
from plugins.wordpress.handlers.taxonomy import get_tool_specifications as get_taxonomy_specs
from plugins.wordpress.handlers.users import UsersHandler
from plugins.wordpress.handlers.users import get_tool_specifications as get_users_specs
from plugins.wordpress.handlers.wp_cli import WPCLIHandler
from plugins.wordpress.handlers.wp_cli import get_tool_specifications as get_wp_cli_specs

__all__ = [
    # Core Handlers
    "PostsHandler",
    "MediaHandler",
    "TaxonomyHandler",
    "CommentsHandler",
    "UsersHandler",
    "SiteHandler",
    # WooCommerce Handlers
    "ProductsHandler",
    "OrdersHandler",
    "CustomersHandler",
    "ReportsHandler",
    "CouponsHandler",
    # Advanced Handlers
    "SEOHandler",
    "WPCLIHandler",
    "MenusHandler",
    # Tool specifications
    "get_posts_specs",
    "get_media_specs",
    "get_taxonomy_specs",
    "get_comments_specs",
    "get_users_specs",
    "get_site_specs",
    "get_products_specs",
    "get_orders_specs",
    "get_customers_specs",
    "get_reports_specs",
    "get_coupons_specs",
    "get_seo_specs",
    "get_wp_cli_specs",
    "get_menus_specs",
]
