"""
OpenPanel Plugin - Product Analytics Management

Complete OpenPanel Self-Hosted management through REST API.
Provides tools for event tracking, data export, funnels,
dashboards, user profiles, and analytics reports.

For Self-Hosted instances deployed on Coolify.
"""

from plugins.openpanel.client import OpenPanelClient
from plugins.openpanel.plugin import OpenPanelPlugin

__all__ = ["OpenPanelPlugin", "OpenPanelClient"]
