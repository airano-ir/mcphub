"""
OpenPanel Handlers

Phase H.1: Core (25 tools)
- events.py: Event tracking (9 tools - alias_user removed)
- export.py: Data export (10 tools)
- system.py: Health & stats (6 tools)

Phase H.2: Analytics (24 tools)
- reports.py: Analytics reports (8 tools)
- funnels.py: Funnel analysis (8 tools)
- profiles.py: User profiles (8 tools)

Phase H.3: Management (24 tools)
- projects.py: Project management (8 tools)
- dashboards.py: Dashboard management (10 tools)
- clients.py: API client management (6 tools)

Total: 73 tools
"""

from plugins.openpanel.handlers import (
    clients,
    dashboards,
    events,
    export,
    funnels,
    profiles,
    projects,
    reports,
    system,
)

__all__ = [
    "events",
    "export",
    "system",
    "reports",
    "funnels",
    "profiles",
    "projects",
    "dashboards",
    "clients",
]
