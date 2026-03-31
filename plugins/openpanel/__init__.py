"""
OpenPanel Plugin - Product Analytics Management.

Self-hosted OpenPanel management through public REST APIs (42 tools).
Event tracking, data export, analytics, project & client management.
"""

from plugins.openpanel.client import OpenPanelClient
from plugins.openpanel.plugin import OpenPanelPlugin

__all__ = ["OpenPanelPlugin", "OpenPanelClient"]
