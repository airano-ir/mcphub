"""Unified settings access with DB > ENV > Default priority (Phase 4C.3).

Usage:
    from core.settings import get_setting

    enabled = await get_setting(
        "ENABLED_PLUGINS",
        "wordpress,woocommerce,wordpress_specialist,supabase,openpanel,gitea,n8n,coolify",
    )
    max_sites = int(await get_setting("MAX_SITES_PER_USER", "10"))
"""

import logging
import os

logger = logging.getLogger(__name__)

# Cached plugin set for sync access (updated when settings change)
_cached_plugins: set[str] | None = None

# Cached int settings for sync access (updated when settings change)
_cached_max_sites: int | None = None
_cached_rate_per_min: int | None = None
_cached_rate_per_hr: int | None = None

# Default values for all managed settings
SETTING_DEFAULTS: dict[str, str] = {
    "ENABLED_PLUGINS": "wordpress,woocommerce,wordpress_specialist,supabase,openpanel,gitea,n8n,coolify",
    "MAX_SITES_PER_USER": "10",
    "USER_RATE_LIMIT_PER_MIN": "30",
    "USER_RATE_LIMIT_PER_HR": "500",
}

# Human-readable labels for the settings UI
SETTING_LABELS: dict[str, dict[str, str]] = {
    "ENABLED_PLUGINS": {
        "label": "Enabled Plugins",
        "label_fa": "پلاگین‌های فعال",
        "hint": "Comma-separated plugin types visible to public users",
        "hint_fa": "انواع پلاگین قابل مشاهده برای کاربران عمومی (با کاما جدا شوند)",
    },
    "MAX_SITES_PER_USER": {
        "label": "Max Sites per User",
        "label_fa": "حداکثر سایت هر کاربر",
        "hint": "Maximum number of sites each user can create",
        "hint_fa": "حداکثر تعداد سایت‌هایی که هر کاربر می‌تواند بسازد",
    },
    "USER_RATE_LIMIT_PER_MIN": {
        "label": "User Rate Limit (per minute)",
        "label_fa": "محدودیت نرخ کاربر (در دقیقه)",
        "hint": "Maximum MCP requests per user per minute",
        "hint_fa": "حداکثر درخواست MCP هر کاربر در دقیقه",
    },
    "USER_RATE_LIMIT_PER_HR": {
        "label": "User Rate Limit (per hour)",
        "label_fa": "محدودیت نرخ کاربر (در ساعت)",
        "hint": "Maximum MCP requests per user per hour",
        "hint_fa": "حداکثر درخواست MCP هر کاربر در ساعت",
    },
}


async def get_setting(key: str, default: str | None = None) -> str | None:
    """Get a setting value with priority: Database > Environment > Default.

    Args:
        key: Setting key (e.g., "ENABLED_PLUGINS").
        default: Fallback if not found anywhere. If None, uses SETTING_DEFAULTS.

    Returns:
        Setting value string, or None if not found anywhere.
    """
    # 1. Try database
    try:
        from core.database import get_database

        db = get_database()
        db_val = await db.get_setting(key)
        if db_val is not None:
            return db_val
    except Exception:
        pass  # DB not initialized yet (startup) — fall through

    # 2. Try environment variable
    env_val = os.environ.get(key)
    if env_val is not None:
        return env_val

    # 3. Use provided default or SETTING_DEFAULTS
    if default is not None:
        return default
    return SETTING_DEFAULTS.get(key)


def get_cached_max_sites() -> int:
    """Return the cached MAX_SITES_PER_USER value (sync, uses last refresh)."""
    if _cached_max_sites is not None:
        return _cached_max_sites
    env_val = os.environ.get("MAX_SITES_PER_USER")
    if env_val:
        try:
            return max(1, int(env_val))
        except ValueError:
            pass
    return int(SETTING_DEFAULTS["MAX_SITES_PER_USER"])


def get_cached_rate_per_min() -> int:
    """Return the cached USER_RATE_LIMIT_PER_MIN value (sync, uses last refresh)."""
    if _cached_rate_per_min is not None:
        return _cached_rate_per_min
    env_val = os.environ.get("USER_RATE_LIMIT_PER_MIN")
    if env_val:
        try:
            return max(1, int(env_val))
        except ValueError:
            pass
    return int(SETTING_DEFAULTS["USER_RATE_LIMIT_PER_MIN"])


def get_cached_rate_per_hr() -> int:
    """Return the cached USER_RATE_LIMIT_PER_HR value (sync, uses last refresh)."""
    if _cached_rate_per_hr is not None:
        return _cached_rate_per_hr
    env_val = os.environ.get("USER_RATE_LIMIT_PER_HR")
    if env_val:
        try:
            return max(1, int(env_val))
        except ValueError:
            pass
    return int(SETTING_DEFAULTS["USER_RATE_LIMIT_PER_HR"])


async def refresh_plugin_cache() -> None:
    """Refresh all sync-readable setting caches from DB/ENV/default."""
    global _cached_plugins, _cached_max_sites, _cached_rate_per_min, _cached_rate_per_hr

    val = await get_setting("ENABLED_PLUGINS")
    if val:
        _cached_plugins = {p.strip().lower() for p in val.split(",") if p.strip()}
    else:
        _cached_plugins = None

    try:
        raw = await get_setting("MAX_SITES_PER_USER")
        _cached_max_sites = max(1, int(raw)) if raw else int(SETTING_DEFAULTS["MAX_SITES_PER_USER"])
    except (ValueError, TypeError):
        _cached_max_sites = int(SETTING_DEFAULTS["MAX_SITES_PER_USER"])

    try:
        raw = await get_setting("USER_RATE_LIMIT_PER_MIN")
        _cached_rate_per_min = (
            max(1, int(raw)) if raw else int(SETTING_DEFAULTS["USER_RATE_LIMIT_PER_MIN"])
        )
    except (ValueError, TypeError):
        _cached_rate_per_min = int(SETTING_DEFAULTS["USER_RATE_LIMIT_PER_MIN"])

    try:
        raw = await get_setting("USER_RATE_LIMIT_PER_HR")
        _cached_rate_per_hr = (
            max(1, int(raw)) if raw else int(SETTING_DEFAULTS["USER_RATE_LIMIT_PER_HR"])
        )
    except (ValueError, TypeError):
        _cached_rate_per_hr = int(SETTING_DEFAULTS["USER_RATE_LIMIT_PER_HR"])


async def save_setting(key: str, value: str) -> None:
    """Save a setting to database and refresh caches."""
    from core.database import get_database

    db = get_database()
    await db.set_setting(key, value)

    await refresh_plugin_cache()


async def delete_setting_value(key: str) -> bool:
    """Delete a setting from database (revert to ENV/default)."""
    from core.database import get_database

    db = get_database()
    deleted = await db.delete_setting(key)

    await refresh_plugin_cache()

    return deleted


async def get_all_managed_settings() -> list[dict[str, str]]:
    """Get all managed settings with their current values and sources.

    Returns:
        List of dicts with: key, value, source ("database"/"environment"/"default"),
        label, hint.
    """
    result = []
    try:
        from core.database import get_database

        db = get_database()
        db_settings = await db.get_all_settings()
    except Exception:
        db_settings = {}

    for key, default_val in SETTING_DEFAULTS.items():
        meta = SETTING_LABELS.get(key, {})
        db_val = db_settings.get(key)
        env_val = os.environ.get(key)

        if db_val is not None:
            value, source = db_val, "database"
        elif env_val is not None:
            value, source = env_val, "environment"
        else:
            value, source = default_val, "default"

        result.append(
            {
                "key": key,
                "value": value,
                "source": source,
                "default": default_val,
                "label": meta.get("label", key),
                "label_fa": meta.get("label_fa", key),
                "hint": meta.get("hint", ""),
                "hint_fa": meta.get("hint_fa", ""),
            }
        )

    return result
