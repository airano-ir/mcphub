"""Appwrite Plugin - Self-Hosted Backend-as-a-Service Management"""

from plugins.appwrite.client import AppwriteClient
from plugins.appwrite.plugin import AppwritePlugin

__all__ = ["AppwritePlugin", "AppwriteClient"]
