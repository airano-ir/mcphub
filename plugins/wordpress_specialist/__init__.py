"""WordPress Specialist Plugin (F.19).

Companion-backed advanced WordPress management for professionals —
plugins, themes, users, options, cron, maintenance, page editing, site
config + layout, db inspection, bulk fan-out. Replaced the deprecated
``wordpress_advanced`` plugin (sunset 2026-05-04 in F.19.3.2-.3); this
plugin requires only Airano MCP Bridge v2.18.0+ and an Application
Password for a user with ``manage_options``. No Docker socket needed.
"""

from plugins.wordpress_specialist import handlers
from plugins.wordpress_specialist.plugin import WordPressSpecialistPlugin

__all__ = [
    "WordPressSpecialistPlugin",
    "handlers",
]
