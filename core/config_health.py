"""Operator-facing configuration health checks.

Single source of truth for "soft misconfiguration" warnings shown to
self-hosting operators: required secrets / environment variables that do
not hard-fail startup but leave the instance in a degraded or insecure
state (e.g. an ephemeral admin key, sessions that drop on every restart,
or disabled site management).

The same warnings are surfaced in two places so a self-hoster cannot miss
them on first deploy:

* a consolidated ``WARNING`` block logged once at startup
  (:func:`log_startup_config_health`)
* the admin dashboard banner via ``GET /api/dashboard/config-health``

Each warning is a plain dict with bilingual (EN/FA) copy so both the
startup log and the SPA banner render from one definition:

    {
        "code": "master_key_missing",   # stable identifier
        "severity": "critical",          # "critical" | "warning"
        "env": "MASTER_API_KEY",         # the env var to set
        "title_en": ..., "title_fa": ...,
        "detail_en": ..., "detail_fa": ...,
    }
"""

import os

__all__ = ["get_config_warnings", "log_startup_config_health"]


def _is_set(name: str) -> bool:
    """True when an env var is present and non-empty after stripping."""
    return bool((os.getenv(name) or "").strip())


def _is_truthy(name: str) -> bool:
    """True for common env truthy values."""
    return (os.getenv(name) or "").strip().lower() in {"1", "true", "yes", "on"}


def get_config_warnings() -> list[dict[str, str]]:
    """Return the list of active configuration warnings (may be empty).

    Pure function of the current environment — no I/O, safe to call from a
    request handler. Ordered most severe / most important first.
    """
    warnings: list[dict[str, str]] = []

    # MASTER_API_KEY is required only when master-key dashboard login is enabled.
    # OAuth-only deployments can intentionally set DISABLE_MASTER_KEY_LOGIN=true;
    # in that posture, showing "setup incomplete" on the login page is confusing
    # because the missing login method is deliberately disabled.
    if not _is_truthy("DISABLE_MASTER_KEY_LOGIN") and not _is_set("MASTER_API_KEY"):
        warnings.append(
            {
                "code": "master_key_missing",
                "severity": "critical",
                "env": "MASTER_API_KEY",
                "title_en": "MASTER_API_KEY is not set",
                "title_fa": "MASTER_API_KEY تنظیم نشده است",
                "detail_en": (
                    "A temporary admin key was generated and written to the startup "
                    "logs. It changes on every restart and exposes admin access to "
                    "anyone who can read the logs. Set MASTER_API_KEY to a long random "
                    "value (e.g. `openssl rand -hex 32`) and redeploy."
                ),
                "detail_fa": (
                    "یک کلید ادمین موقت ساخته و در لاگ استارت‌آپ نوشته شد. این کلید با "
                    "هر ری‌استارت عوض می‌شود و دسترسی ادمین را در اختیار هرکسی که لاگ‌ها "
                    "را ببیند می‌گذارد. MASTER_API_KEY را به یک مقدار تصادفی بلند "
                    "(مثلاً `openssl rand -hex 32`) تنظیم کنید و دوباره دیپلوی کنید."
                ),
            }
        )

    # Session secret — both DASHBOARD_SESSION_SECRET and its OAUTH_JWT_SECRET_KEY
    # fallback unset means a random secret is minted per process, so every
    # dashboard + OAuth login is invalidated on each restart/redeploy.
    if not _is_set("DASHBOARD_SESSION_SECRET") and not _is_set("OAUTH_JWT_SECRET_KEY"):
        warnings.append(
            {
                "code": "session_secret_ephemeral",
                "severity": "critical",
                "env": "DASHBOARD_SESSION_SECRET",
                "title_en": "No persistent session secret configured",
                "title_fa": "هیچ secret ماندگاری برای سشن تنظیم نشده است",
                "detail_en": (
                    "Neither DASHBOARD_SESSION_SECRET nor OAUTH_JWT_SECRET_KEY is set, so "
                    "a random secret is generated on each start. All dashboard and login "
                    "sessions are dropped on every restart/redeploy. Set "
                    "DASHBOARD_SESSION_SECRET to a stable random value."
                ),
                "detail_fa": (
                    "نه DASHBOARD_SESSION_SECRET و نه OAUTH_JWT_SECRET_KEY تنظیم نشده‌اند، "
                    "پس در هر بار اجرا یک secret تصادفی ساخته می‌شود و تمام سشن‌های داشبورد "
                    "و لاگین با هر ری‌استارت/ری‌دیپلوی باطل می‌شوند. "
                    "DASHBOARD_SESSION_SECRET را به یک مقدار تصادفی ثابت تنظیم کنید."
                ),
            }
        )

    # ENCRYPTION_KEY — when unset, user site management is disabled (sites
    # cannot be created/edited and credentials cannot be decrypted).
    if not _is_set("ENCRYPTION_KEY"):
        warnings.append(
            {
                "code": "encryption_key_missing",
                "severity": "warning",
                "env": "ENCRYPTION_KEY",
                "title_en": "ENCRYPTION_KEY is not set — site management disabled",
                "title_fa": "ENCRYPTION_KEY تنظیم نشده است — مدیریت سایت غیرفعال است",
                "detail_en": (
                    "Site management is disabled because credentials cannot be encrypted. "
                    "Users cannot add or test services. Generate a key with "
                    '`python -c "import os,base64; print(base64.b64encode(os.urandom(32)).decode())"` '
                    "and set it as ENCRYPTION_KEY."
                ),
                "detail_fa": (
                    "به‌دلیل عدم امکان رمزنگاری credentialها، مدیریت سایت غیرفعال است و "
                    "کاربران نمی‌توانند سرویس اضافه یا تست کنند. یک کلید با "
                    '`python -c "import os,base64; print(base64.b64encode(os.urandom(32)).decode())"` '
                    "بسازید و آن را به‌عنوان ENCRYPTION_KEY تنظیم کنید."
                ),
            }
        )

    # OAUTH_BASE_URL / PUBLIC_URL — required for OAuth login redirects to
    # resolve to the public host instead of the internal container address.
    if not _is_set("OAUTH_BASE_URL") and not _is_set("PUBLIC_URL"):
        warnings.append(
            {
                "code": "public_url_missing",
                "severity": "warning",
                "env": "OAUTH_BASE_URL",
                "title_en": "OAUTH_BASE_URL / PUBLIC_URL is not set",
                "title_fa": "OAUTH_BASE_URL / PUBLIC_URL تنظیم نشده است",
                "detail_en": (
                    "OAuth login redirects and MCP endpoint URLs may resolve to the "
                    "internal container address instead of your public domain. Set "
                    "OAUTH_BASE_URL (or PUBLIC_URL) to your public https URL."
                ),
                "detail_fa": (
                    "ریدایرکت‌های لاگین OAuth و آدرس‌های اندپوینت MCP ممکن است به آدرس "
                    "داخلی کانتینر اشاره کنند نه دامنهٔ عمومی شما. OAUTH_BASE_URL (یا "
                    "PUBLIC_URL) را به آدرس https عمومی‌تان تنظیم کنید."
                ),
            }
        )

    return warnings


def log_startup_config_health(logger) -> None:
    """Emit a single consolidated WARNING block at startup, if needed.

    No-op when the environment is fully configured. Kept dependency-free
    (takes the caller's logger) so it can run early in ``server.py`` before
    other subsystems are initialized.
    """
    warnings = get_config_warnings()
    if not warnings:
        logger.info("Configuration health: all required environment variables are set.")
        return

    n_critical = sum(1 for w in warnings if w["severity"] == "critical")
    lines = [
        "",
        "=" * 72,
        f"CONFIGURATION HEALTH: {len(warnings)} issue(s) detected "
        f"({n_critical} critical). The server will start, but fix these for "
        f"a secure, persistent deployment:",
        "=" * 72,
    ]
    for w in warnings:
        marker = "✗ CRITICAL" if w["severity"] == "critical" else "! WARNING "
        lines.append(f"  {marker}  [{w['env']}] {w['title_en']}")
        lines.append(f"             {w['detail_en']}")
    lines.append("=" * 72)
    logger.warning("\n".join(lines))
