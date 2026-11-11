"""
Plugins package

All project type plugins are here.

2026-08-26: Cloudflare Plugin added (static API token — zones, DNS,
            Workers, KV, R2, cache; read/write/admin scope tiers).
F.19.3.2-.3 (2026-05-04): wordpress_advanced sunset — the deprecated
                     Docker-socket / WP-CLI plugin was removed once
                     wordpress_specialist absorbed db inspection +
                     bulk fan-out (companion v2.18.0).
F.19.1 (2026-05-01): WordPress Specialist Plugin added (companion-backed,
                     no Docker socket).
v2.5.0 (Phase H): OpenPanel Analytics Plugin added
v2.3.0 (Phase G): Supabase Self-Hosted Plugin added
"""

from plugins.base import BasePlugin, PluginRegistry
from plugins.cloudflare.plugin import CloudflarePlugin
from plugins.coolify.plugin import CoolifyPlugin
from plugins.gitea.plugin import GiteaPlugin
from plugins.gmail.plugin import GmailPlugin
from plugins.google_search_console.plugin import GoogleSearchConsolePlugin
from plugins.n8n.plugin import N8nPlugin
from plugins.openpanel.plugin import OpenPanelPlugin
from plugins.supabase.plugin import SupabasePlugin
from plugins.woocommerce.plugin import WooCommercePlugin
from plugins.wordpress.plugin import WordPressPlugin
from plugins.wordpress_specialist.plugin import WordPressSpecialistPlugin

# Create global registry
registry = PluginRegistry()

# Register available plugins (11 active plugins)
registry.register("wordpress", WordPressPlugin)
registry.register("woocommerce", WooCommercePlugin)
registry.register("wordpress_specialist", WordPressSpecialistPlugin)
registry.register("gitea", GiteaPlugin)
registry.register("n8n", N8nPlugin)
registry.register("supabase", SupabasePlugin)
registry.register("openpanel", OpenPanelPlugin)
registry.register("coolify", CoolifyPlugin)
registry.register("gmail", GmailPlugin)
registry.register("google_search_console", GoogleSearchConsolePlugin)
registry.register("cloudflare", CloudflarePlugin)

__all__ = [
    "BasePlugin",
    "PluginRegistry",
    "registry",
    "WordPressPlugin",
    "WooCommercePlugin",
    "WordPressSpecialistPlugin",
    "GiteaPlugin",
    "N8nPlugin",
    "SupabasePlugin",
    "OpenPanelPlugin",
    "CoolifyPlugin",
    "GmailPlugin",
    "GoogleSearchConsolePlugin",
    "CloudflarePlugin",
]
