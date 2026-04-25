"""
WordPress Handlers

Modular handlers for WordPress functionality.
Each handler is responsible for a specific domain of WordPress operations.

Part of Option B clean architecture refactoring.
"""

from plugins.wordpress.handlers.ai_media import AIMediaHandler
from plugins.wordpress.handlers.ai_media import get_tool_specifications as get_ai_media_specs
from plugins.wordpress.handlers.audit_hook import AuditHookHandler
from plugins.wordpress.handlers.audit_hook import (
    get_tool_specifications as get_audit_hook_specs,
)
from plugins.wordpress.handlers.bulk_meta import BulkMetaHandler
from plugins.wordpress.handlers.bulk_meta import get_tool_specifications as get_bulk_meta_specs
from plugins.wordpress.handlers.cache_purge import CachePurgeHandler
from plugins.wordpress.handlers.cache_purge import (
    get_tool_specifications as get_cache_purge_specs,
)
from plugins.wordpress.handlers.capabilities import CapabilitiesHandler
from plugins.wordpress.handlers.capabilities import (
    get_tool_specifications as get_capabilities_specs,
)
from plugins.wordpress.handlers.comments import CommentsHandler
from plugins.wordpress.handlers.comments import get_tool_specifications as get_comments_specs
from plugins.wordpress.handlers.coupons import CouponsHandler
from plugins.wordpress.handlers.coupons import get_tool_specifications as get_coupons_specs
from plugins.wordpress.handlers.customers import CustomersHandler
from plugins.wordpress.handlers.customers import get_tool_specifications as get_customers_specs
from plugins.wordpress.handlers.export import ExportHandler
from plugins.wordpress.handlers.export import get_tool_specifications as get_export_specs
from plugins.wordpress.handlers.media import MediaHandler
from plugins.wordpress.handlers.media import get_tool_specifications as get_media_specs
from plugins.wordpress.handlers.media_attach import MediaAttachHandler
from plugins.wordpress.handlers.media_attach import (
    get_tool_specifications as get_media_attach_specs,
)
from plugins.wordpress.handlers.media_bulk import MediaBulkHandler
from plugins.wordpress.handlers.media_bulk import (
    get_tool_specifications as get_media_bulk_specs,
)
from plugins.wordpress.handlers.media_chunked import MediaChunkedHandler
from plugins.wordpress.handlers.media_chunked import (
    get_tool_specifications as get_media_chunked_specs,
)
from plugins.wordpress.handlers.media_probe import ProbeHandler
from plugins.wordpress.handlers.media_probe import (
    get_tool_specifications as get_media_probe_specs,
)
from plugins.wordpress.handlers.menus import MenusHandler
from plugins.wordpress.handlers.menus import get_tool_specifications as get_menus_specs
from plugins.wordpress.handlers.orders import OrdersHandler
from plugins.wordpress.handlers.orders import get_tool_specifications as get_orders_specs
from plugins.wordpress.handlers.posts import PostsHandler
from plugins.wordpress.handlers.posts import get_tool_specifications as get_posts_specs
from plugins.wordpress.handlers.products import ProductsHandler
from plugins.wordpress.handlers.products import get_tool_specifications as get_products_specs
from plugins.wordpress.handlers.regenerate_thumbnails import RegenerateThumbnailsHandler
from plugins.wordpress.handlers.regenerate_thumbnails import (
    get_tool_specifications as get_regenerate_thumbnails_specs,
)
from plugins.wordpress.handlers.reports import ReportsHandler
from plugins.wordpress.handlers.reports import get_tool_specifications as get_reports_specs
from plugins.wordpress.handlers.seo import SEOHandler
from plugins.wordpress.handlers.seo import get_tool_specifications as get_seo_specs
from plugins.wordpress.handlers.site import SiteHandler
from plugins.wordpress.handlers.site import get_tool_specifications as get_site_specs
from plugins.wordpress.handlers.site_health import SiteHealthHandler
from plugins.wordpress.handlers.site_health import (
    get_tool_specifications as get_site_health_specs,
)
from plugins.wordpress.handlers.taxonomy import TaxonomyHandler
from plugins.wordpress.handlers.taxonomy import get_tool_specifications as get_taxonomy_specs
from plugins.wordpress.handlers.transient_flush import TransientFlushHandler
from plugins.wordpress.handlers.transient_flush import (
    get_tool_specifications as get_transient_flush_specs,
)
from plugins.wordpress.handlers.users import UsersHandler
from plugins.wordpress.handlers.users import get_tool_specifications as get_users_specs
from plugins.wordpress.handlers.wp_cli import WPCLIHandler
from plugins.wordpress.handlers.wp_cli import get_tool_specifications as get_wp_cli_specs

__all__ = [
    # Core Handlers
    "PostsHandler",
    "MediaHandler",
    "MediaAttachHandler",
    "MediaBulkHandler",
    "MediaChunkedHandler",
    "ProbeHandler",
    "AIMediaHandler",
    "AuditHookHandler",
    "BulkMetaHandler",
    "CachePurgeHandler",
    "CapabilitiesHandler",
    "RegenerateThumbnailsHandler",
    "ExportHandler",
    "SiteHealthHandler",
    "TransientFlushHandler",
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
    "get_media_attach_specs",
    "get_media_bulk_specs",
    "get_media_chunked_specs",
    "get_media_probe_specs",
    "get_ai_media_specs",
    "get_audit_hook_specs",
    "get_bulk_meta_specs",
    "get_cache_purge_specs",
    "get_capabilities_specs",
    "get_regenerate_thumbnails_specs",
    "get_export_specs",
    "get_site_health_specs",
    "get_transient_flush_specs",
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
