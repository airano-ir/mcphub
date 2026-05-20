"""Handlers for the WordPress Specialist plugin."""

from plugins.wordpress_specialist.handlers.bulk import BulkHandler
from plugins.wordpress_specialist.handlers.bulk import (
    get_tool_specifications as get_bulk_specs,
)
from plugins.wordpress_specialist.handlers.database import DatabaseHandler
from plugins.wordpress_specialist.handlers.database import (
    get_tool_specifications as get_database_specs,
)
from plugins.wordpress_specialist.handlers.management import ManagementHandler
from plugins.wordpress_specialist.handlers.management import (
    get_tool_specifications as get_management_specs,
)
from plugins.wordpress_specialist.handlers.pages import PagesHandler
from plugins.wordpress_specialist.handlers.pages import (
    get_tool_specifications as get_pages_specs,
)
from plugins.wordpress_specialist.handlers.plugins import PluginsHandler
from plugins.wordpress_specialist.handlers.plugins import (
    get_tool_specifications as get_plugins_specs,
)
from plugins.wordpress_specialist.handlers.site_config import SiteConfigHandler
from plugins.wordpress_specialist.handlers.site_config import (
    get_tool_specifications as get_site_config_specs,
)
from plugins.wordpress_specialist.handlers.site_layout import SiteLayoutHandler
from plugins.wordpress_specialist.handlers.site_layout import (
    get_tool_specifications as get_site_layout_specs,
)
from plugins.wordpress_specialist.handlers.themes import ThemesHandler
from plugins.wordpress_specialist.handlers.themes import (
    get_tool_specifications as get_themes_specs,
)

__all__ = [
    "BulkHandler",
    "get_bulk_specs",
    "DatabaseHandler",
    "get_database_specs",
    "ManagementHandler",
    "get_management_specs",
    "PagesHandler",
    "get_pages_specs",
    "PluginsHandler",
    "get_plugins_specs",
    "SiteConfigHandler",
    "get_site_config_specs",
    "SiteLayoutHandler",
    "get_site_layout_specs",
    "ThemesHandler",
    "get_themes_specs",
]
