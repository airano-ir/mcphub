"""Plugin visibility control for public vs admin users (Track F.1).

Controls which plugins are visible to public (OAuth) users vs admin users.
Admin users (MASTER_API_KEY) always see all plugins. Public users only see
plugins listed in the ENABLED_PLUGINS setting (DB > ENV > default).

Usage:
    from core.plugin_visibility import get_public_plugin_types, is_plugin_public

    public_types = get_public_plugin_types()  # {"wordpress", "woocommerce", "supabase"}
    if is_plugin_public("gitea"):  # False
        ...
"""

import os

# Default plugins available to public (OAuth) users
DEFAULT_PUBLIC_PLUGINS = {"wordpress", "woocommerce", "supabase", "openpanel"}


def _parse_plugins(val: str) -> set[str]:
    """Parse comma-separated plugin string into set."""
    return {p.strip().lower() for p in val.split(",") if p.strip()}


def get_public_plugin_types() -> set[str]:
    """Return the set of plugin types visible to public users.

    Checks DB settings first (sync-safe), then env var, then defaults.

    Returns:
        Set of lowercase plugin type strings.
    """
    # Try DB setting (sync access via cached value)
    try:
        from core.settings import _cached_plugins

        if _cached_plugins is not None:
            return set(_cached_plugins)
    except (ImportError, AttributeError):
        pass

    # Fallback to env var
    env_val = os.getenv("ENABLED_PLUGINS", "").strip()
    if not env_val:
        return set(DEFAULT_PUBLIC_PLUGINS)
    return _parse_plugins(env_val)


def is_plugin_public(plugin_type: str) -> bool:
    """Check if a plugin type is enabled for public users.

    Args:
        plugin_type: Plugin type string (e.g., "wordpress").

    Returns:
        True if the plugin is in the public set.
    """
    return plugin_type.lower() in get_public_plugin_types()
