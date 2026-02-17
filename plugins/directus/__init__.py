"""Directus CMS Plugin - Self-Hosted Headless CMS Management"""

from plugins.directus.client import DirectusClient
from plugins.directus.plugin import DirectusPlugin

__all__ = ["DirectusPlugin", "DirectusClient"]
