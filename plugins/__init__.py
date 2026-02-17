"""
Plugins package

All project type plugins are here.

v2.8.0 (Phase J): Directus CMS Plugin added
v2.6.0 (Phase I): Appwrite Backend Plugin added
v2.5.0 (Phase H): OpenPanel Analytics Plugin added
v2.3.0 (Phase G): Supabase Self-Hosted Plugin added
"""

from plugins.appwrite.plugin import AppwritePlugin
from plugins.base import BasePlugin, PluginRegistry
from plugins.directus.plugin import DirectusPlugin
from plugins.gitea.plugin import GiteaPlugin
from plugins.n8n.plugin import N8nPlugin
from plugins.openpanel.plugin import OpenPanelPlugin
from plugins.supabase.plugin import SupabasePlugin
from plugins.woocommerce.plugin import WooCommercePlugin
from plugins.wordpress.plugin import WordPressPlugin
from plugins.wordpress_advanced.plugin import WordPressAdvancedPlugin

# Create global registry
registry = PluginRegistry()

# Register available plugins
registry.register("wordpress", WordPressPlugin)
registry.register("woocommerce", WooCommercePlugin)
registry.register("wordpress_advanced", WordPressAdvancedPlugin)
registry.register("gitea", GiteaPlugin)
registry.register("n8n", N8nPlugin)
registry.register("supabase", SupabasePlugin)
registry.register("openpanel", OpenPanelPlugin)
registry.register("appwrite", AppwritePlugin)
registry.register("directus", DirectusPlugin)

__all__ = [
    "BasePlugin",
    "PluginRegistry",
    "registry",
    "WordPressPlugin",
    "WooCommercePlugin",
    "WordPressAdvancedPlugin",
    "GiteaPlugin",
    "N8nPlugin",
    "SupabasePlugin",
    "OpenPanelPlugin",
    "AppwritePlugin",
    "DirectusPlugin",
]
