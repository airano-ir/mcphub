"""
OpenPanel Handlers — 42 tools across 7 handlers.

All tools use public REST APIs (no tRPC/session dependency).

Track API (/track) — write mode:
- events.py: Event tracking, groups (11 tools)

Export API (/export) — read mode:
- export.py: Data export & analytics (10 tools)

Insights API (/insights) — read mode:
- reports.py: Overview & realtime stats (2 tools)

Profile API — read mode:
- profiles.py: Profile events & data export (3 tools)

Manage API (/manage) — root mode:
- projects.py: Project CRUD (5 tools)
- clients.py: Client CRUD (5 tools)

System:
- system.py: Health & instance info (6 tools)

Removed (no public API):
- dashboards.py (tRPC-only)
- funnels.py (tRPC-only)
"""

from plugins.openpanel.handlers import (
    clients,
    events,
    export,
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
    "profiles",
    "projects",
    "clients",
]
