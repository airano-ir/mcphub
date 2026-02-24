"""
Dashboard Routes - Web UI routes for MCP Hub.

Phase K.1: Core Infrastructure
"""

import logging
import os
from datetime import UTC, datetime

from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.templating import Jinja2Templates

from .auth import (
    get_dashboard_auth,
    get_session_display_info,
    get_session_user_id,
    is_admin_session,
)

logger = logging.getLogger(__name__)

# Templates directory (core/templates/ — one level up from core/dashboard/)
TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# Plugin display names mapping (for special cases like n8n)
PLUGIN_DISPLAY_NAMES = {
    "n8n": "n8n",
    "wordpress": "WordPress",
    "wordpress_advanced": "WordPress Advanced",
    "woocommerce": "WooCommerce",
    "directus": "Directus",
    "supabase": "Supabase",
    "gitea": "Gitea",
    "openpanel": "OpenPanel",
    "appwrite": "Appwrite",
}


def get_plugin_display_name(plugin_type: str) -> str:
    """Get the proper display name for a plugin type."""
    if plugin_type in PLUGIN_DISPLAY_NAMES:
        return PLUGIN_DISPLAY_NAMES[plugin_type]
    # Default: replace underscores with spaces and title case
    return plugin_type.replace("_", " ").title()


# Register custom Jinja filter
templates.env.filters["plugin_name"] = get_plugin_display_name

# Register RBAC helpers as Jinja2 globals (available in all templates)
templates.env.globals["is_admin_session"] = is_admin_session
templates.env.globals["get_session_display_info"] = get_session_display_info

# Dashboard translations
DASHBOARD_TRANSLATIONS = {
    "en": {
        # Navigation
        "dashboard": "Dashboard",
        "projects": "Projects",
        "api_keys": "API Keys",
        "oauth_clients": "OAuth Clients",
        "audit_logs": "Audit Logs",
        "health": "Health",
        "settings": "Settings",
        "logout": "Logout",
        # Login page
        "login_title": "Dashboard Login",
        "login_subtitle": "Enter your Master API Key to access the MCP (Model Context Protocol) Hub",
        "api_key_label": "API Key",
        "api_key_placeholder": "sk-... or cmp_...",
        "login_button": "Login",
        "login_error": "Invalid API key or insufficient permissions",
        "rate_limit_error": "Too many login attempts. Please try again later.",
        # Dashboard home
        "welcome": "Welcome to MCP Hub",
        "overview": "Overview",
        "total_projects": "Total Projects",
        "active_api_keys": "Active API Keys",
        "total_tools": "Total Tools",
        "system_uptime": "System Uptime",
        "recent_activity": "Recent Activity",
        "projects_by_type": "Projects by Type",
        "health_status": "Health Status",
        "healthy": "Healthy",
        "warning": "Warning",
        "error": "Error",
        "view_all": "View All",
        "no_activity": "No recent activity",
        # Common
        "loading": "Loading...",
        "error_occurred": "An error occurred",
        "refresh": "Refresh",
        "back": "Back",
        "save": "Save",
        "cancel": "Cancel",
        "delete": "Delete",
        "create": "Create",
        "edit": "Edit",
        "view": "View",
        "search": "Search",
        "filter": "Filter",
        "all": "All",
        "clear": "Clear",
        "online": "Online",
        "offline": "Offline",
        "active": "Active",
        "inactive": "Inactive",
        # Sites (E.3)
        "my_sites": "My Sites",
        "add_site": "Add Site / Connect Service",
        "connect": "Connect",
        "plugin_type": "Plugin Type",
        "site_url": "Site URL",
        "site_alias": "Alias",
        "site_alias_hint": "Friendly name (letters, numbers, hyphens)",
        "status": "Status",
        "actions": "Actions",
        "test_connection": "Test Connection",
        "no_sites": "No sites added yet",
        "add_first_site": "Add your first site to get started",
        "site_added": "Site added successfully",
        "site_deleted": "Site deleted",
        "connection_ok": "Connection OK",
        "connection_failed": "Connection failed",
        "credentials": "Credentials",
        "select_plugin": "Select plugin type",
        "adding_site": "Adding site...",
        "testing": "Testing...",
        "copy": "Copy",
        "copied": "Copied!",
        "api_key_name": "Key Name",
        "generate_key": "Generate API Key",
        "your_api_key": "Your API Key",
        "key_shown_once": "This key will only be shown once. Copy it now!",
        "no_api_keys": "No API keys yet",
        "config_snippets": "Configuration Snippets",
        "select_site": "Select a site",
        "select_client": "Select client",
        "max_sites_reached": "Maximum sites reached",
        # User dashboard
        "my_services": "My Services",
        "active_connections": "Active Connections",
        "user_api_keys": "API Keys",
        "available_tools": "Available Tools",
        "site_status": "Site Status",
        "no_services_yet": "You haven't connected any services yet.",
        "add_first_service": "Add your first service to start using MCP tools.",
        "admin_login": "Admin Login with API Key",
        "profile": "Profile",
        "admin_badge": "Admin",
    },
    "fa": {
        # Navigation
        "dashboard": "داشبورد",
        "projects": "پروژه‌ها",
        "api_keys": "کلیدهای API",
        "oauth_clients": "کلاینت‌های OAuth",
        "audit_logs": "لاگ‌های ممیزی",
        "health": "سلامت",
        "settings": "تنظیمات",
        "logout": "خروج",
        # Login page
        "login_title": "ورود به داشبورد",
        "login_subtitle": "برای دسترسی به هاب MCP (Model Context Protocol)، کلید API مستر خود را وارد کنید",
        "api_key_label": "کلید API",
        "api_key_placeholder": "sk-... یا cmp_...",
        "login_button": "ورود",
        "login_error": "کلید API نامعتبر یا دسترسی ناکافی",
        "rate_limit_error": "تلاش‌های زیاد برای ورود. لطفاً بعداً تلاش کنید.",
        # Dashboard home
        "welcome": "خوش آمدید به MCP Hub",
        "overview": "نمای کلی",
        "total_projects": "کل پروژه‌ها",
        "active_api_keys": "کلیدهای API فعال",
        "total_tools": "کل ابزارها",
        "system_uptime": "آپتایم سیستم",
        "recent_activity": "فعالیت اخیر",
        "projects_by_type": "پروژه‌ها بر اساس نوع",
        "health_status": "وضعیت سلامت",
        "healthy": "سالم",
        "warning": "هشدار",
        "error": "خطا",
        "view_all": "مشاهده همه",
        "no_activity": "فعالیت اخیری وجود ندارد",
        # Common
        "loading": "در حال بارگذاری...",
        "error_occurred": "خطایی رخ داد",
        "refresh": "بروزرسانی",
        "back": "بازگشت",
        "save": "ذخیره",
        "cancel": "لغو",
        "delete": "حذف",
        "create": "ایجاد",
        "edit": "ویرایش",
        "view": "مشاهده",
        "search": "جستجو",
        "filter": "فیلتر",
        "all": "همه",
        "clear": "پاک کردن",
        "online": "آنلاین",
        "offline": "آفلاین",
        "active": "فعال",
        "inactive": "غیرفعال",
        # Sites (E.3)
        "my_sites": "سایت‌های من",
        "add_site": "افزودن سایت / اتصال سرویس",
        "connect": "اتصال",
        "plugin_type": "نوع پلاگین",
        "site_url": "آدرس سایت",
        "site_alias": "نام مستعار",
        "site_alias_hint": "نام دوستانه (حروف، اعداد، خط تیره)",
        "status": "وضعیت",
        "actions": "عملیات",
        "test_connection": "تست اتصال",
        "no_sites": "هنوز سایتی اضافه نشده",
        "add_first_site": "اولین سایت خود را اضافه کنید",
        "site_added": "سایت با موفقیت اضافه شد",
        "site_deleted": "سایت حذف شد",
        "connection_ok": "اتصال برقرار",
        "connection_failed": "اتصال ناموفق",
        "credentials": "مشخصات دسترسی",
        "select_plugin": "نوع پلاگین را انتخاب کنید",
        "adding_site": "در حال افزودن سایت...",
        "testing": "در حال تست...",
        "copy": "کپی",
        "copied": "کپی شد!",
        "api_key_name": "نام کلید",
        "generate_key": "تولید کلید API",
        "your_api_key": "کلید API شما",
        "key_shown_once": "این کلید فقط یکبار نمایش داده می‌شود. الان کپی کنید!",
        "no_api_keys": "هنوز کلید API ندارید",
        "config_snippets": "نمونه کدهای پیکربندی",
        "select_site": "انتخاب سایت",
        "select_client": "انتخاب کلاینت",
        "max_sites_reached": "حداکثر سایت‌ها رسیده است",
        # User dashboard
        "my_services": "سرویس‌های من",
        "active_connections": "اتصالات فعال",
        "user_api_keys": "کلیدهای API",
        "available_tools": "ابزارهای موجود",
        "site_status": "وضعیت سایت‌ها",
        "no_services_yet": "هنوز سرویسی متصل نکرده‌اید.",
        "add_first_service": "اولین سرویس خود را اضافه کنید تا از ابزارهای MCP استفاده کنید.",
        "admin_login": "ورود مدیر با کلید API",
        "profile": "پروفایل",
        "admin_badge": "مدیر",
    },
}


def detect_language(accept_language: str | None, query_lang: str | None = None) -> str:
    """Detect language from query parameter. Default is English."""
    if query_lang and query_lang in DASHBOARD_TRANSLATIONS:
        return query_lang

    return "en"


def get_translations(lang: str) -> dict:
    """Get translations for a language."""
    return DASHBOARD_TRANSLATIONS.get(lang, DASHBOARD_TRANSLATIONS["en"])


def get_client_ip(request: Request) -> str:
    """Get client IP from request, handling proxies."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def get_dashboard_stats() -> dict:
    """Get dashboard statistics."""
    stats = {
        "projects_count": 0,
        "api_keys_count": 0,
        "tools_count": 0,
        "uptime_percent": 99.9,
        "uptime_days": 0,
    }

    try:
        # Get projects count
        from core.site_manager import get_site_manager

        site_manager = get_site_manager()
        sites = site_manager.list_all_sites()
        stats["projects_count"] = len(sites)

        # Get API keys count
        from core.api_keys import get_api_key_manager

        api_key_manager = get_api_key_manager()
        keys = api_key_manager.list_keys()
        stats["api_keys_count"] = len([k for k in keys if not k.get("revoked", False)])

        # Get tools count
        from core.tool_registry import get_tool_registry

        tool_registry = get_tool_registry()
        stats["tools_count"] = len(tool_registry.get_all())

        # Get uptime
        from core.health import get_health_monitor

        health_monitor = get_health_monitor()
        system_metrics = health_monitor.get_system_metrics()
        stats["uptime_days"] = system_metrics.uptime_seconds / 86400

    except Exception as e:
        logger.warning(f"Error getting dashboard stats: {e}")

    return stats


async def get_user_dashboard_stats(user_id: str) -> dict:
    """Get dashboard statistics for an OAuth user."""
    stats = {
        "sites_count": 0,
        "active_sites_count": 0,
        "api_keys_count": 0,
        "tools_count": 0,
    }
    try:
        from core.site_api import get_user_sites

        sites = await get_user_sites(user_id)
        stats["sites_count"] = len(sites)
        stats["active_sites_count"] = len([s for s in sites if s.get("status") == "active"])
    except Exception as e:
        logger.warning(f"Error getting user sites count: {e}")

    try:
        from core.user_keys import get_user_key_manager

        key_mgr = get_user_key_manager()
        keys = await key_mgr.list_keys(user_id)
        stats["api_keys_count"] = len(keys)
    except Exception as e:
        logger.debug(f"Error getting user keys count: {e}")

    try:
        from core.tool_registry import get_tool_registry

        tool_registry = get_tool_registry()
        stats["tools_count"] = len(tool_registry.get_all())
    except Exception:
        stats["tools_count"] = 596  # Fallback

    return stats


async def get_user_sites_summary(user_id: str) -> list:
    """Get a summary of user's sites with status for dashboard display."""
    try:
        from core.site_api import get_user_sites

        return await get_user_sites(user_id)
    except Exception as e:
        logger.warning(f"Error getting user sites summary: {e}")
        return []


async def get_projects_by_type() -> dict:
    """Get projects grouped by plugin type."""
    projects_by_type = {}

    try:
        from core.site_manager import get_site_manager

        site_manager = get_site_manager()
        sites = site_manager.list_all_sites()

        for site in sites:
            plugin_type = site.get("plugin_type", "unknown")
            if plugin_type not in projects_by_type:
                projects_by_type[plugin_type] = 0
            projects_by_type[plugin_type] += 1

    except Exception as e:
        logger.warning(f"Error getting projects by type: {e}")

    return projects_by_type


async def get_recent_activity(limit: int = 10) -> list:
    """Get recent activity from audit logs."""
    activity = []

    try:
        from core.audit_log import get_audit_logger

        audit_logger = get_audit_logger()

        # Fetch extra entries because we filter some out
        entries = audit_logger.get_recent_entries(limit=limit * 3)

        for entry in entries:
            # Skip internal/noise events
            evt = entry.get("event_type", "")
            if evt in ("health_metric_recorded", "health_check"):
                continue

            project = (entry.get("metadata") or {}).get("project_id") or "-"

            activity.append(
                {
                    "timestamp": entry.get("timestamp") or "",
                    "type": evt or "unknown",
                    "message": entry.get("message") or "",
                    "project": project if project != "None" else "-",
                    "level": entry.get("level") or "INFO",
                }
            )

            # Stop once we have enough
            if len(activity) >= limit:
                break

    except Exception as e:
        logger.warning(f"Error getting recent activity: {e}")

    return activity


async def get_health_summary() -> dict:
    """Get health status summary."""
    summary = {
        "status": "healthy",
        "components": {
            "core": "healthy",
            "auth": "healthy",
            "rate_limit": "healthy",
        },
        "last_check": datetime.now(UTC).isoformat(),
    }

    try:
        from core.health import get_health_monitor

        health_monitor = get_health_monitor()
        system_metrics = health_monitor.get_system_metrics()

        # Determine status based on error rate
        if system_metrics.error_rate_percent > 25:
            summary["status"] = "unhealthy"
        elif system_metrics.error_rate_percent > 10:
            summary["status"] = "degraded"
        else:
            summary["status"] = "healthy"

    except Exception as e:
        logger.warning(f"Error getting health summary: {e}")
        summary["status"] = "unknown"

    return summary


# Route handlers


async def dashboard_login_page(request: Request) -> Response:
    """Render dashboard login page."""
    auth = get_dashboard_auth()

    # Check if already logged in
    session = auth.get_session_from_request(request) or auth.get_user_session_from_request(request)
    if session:
        return RedirectResponse(url="/dashboard", status_code=303)

    # Get language
    accept_language = request.headers.get("accept-language")
    query_lang = request.query_params.get("lang")
    lang = detect_language(accept_language, query_lang)
    t = get_translations(lang)

    error = request.query_params.get("error")
    next_url = request.query_params.get("next", "/dashboard")

    return templates.TemplateResponse(
        "dashboard/login.html",
        {
            "request": request,
            "lang": lang,
            "t": t,
            "error": error,
            "next_url": next_url,
            "version": _get_project_version(),
        },
    )


async def dashboard_login_submit(request: Request) -> Response:
    """Handle dashboard login form submission."""
    auth = get_dashboard_auth()

    # Get language
    accept_language = request.headers.get("accept-language")
    lang = detect_language(accept_language)
    get_translations(lang)

    # Get client IP for rate limiting
    client_ip = get_client_ip(request)

    # Check rate limit
    if not auth.check_rate_limit(client_ip):
        logger.warning(f"Dashboard login rate limit exceeded for {client_ip}")
        return RedirectResponse(
            url=f"/dashboard/login?error=rate_limit&lang={lang}",
            status_code=303,
        )

    # Record login attempt
    auth.record_login_attempt(client_ip)

    # Get form data
    form = await request.form()
    api_key = form.get("api_key", "")
    next_url = form.get("next", "/dashboard")

    # Validate API key
    is_valid, user_type, key_id = auth.validate_api_key(api_key)

    if not is_valid:
        logger.warning(f"Dashboard login failed for {client_ip}")

        # Log failed authentication attempt
        try:
            from core.audit_log import get_audit_logger

            audit_logger = get_audit_logger()
            if audit_logger:
                audit_logger.log_authentication(
                    success=False,
                    reason="Invalid API key or insufficient permissions",
                    ip_address=client_ip,
                )
        except Exception as e:
            logger.warning(f"Failed to log auth event: {e}")

        return RedirectResponse(
            url=f"/dashboard/login?error=invalid&next={next_url}&lang={lang}",
            status_code=303,
        )

    # Create session
    token = auth.create_session(user_type, key_id)

    # Redirect to dashboard
    response = RedirectResponse(url=next_url, status_code=303)
    auth.set_session_cookie(response, token)

    # Log successful authentication
    try:
        from core.audit_log import get_audit_logger

        audit_logger = get_audit_logger()
        if audit_logger:
            audit_logger.log_authentication(success=True, ip_address=client_ip)
    except Exception as e:
        logger.warning(f"Failed to log auth event: {e}")
        logger.info(f"Dashboard login successful: type={user_type}, ip={client_ip}")
    return response


async def auth_logout(request: Request) -> Response:
    """Clear OAuth user session cookie."""
    from core.dashboard.auth import get_dashboard_auth

    auth = get_dashboard_auth()
    response = RedirectResponse(url="/auth/login", status_code=303)
    auth.clear_session_cookie(response)
    client_ip = request.client.host if request.client else "unknown"
    # Log logout event
    try:
        from core.audit_log import get_audit_logger

        audit_logger = get_audit_logger()
        if audit_logger:
            audit_logger.log_system_event(
                event="Dashboard logout", details={"ip_address": client_ip}
            )
    except Exception as e:
        logger.warning(f"Failed to log logout event: {e}")

    logger.info(f"Dashboard logout from {client_ip}")
    return response


# Alias for backwards compatibility with __init__.py and other routes
dashboard_logout = auth_logout


async def dashboard_home(request: Request) -> Response:
    """Render dashboard home page."""
    auth = get_dashboard_auth()

    # Check authentication
    redirect = auth.require_auth(request)
    if redirect:
        return redirect

    session = auth.get_session_from_request(request) or auth.get_user_session_from_request(request)
    admin = is_admin_session(session)
    display_info = get_session_display_info(session)
    user_id = get_session_user_id(session)

    # Get language
    accept_language = request.headers.get("accept-language")
    query_lang = request.query_params.get("lang")
    lang = detect_language(accept_language, query_lang)
    t = get_translations(lang)

    context = {
        "request": request,
        "lang": lang,
        "t": t,
        "session": session,
        "is_admin": admin,
        "display_info": display_info,
        "current_page": "dashboard",
    }

    if admin:
        # Admin dashboard — full system stats
        stats = await get_dashboard_stats()
        projects_by_type = await get_projects_by_type()
        recent_activity = await get_recent_activity(limit=5)
        health_summary = await get_health_summary()
        context.update(
            {
                "stats": stats,
                "projects_by_type": projects_by_type,
                "recent_activity": recent_activity,
                "health_summary": health_summary,
            }
        )
    else:
        # User dashboard — personal stats
        user_stats = await get_user_dashboard_stats(user_id) if user_id else {}
        user_sites = await get_user_sites_summary(user_id) if user_id else []
        context.update(
            {
                "stats": user_stats,
                "user_sites": user_sites,
            }
        )

    return templates.TemplateResponse("dashboard/index.html", context)


async def dashboard_api_stats(request: Request) -> Response:
    """API endpoint for dashboard stats."""
    auth = get_dashboard_auth()

    # Check authentication
    session = auth.get_session_from_request(request) or auth.get_user_session_from_request(request)
    if not session:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    if is_admin_session(session):
        stats = await get_dashboard_stats()
        projects_by_type = await get_projects_by_type()
        health_summary = await get_health_summary()
    else:
        user_id = get_session_user_id(session)
        stats = await get_user_dashboard_stats(user_id) if user_id else {}
        projects_by_type = {}
        health_summary = {"status": "n/a"}

    return JSONResponse(
        {
            "stats": stats,
            "projects_by_type": projects_by_type,
            "health": health_summary,
        }
    )


# ============================================================
# Projects Routes (Phase K.2)
# ============================================================


def get_cached_health_status(project_id: str) -> dict:
    """
    Get cached health status for a project without performing new health check.

    Returns:
        dict with keys: status ('healthy', 'warning', 'unhealthy', 'unknown'),
                       last_check (ISO string or None),
                       error_rate (float)
    """
    try:
        from core.health import get_health_monitor

        health_monitor = get_health_monitor()

        if not health_monitor:
            return {"status": "unknown", "last_check": None, "error_rate": 0, "reason": None}

        # First check the latest active health status
        latest = health_monitor.latest_health_status.get(project_id)
        if latest:
            if latest.healthy:
                status = "healthy"
            elif 0 < latest.error_rate_percent <= 10:
                # If recently slightly failing
                status = "warning"
            else:
                status = "unhealthy"

            reason = latest.recent_errors[-1] if latest.recent_errors else None
            return {
                "status": status,
                "last_check": latest.last_check.isoformat() if latest.last_check else None,
                "error_rate": latest.error_rate_percent,
                "reason": reason,
            }

        # Fallback to cached metrics (last 24 hours) if no active check exists yet
        metrics = health_monitor.get_project_metrics(project_id, hours=24)

        if not metrics or metrics.get("total_requests", 0) == 0:
            return {"status": "unknown", "last_check": None, "error_rate": 0, "reason": None}

        error_rate = metrics.get("error_rate_percent", 0)

        # Determine status based on error rate
        if error_rate > 25:
            status = "unhealthy"
        elif error_rate > 10:
            status = "warning"
        else:
            status = "healthy"

        # Get last check time from metrics history
        last_check = None
        if project_id in health_monitor.metrics_history:
            history = health_monitor.metrics_history[project_id]
            if history:
                last_check = history[-1].timestamp.isoformat()

        return {
            "status": status,
            "last_check": last_check,
            "error_rate": error_rate,
            "reason": None,
        }
    except Exception as e:
        logger.warning(f"Error getting cached health for {project_id}: {e}")
        return {"status": "unknown", "last_check": None, "error_rate": 0}


async def get_all_projects(
    plugin_type: str | None = None,
    search: str | None = None,
    status_filter: str | None = None,
    page: int = 1,
    per_page: int = 20,
    user_session: dict | object | None = None,
) -> dict:
    """Get all projects with optional filtering."""
    projects = []
    available_plugin_types = set()

    try:
        from core.site_manager import get_site_manager

        site_manager = get_site_manager()
        sites = site_manager.list_all_sites()

        is_master = False
        current_user_id = None
        if user_session:
            if hasattr(user_session, "user_type") and user_session.user_type == "master":
                is_master = True
            elif isinstance(user_session, dict) and "user_id" in user_session:
                current_user_id = user_session["user_id"]

        for site in sites:
            # Tenant isolation checks
            site_user_id = site.get("user_id")
            if not is_master:
                if site_user_id != current_user_id:
                    continue

            site_plugin_type = site.get("plugin_type", "unknown")
            available_plugin_types.add(site_plugin_type)

            # Apply filters
            if plugin_type and site_plugin_type != plugin_type:
                continue

            site_id = site.get("site_id", "")
            alias = site.get("alias", "")
            full_id = f"{site_plugin_type}_{site_id}"

            if search:
                search_lower = search.lower()
                if (
                    search_lower not in site_id.lower()
                    and search_lower not in alias.lower()
                    and search_lower not in site_plugin_type.lower()
                    and search_lower not in full_id.lower()
                ):
                    continue

            # Get cached health status
            cached_health = get_cached_health_status(full_id)

            # Apply status filter
            if status_filter and cached_health["status"] != status_filter:
                continue

            projects.append(
                {
                    "site_id": site_id,
                    "plugin_type": site_plugin_type,
                    "alias": alias,
                    "full_id": full_id,
                    "url": site.get("url", ""),
                    "health_status": cached_health["status"],
                    "last_health_check": cached_health["last_check"],
                    "error_rate": cached_health["error_rate"],
                    "reason": cached_health.get("reason"),
                }
            )

    except Exception as e:
        logger.warning(f"Error getting projects: {e}")

    # Pagination
    total_count = len(projects)
    total_pages = max(1, (total_count + per_page - 1) // per_page)
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_projects = projects[start_idx:end_idx]

    return {
        "projects": paginated_projects,
        "total_count": total_count,
        "total_pages": total_pages,
        "current_page": page,
        "per_page": per_page,
        "available_plugin_types": sorted(available_plugin_types),
    }


async def get_project_detail(project_id: str) -> dict | None:
    """Get detailed information about a specific project."""
    try:
        from core.api_keys import get_api_key_manager
        from core.audit_log import get_audit_logger
        from core.site_manager import get_site_manager
        from core.tool_registry import get_tool_registry

        site_manager = get_site_manager()

        # Parse project_id (format: plugin_type_site_id)
        parts = project_id.split("_", 1)
        if len(parts) < 2:
            return None

        plugin_type = parts[0]
        site_id = parts[1]

        # Find the site
        sites = site_manager.list_all_sites()
        site = None
        for s in sites:
            if s.get("plugin_type") == plugin_type and s.get("site_id") == site_id:
                site = s
                break

        if not site:
            # Try matching full_id directly
            for s in sites:
                full_id = f"{s.get('plugin_type')}_{s.get('site_id')}"
                if full_id == project_id:
                    site = s
                    plugin_type = s.get("plugin_type")
                    site_id = s.get("site_id")
                    break

        if not site:
            return None

        # Get tools for this plugin type
        tool_registry = get_tool_registry()
        all_tools = tool_registry.get_all()
        plugin_tools = [
            {
                "name": (
                    t.name.replace(f"{plugin_type}_", "")
                    if t.name.startswith(f"{plugin_type}_")
                    else t.name
                ),
                "description": t.description,
                "scope": t.required_scope,
            }
            for t in all_tools
            if t.plugin_type == plugin_type
        ]

        # Get API keys for this project
        api_key_manager = get_api_key_manager()
        all_keys = api_key_manager.list_keys()
        project_keys = [
            k
            for k in all_keys
            if not k.get("revoked")
            and (k.get("project_id") == project_id or k.get("project_id") == "*")
        ]

        # Get recent activity for this project
        audit_logger = get_audit_logger()
        recent_entries = audit_logger.get_recent_entries(limit=60)
        project_activity = [
            e
            for e in recent_entries
            if (
                e.get("metadata", {}).get("project_id") == project_id
                or e.get("metadata", {}).get("site") == site_id
            )
            and e.get("event_type", "") not in ("health_metric_recorded", "health_check")
        ][:5]

        # Get cached health status
        cached_health = get_cached_health_status(project_id)

        # Get request count from metrics
        requests_24h = 0
        try:
            from core.health import get_health_monitor

            health_monitor = get_health_monitor()
            if health_monitor:
                metrics = health_monitor.get_project_metrics(project_id, hours=24)
                requests_24h = metrics.get("total_requests", 0)
        except Exception:
            pass

        return {
            "site_id": site_id,
            "plugin_type": plugin_type,
            "alias": site.get("alias", ""),
            "full_id": project_id,
            "url": site.get("url", ""),
            "health": {
                "status": cached_health["status"],
                "last_check": cached_health["last_check"],
                "error_rate": cached_health["error_rate"],
            },
            "tools": plugin_tools,
            "tools_count": len(plugin_tools),
            "api_keys_count": len(project_keys),
            "requests_24h": requests_24h,
            "recent_activity": project_activity,
        }

    except Exception as e:
        logger.warning(f"Error getting project detail: {e}")
        return None


async def dashboard_projects_list(request: Request) -> Response:
    """Render projects list page (admin only)."""
    session, redirect = _require_admin_session(request)
    if redirect:
        return redirect

    # Get language
    accept_language = request.headers.get("accept-language")
    query_lang = request.query_params.get("lang")
    lang = detect_language(accept_language, query_lang)
    t = get_translations(lang)

    # Get query parameters
    plugin_type = request.query_params.get("plugin_type", "")
    search = request.query_params.get("search", "")
    status = request.query_params.get("status", "")
    page = int(request.query_params.get("page", 1))

    # Get projects
    projects_data = await get_all_projects(
        plugin_type=plugin_type if plugin_type else None,
        search=search if search else None,
        status_filter=status if status else None,
        page=page,
        user_session=session,
    )

    return templates.TemplateResponse(
        "dashboard/projects/list.html",
        {
            "request": request,
            "lang": lang,
            "t": t,
            "session": session,
            "projects": projects_data["projects"],
            "total_count": projects_data["total_count"],
            "total_pages": projects_data["total_pages"],
            "page_number": projects_data["current_page"],
            "per_page": projects_data["per_page"],
            "available_plugin_types": projects_data["available_plugin_types"],
            "selected_plugin_type": plugin_type,
            "selected_status": status,
            "search_query": search,
            "current_page": "projects",
        },
    )


async def dashboard_project_detail(request: Request) -> Response:
    """Render project detail page."""
    auth = get_dashboard_auth()

    # Check authentication
    redirect = auth.require_auth(request)
    if redirect:
        return redirect

    session = auth.get_session_from_request(request) or auth.get_user_session_from_request(request)

    # Get language
    accept_language = request.headers.get("accept-language")
    query_lang = request.query_params.get("lang")
    lang = detect_language(accept_language, query_lang)
    t = get_translations(lang)

    # Get project ID from path
    project_id = request.path_params.get("project_id", "")

    # Get project detail
    project = await get_project_detail(project_id)

    if not project:
        return templates.TemplateResponse(
            "dashboard/projects/list.html",
            {
                "request": request,
                "lang": lang,
                "t": t,
                "session": session,
                "projects": [],
                "error": f"Project '{project_id}' not found",
                "current_page": "projects",
            },
            status_code=404,
        )

    return templates.TemplateResponse(
        "dashboard/projects/detail.html",
        {
            "request": request,
            "lang": lang,
            "t": t,
            "session": session,
            "project": project,
            "current_page": "projects",
        },
    )


async def dashboard_api_projects(request: Request) -> Response:
    """API endpoint for projects list."""
    auth = get_dashboard_auth()

    # Check authentication
    session = auth.get_session_from_request(request) or auth.get_user_session_from_request(request)
    if not session:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    # Get query parameters
    plugin_type = request.query_params.get("plugin_type")
    search = request.query_params.get("search")
    page = int(request.query_params.get("page", 1))

    projects_data = await get_all_projects(
        plugin_type=plugin_type,
        search=search,
        page=page,
        user_session=session,
    )

    return JSONResponse(projects_data)


async def dashboard_api_project_detail(request: Request) -> Response:
    """API endpoint for project detail."""
    auth = get_dashboard_auth()

    # Check authentication
    session = auth.get_session_from_request(request) or auth.get_user_session_from_request(request)
    if not session:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    project_id = request.path_params.get("project_id", "")
    project = await get_project_detail(project_id)

    if not project:
        return JSONResponse({"error": "Project not found"}, status_code=404)

    return JSONResponse(project)


async def dashboard_project_health_check(request: Request) -> Response:
    """API endpoint to check health of a specific project."""
    logger.debug(f"Health check request received: {request.url.path}")

    auth = get_dashboard_auth()

    # Check authentication
    session = auth.get_session_from_request(request) or auth.get_user_session_from_request(request)
    if not session:
        logger.warning("Health check unauthorized - no session")
        return JSONResponse({"error": "Unauthorized", "status": "error"}, status_code=401)

    project_id = request.path_params.get("project_id", "")
    logger.debug(f"Health check for project_id: {project_id}")

    if not project_id:
        return JSONResponse({"error": "Project ID required", "status": "error"}, status_code=400)

    try:
        from core.health import get_health_monitor

        health_monitor = get_health_monitor()
        if not health_monitor:
            logger.warning("Health monitor not initialized")
            return JSONResponse(
                {
                    "status": "unknown",
                    "message": "Health monitor not available",
                    "project_id": project_id,
                }
            )

        # Check project health - returns ProjectHealthStatus dataclass
        logger.debug(f"Calling check_project_health for: {project_id}")
        health_result = await health_monitor.check_project_health(project_id)
        logger.debug(f"Health result: healthy={health_result.healthy}")

        # Log the health check
        try:
            from core.audit_log import get_audit_logger

            audit_logger = get_audit_logger()
            if audit_logger:
                audit_logger.log_system_event(
                    event=f"Health check performed for project {project_id}",
                    details={
                        "project_id": project_id,
                        "status": "healthy" if health_result.healthy else "unhealthy",
                    },
                )
        except Exception as audit_err:
            logger.warning(f"Failed to log health check audit: {audit_err}")

        return JSONResponse(
            {
                "status": "healthy" if health_result.healthy else "unhealthy",
                "project_id": project_id,
                "response_time_ms": health_result.response_time_ms,
                "error_rate_percent": health_result.error_rate_percent,
                "last_check": (
                    health_result.last_check.isoformat() if health_result.last_check else ""
                ),
                "message": "Health check completed successfully",
            }
        )
    except Exception as e:
        logger.error(f"Health check failed for {project_id}: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return JSONResponse(
            {"status": "error", "project_id": project_id, "message": str(e)}, status_code=500
        )


# =============================================================================
# K.3: API Keys Management
# =============================================================================


async def get_all_api_keys(
    project_id: str | None = None,
    status: str = "active",
    search: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> dict:
    """Get all API keys with optional filtering."""
    from core.api_keys import get_api_key_manager

    api_key_manager = get_api_key_manager()
    include_revoked = status in ("all", "revoked")

    all_keys = api_key_manager.list_keys(
        project_id=project_id if project_id and project_id != "*" else None,
        include_revoked=include_revoked,
    )

    # Filter by status
    if status == "revoked":
        all_keys = [k for k in all_keys if k.get("revoked")]
    elif status == "active":
        all_keys = [k for k in all_keys if not k.get("revoked")]

    # Filter by project_id = "*" (global keys)
    if project_id == "*":
        all_keys = [k for k in all_keys if k.get("project_id") == "*"]

    # Search filter
    if search:
        search_lower = search.lower()
        all_keys = [
            k
            for k in all_keys
            if search_lower in (k.get("description") or "").lower()
            or search_lower in k.get("key_id", "").lower()
            or search_lower in k.get("project_id", "").lower()
        ]

    # Pagination
    total_count = len(all_keys)
    total_pages = max(1, (total_count + per_page - 1) // per_page)
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_keys = all_keys[start_idx:end_idx]

    return {
        "api_keys": paginated_keys,
        "total_count": total_count,
        "total_pages": total_pages,
        "current_page": page,
        "per_page": per_page,
    }


async def dashboard_api_keys_list(request: Request) -> Response:
    """Render API keys list page (admin only)."""
    session, redirect = _require_admin_session(request)
    if redirect:
        return redirect

    # Get language
    accept_language = request.headers.get("accept-language")
    query_lang = request.query_params.get("lang")
    lang = detect_language(accept_language, query_lang)
    t = get_translations(lang)

    # Get query parameters
    project_filter = request.query_params.get("project", "")
    status_filter = request.query_params.get("status", "active")
    search = request.query_params.get("search", "")
    page = int(request.query_params.get("page", 1))

    # Get API keys
    keys_data = await get_all_api_keys(
        project_id=project_filter if project_filter else None,
        status=status_filter,
        search=search if search else None,
        page=page,
    )

    # Get available projects for filter dropdown
    from core.site_manager import get_site_manager

    site_manager = get_site_manager()
    available_projects = site_manager.list_all_sites()

    return templates.TemplateResponse(
        "dashboard/api-keys/list.html",
        {
            "request": request,
            "lang": lang,
            "t": t,
            "session": session,
            "api_keys": keys_data["api_keys"],
            "total_count": keys_data["total_count"],
            "total_pages": keys_data["total_pages"],
            "page_number": keys_data["current_page"],
            "per_page": keys_data["per_page"],
            "available_projects": available_projects,
            "selected_project": project_filter,
            "selected_status": status_filter,
            "search_query": search,
            "current_page": "api_keys",
        },
    )


async def dashboard_api_keys_create(request: Request) -> Response:
    """API endpoint to create a new API key (admin only)."""
    session, redirect = _require_admin_session(request)
    if redirect:
        return JSONResponse({"error": "Admin access required"}, status_code=403)

    try:
        data = await request.json()
        project_id = data.get("project_id", "*")
        scope = data.get("scope", "read")
        description = data.get("description")
        expires_in_days = data.get("expires_in_days")

        from core.api_keys import get_api_key_manager

        api_key_manager = get_api_key_manager()

        result = api_key_manager.create_key(
            project_id=project_id,
            scope=scope,
            description=description,
            expires_in_days=expires_in_days,
        )

        # Log the action
        from core.audit_log import get_audit_logger

        audit_logger = get_audit_logger()
        audit_logger.log_system_event(
            event=f"API key created for project {project_id}",
            details={
                "key_id": result["key_id"],
                "project_id": project_id,
                "scope": scope,
            },
        )

        return JSONResponse(
            {
                "success": True,
                "key": result["key"],
                "key_id": result["key_id"],
            }
        )

    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except Exception as e:
        logger.error(f"Error creating API key: {e}")
        return JSONResponse({"error": "Failed to create key"}, status_code=500)


async def dashboard_api_keys_revoke(request: Request) -> Response:
    """API endpoint to revoke an API key (admin only)."""
    session, redirect = _require_admin_session(request)
    if redirect:
        return JSONResponse({"error": "Admin access required"}, status_code=403)

    try:
        key_id = request.path_params.get("key_id", "")

        from core.api_keys import get_api_key_manager

        api_key_manager = get_api_key_manager()

        success = api_key_manager.revoke_key(key_id)

        if success:
            # Log the action
            from core.audit_log import get_audit_logger

            audit_logger = get_audit_logger()
            audit_logger.log_system_event(
                event=f"API key {key_id} revoked", details={"key_id": key_id}
            )
            return JSONResponse({"success": True})
        else:
            return JSONResponse({"error": "Key not found"}, status_code=404)
    except Exception as e:
        logger.error(f"Error revoking API key: {e}")
        return JSONResponse({"error": "Failed to revoke key"}, status_code=500)


async def dashboard_api_keys_delete(request: Request) -> Response:
    """API endpoint to delete an API key (admin only)."""
    session, redirect = _require_admin_session(request)
    if redirect:
        return JSONResponse({"error": "Admin access required"}, status_code=403)

    try:
        key_id = request.path_params.get("key_id", "")

        from core.api_keys import get_api_key_manager

        api_key_manager = get_api_key_manager()

        success = api_key_manager.delete_key(key_id)

        if success:
            # Log the action
            from core.audit_log import get_audit_logger

            audit_logger = get_audit_logger()
            audit_logger.log_system_event(
                event=f"API key {key_id} deleted", details={"key_id": key_id}
            )
            return JSONResponse({"success": True})
        else:
            return JSONResponse({"error": "Key not found"}, status_code=404)
    except Exception as e:
        logger.error(f"Error deleting API key: {e}")
        return JSONResponse({"error": "Failed to delete key"}, status_code=500)


# =============================================================================
# K.4: OAuth Clients Management
# =============================================================================


async def get_oauth_clients_data() -> dict:
    """Get OAuth clients data."""
    from core.oauth.client_registry import get_client_registry

    try:
        client_registry = get_client_registry()
        clients = client_registry.list_clients()

        clients_list = []
        for client in clients:
            clients_list.append(
                {
                    "client_id": client.client_id,
                    "client_name": client.client_name,
                    "redirect_uris": client.redirect_uris,
                    "grant_types": client.grant_types,
                    "allowed_scopes": client.allowed_scopes,
                    "created_at": client.created_at.isoformat() if client.created_at else "",
                }
            )

        return {
            "clients": clients_list,
            "total_count": len(clients_list),
        }
    except Exception as e:
        logger.warning(f"Error getting OAuth clients: {e}")
        return {
            "clients": [],
            "total_count": 0,
        }


async def dashboard_oauth_clients_list(request: Request) -> Response:
    """Render OAuth clients list page (admin only)."""
    session, redirect = _require_admin_session(request)
    if redirect:
        return redirect

    # Get language
    accept_language = request.headers.get("accept-language")
    query_lang = request.query_params.get("lang")
    lang = detect_language(accept_language, query_lang)
    t = get_translations(lang)

    # Get clients data
    clients_data = await get_oauth_clients_data()

    return templates.TemplateResponse(
        "dashboard/oauth-clients/list.html",
        {
            "request": request,
            "lang": lang,
            "t": t,
            "session": session,
            "clients": clients_data["clients"],
            "total_count": clients_data["total_count"],
            "current_page": "oauth_clients",
        },
    )


async def dashboard_oauth_clients_create(request: Request) -> Response:
    """API endpoint to create OAuth client (admin only)."""
    session, redirect = _require_admin_session(request)
    if redirect:
        return JSONResponse({"error": "Admin access required"}, status_code=403)

    try:
        data = await request.json()
        client_name = data.get("client_name")
        # Support both single redirect_uri and multiple redirect_uris
        redirect_uris = data.get("redirect_uris") or []
        if not redirect_uris and data.get("redirect_uri"):
            redirect_uris = [data.get("redirect_uri")]
        scopes = data.get("scopes", ["read"])

        if not client_name or not redirect_uris:
            return JSONResponse({"error": "Missing required fields"}, status_code=400)

        from core.oauth.client_registry import get_client_registry

        client_registry = get_client_registry()

        client_id, client_secret = client_registry.create_client(
            client_name=client_name, redirect_uris=redirect_uris, allowed_scopes=scopes
        )

        # Log the action
        from core.audit_log import get_audit_logger

        audit_logger = get_audit_logger()
        audit_logger.log_system_event(
            event=f"OAuth client created: {client_name}", details={"client_id": client_id}
        )

        return JSONResponse(
            {
                "success": True,
                "client_id": client_id,
                "client_secret": client_secret,
            }
        )

    except Exception as e:
        logger.error(f"Error creating OAuth client: {e}")
        return JSONResponse({"error": "Failed to create client"}, status_code=500)


async def dashboard_oauth_clients_delete(request: Request) -> Response:
    """API endpoint to delete OAuth client (admin only)."""
    session, redirect = _require_admin_session(request)
    if redirect:
        return JSONResponse({"error": "Admin access required"}, status_code=403)

    try:
        client_id = request.path_params.get("client_id", "")

        from core.oauth.client_registry import get_client_registry

        client_registry = get_client_registry()

        success = client_registry.delete_client(client_id)

        if success:
            # Log the action
            from core.audit_log import get_audit_logger

            audit_logger = get_audit_logger()
            audit_logger.log_system_event(
                event=f"OAuth client deleted: {client_id}", details={"client_id": client_id}
            )
            return JSONResponse({"success": True})
        else:
            return JSONResponse({"error": "Client not found"}, status_code=404)

    except Exception as e:
        logger.error(f"Error deleting OAuth client: {e}")
        return JSONResponse({"error": "Failed to delete client"}, status_code=500)


# =============================================================================
# K.4: Audit Logs Management
# =============================================================================


async def get_audit_logs_data(
    event_type: str | None = None,
    level: str | None = None,
    date: str | None = None,
    search: str | None = None,
    project_id: str | None = None,
    page: int = 1,
    per_page: int = 50,
) -> dict:
    """Get audit logs with optional filtering."""
    from core.audit_log import EventType, LogLevel, get_audit_logger

    audit_logger = get_audit_logger()

    # Convert string filters to enum if provided
    event_type_enum = None
    if event_type:
        try:
            event_type_enum = EventType(event_type)
        except ValueError:
            pass

    level_enum = None
    if level:
        try:
            level_enum = LogLevel(level)
        except ValueError:
            pass

    # Parse date filter
    start_time = None
    end_time = None
    if date:
        try:
            from datetime import datetime, timedelta

            date_obj = datetime.strptime(date, "%Y-%m-%d")
            start_time = date_obj.replace(tzinfo=UTC)
            end_time = start_time + timedelta(days=1)
        except ValueError:
            pass

    # Get logs with filters
    all_logs = audit_logger.get_logs(
        event_type=event_type_enum,
        level=level_enum,
        start_time=start_time,
        end_time=end_time,
        limit=1000,  # Get more for search filtering
    )

    # Apply project filter - check both project_id and site fields
    if project_id:
        project_id_lower = project_id.lower()
        # Extract site_id from project_id (e.g., "wordpress_site1" -> "site1")
        site_part = project_id.split("_", 1)[1] if "_" in project_id else project_id
        site_part_lower = site_part.lower()

        all_logs = [
            log
            for log in all_logs
            if (
                str(log.get("project_id", "")).lower() == project_id_lower
                or str(log.get("site", "")).lower() == site_part_lower
                or str(log.get("site", "")).lower() == project_id_lower
                or
                # Also check in metadata/details
                str(
                    log.get("details", {}).get("project_id", "")
                    if isinstance(log.get("details"), dict)
                    else ""
                ).lower()
                == project_id_lower
            )
        ]

    # Apply search filter
    if search:
        search_lower = search.lower()
        all_logs = [
            log
            for log in all_logs
            if search_lower in str(log.get("event", "")).lower()
            or search_lower in str(log.get("tool_name", "")).lower()
            or search_lower in str(log.get("project_id", "")).lower()
            or search_lower in str(log.get("error_message", "")).lower()
            or search_lower in str(log.get("message", "")).lower()
        ]

    # Sort by timestamp descending (newest first)
    all_logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    # Pagination
    total_count = len(all_logs)
    total_pages = max(1, (total_count + per_page - 1) // per_page)
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_logs = all_logs[start_idx:end_idx]

    # Get statistics
    stats = audit_logger.get_statistics()
    stats_summary = {
        "total": stats.get("total_entries", 0),
        "tool_calls": stats.get("by_type", {}).get("tool_call", 0),
        "auth_events": stats.get("by_type", {}).get("authentication", 0),
        "errors": stats.get("by_level", {}).get("ERROR", 0),
    }

    return {
        "logs": paginated_logs,
        "stats": stats_summary,
        "total_count": total_count,
        "total_pages": total_pages,
        "current_page": page,
        "per_page": per_page,
    }


async def dashboard_audit_logs_list(request: Request) -> Response:
    """Render audit logs list page (admin only)."""
    session, redirect = _require_admin_session(request)
    if redirect:
        return redirect

    # Get language
    accept_language = request.headers.get("accept-language")
    query_lang = request.query_params.get("lang")
    lang = detect_language(accept_language, query_lang)
    t = get_translations(lang)

    # Get query parameters
    event_type = request.query_params.get("event_type", "")
    level = request.query_params.get("level", "")
    date = request.query_params.get("date", "")
    search = request.query_params.get("search", "")
    project_filter = request.query_params.get("project", "")
    page = int(request.query_params.get("page", 1))

    # Get logs data
    logs_data = await get_audit_logs_data(
        event_type=event_type if event_type else None,
        level=level if level else None,
        date=date if date else None,
        search=search if search else None,
        project_id=project_filter if project_filter else None,
        page=page,
    )

    # Get available projects for filter dropdown
    from core.site_manager import get_site_manager

    site_manager = get_site_manager()
    available_projects = site_manager.list_all_sites()

    return templates.TemplateResponse(
        "dashboard/audit-logs/list.html",
        {
            "request": request,
            "lang": lang,
            "t": t,
            "session": session,
            "logs": logs_data["logs"],
            "stats": logs_data["stats"],
            "total_count": logs_data["total_count"],
            "total_pages": logs_data["total_pages"],
            "page_number": logs_data["current_page"],
            "per_page": logs_data["per_page"],
            "available_projects": available_projects,
            "selected_project": project_filter,
            "selected_event_type": event_type,
            "selected_level": level,
            "selected_date": date,
            "search_query": search,
            "current_page": "audit_logs",
        },
    )


async def dashboard_api_audit_logs(request: Request) -> Response:
    """API endpoint for audit logs list."""
    auth = get_dashboard_auth()

    # Check authentication
    session = auth.get_session_from_request(request) or auth.get_user_session_from_request(request)
    if not session:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    try:
        # Get query parameters
        event_type = request.query_params.get("event_type")
        level = request.query_params.get("level")
        date = request.query_params.get("date")
        search = request.query_params.get("search")
        page = int(request.query_params.get("page", 1))

        logs_data = await get_audit_logs_data(
            event_type=event_type,
            level=level,
            date=date,
            search=search,
            page=page,
        )

        return JSONResponse(logs_data)

    except Exception as e:
        logger.error(f"Error getting audit logs: {e}")
        return JSONResponse({"error": "Failed to get logs"}, status_code=500)


# =============================================================================
# K.5: Health Monitoring
# =============================================================================


def get_basic_health_data() -> dict:
    """Get basic health data (fast, no project checks)."""
    try:
        from core.health import get_health_monitor

        health_monitor = get_health_monitor()
        if not health_monitor:
            return {
                "system_status": "unknown",
                "metrics": {
                    "total_requests": 0,
                    "successful_requests": 0,
                    "failed_requests": 0,
                    "average_response_time_ms": 0,
                    "error_rate_percent": 0,
                    "requests_per_minute": 0,
                },
                "uptime": {
                    "start_time": "",
                    "current_time": "",
                    "formatted": "0s",
                    "days": 0,
                    "hours": 0,
                },
            }

        # Get system metrics (fast)
        system_metrics = health_monitor.get_system_metrics()
        uptime_data = health_monitor.get_uptime()

        return {
            "system_status": "checking",  # Will be updated by async call
            "metrics": {
                "total_requests": system_metrics.total_requests,
                "successful_requests": system_metrics.successful_requests,
                "failed_requests": system_metrics.failed_requests,
                "average_response_time_ms": system_metrics.average_response_time_ms,
                "error_rate_percent": system_metrics.error_rate_percent,
                "requests_per_minute": system_metrics.requests_per_minute,
            },
            "uptime": {
                "start_time": uptime_data.get("start_time", ""),
                "current_time": uptime_data.get("current_time", ""),
                "formatted": uptime_data.get("uptime_formatted", "0s"),
                "days": uptime_data.get("uptime_days", 0),
                "hours": uptime_data.get("uptime_hours", 0),
            },
        }
    except Exception as e:
        logger.warning(f"Error getting basic health data: {e}")
        return {
            "system_status": "error",
            "metrics": {
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "average_response_time_ms": 0,
                "error_rate_percent": 0,
                "requests_per_minute": 0,
            },
            "uptime": {
                "start_time": "",
                "current_time": "",
                "formatted": "0s",
                "days": 0,
                "hours": 0,
            },
        }


def get_cached_projects_health() -> dict:
    """
    Get cached health status for all projects without live checks.
    Uses stored metrics to determine status.
    """
    from core.site_manager import get_site_manager

    projects_health = {}
    healthy_count = 0
    unhealthy_count = 0
    warning_count = 0

    try:
        site_manager = get_site_manager()
        sites = site_manager.list_all_sites()

        for site in sites:
            full_id = f"{site.get('plugin_type')}_{site.get('site_id')}"
            cached = get_cached_health_status(full_id)

            # Convert to format expected by template
            projects_health[full_id] = {
                "healthy": cached["status"] == "healthy",
                "response_time_ms": 0,  # Not available from cache
                "error_rate_percent": cached["error_rate"],
                "last_check": cached["last_check"] or "",
                "status": cached["status"],
            }

            if cached["status"] == "healthy":
                healthy_count += 1
            elif cached["status"] == "warning":
                warning_count += 1
            elif cached["status"] == "unhealthy":
                unhealthy_count += 1

    except Exception as e:
        logger.warning(f"Error getting cached projects health: {e}")

    # Determine overall status
    total = len(projects_health)
    if total == 0:
        system_status = "unknown"
    elif unhealthy_count > 0:
        system_status = "unhealthy"
    elif warning_count > 0:
        system_status = "degraded"
    else:
        system_status = "healthy"

    return {
        "system_status": system_status,
        "projects_health": projects_health,
        "projects_summary": {
            "total": total,
            "healthy": healthy_count,
            "unhealthy": unhealthy_count + warning_count,
        },
        "alerts": [],  # No alerts from cached data
    }


async def get_health_data(live_check: bool = True) -> dict:
    """
    Get comprehensive health monitoring data.

    Args:
        live_check: If True, perform live health checks. If False, use cached data.
    """
    default_result = {
        "system_status": "unknown",
        "metrics": {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "average_response_time_ms": 0,
            "error_rate_percent": 0,
            "requests_per_minute": 0,
        },
        "uptime": {
            "start_time": "",
            "current_time": "",
            "formatted": "0s",
            "days": 0,
            "hours": 0,
        },
        "alerts": [],
        "projects_health": {},
        "projects_summary": {"total": 0, "healthy": 0, "unhealthy": 0},
    }

    try:
        from core.health import get_health_monitor

        health_monitor = get_health_monitor()
        if not health_monitor:
            return default_result

        # Get system metrics (always available from cache)
        system_metrics = health_monitor.get_system_metrics()
        uptime_data = health_monitor.get_uptime()

        # Get projects health - either live or cached
        if live_check:
            # Live health check (slow but accurate)
            try:
                projects_health_data = await health_monitor.check_all_projects_health(
                    include_metrics=True
                )
            except Exception as e:
                logger.warning(f"Error checking projects health: {e}")
                projects_health_data = {
                    "status": "unknown",
                    "alerts": [],
                    "summary": {"total_projects": 0, "healthy": 0, "unhealthy": 0},
                    "projects": {},
                }
        else:
            # Use cached data (fast)
            cached = get_cached_projects_health()
            projects_health_data = {
                "status": cached["system_status"],
                "alerts": cached["alerts"],
                "summary": {
                    "total_projects": cached["projects_summary"]["total"],
                    "healthy": cached["projects_summary"]["healthy"],
                    "unhealthy": cached["projects_summary"]["unhealthy"],
                },
                "projects": cached["projects_health"],
            }

        return {
            "system_status": projects_health_data.get("status", "unknown"),
            "metrics": {
                "total_requests": system_metrics.total_requests,
                "successful_requests": system_metrics.successful_requests,
                "failed_requests": system_metrics.failed_requests,
                "average_response_time_ms": system_metrics.average_response_time_ms,
                "error_rate_percent": system_metrics.error_rate_percent,
                "requests_per_minute": system_metrics.requests_per_minute,
            },
            "uptime": {
                "start_time": uptime_data.get("start_time", ""),
                "current_time": uptime_data.get("current_time", ""),
                "formatted": uptime_data.get("uptime_formatted", "0s"),
                "days": uptime_data.get("uptime_days", 0),
                "hours": uptime_data.get("uptime_hours", 0),
            },
            "alerts": projects_health_data.get("alerts", []),
            "projects_health": projects_health_data.get("projects", {}),
            "projects_summary": {
                "total": projects_health_data.get("summary", {}).get("total_projects", 0),
                "healthy": projects_health_data.get("summary", {}).get("healthy", 0),
                "unhealthy": projects_health_data.get("summary", {}).get("unhealthy", 0),
            },
        }
    except Exception as e:
        logger.error(f"Error getting health data: {e}")
        return default_result


async def dashboard_health_page(request: Request) -> Response:
    """
    Render health monitoring page (admin only).

    By default, shows cached health data (fast load).
    If ?refresh=true, performs live health checks (slower but accurate).
    """
    try:
        session, redirect = _require_admin_session(request)
        if redirect:
            return redirect

        # Get language
        accept_language = request.headers.get("accept-language")
        query_lang = request.query_params.get("lang")
        lang = detect_language(accept_language, query_lang)
        t = get_translations(lang)

        # Check if live refresh is requested
        refresh = request.query_params.get("refresh", "").lower() == "true"

        # Get health data - cached by default, live if refresh requested
        health_data = await get_health_data(live_check=refresh)

        return templates.TemplateResponse(
            "dashboard/health/index.html",
            {
                "request": request,
                "lang": lang,
                "t": t,
                "session": session if session else {},
                "system_status": health_data["system_status"],
                "metrics": health_data["metrics"],
                "uptime": health_data["uptime"],
                "alerts": health_data["alerts"],
                "projects_health": health_data["projects_health"],
                "projects_summary": health_data["projects_summary"],
                "async_load": False,  # Data is already loaded
                "is_cached": not refresh,  # Indicate if showing cached data
                "current_page": "health",
            },
        )
    except Exception as e:
        logger.error(f"Error rendering health page: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return HTMLResponse(f"<h1>Error loading health page</h1><pre>{e}</pre>", status_code=500)


async def dashboard_health_projects_partial(request: Request) -> Response:
    """HTMX endpoint for projects health data (admin only, HTML partial)."""
    logger.debug("Health projects partial endpoint called")

    session, redirect = _require_admin_session(request)
    if redirect:
        return HTMLResponse(
            "<tr><td colspan='5' class='text-red-400 text-center py-4'>Unauthorized</td></tr>",
            status_code=401,
        )

    # Get language
    accept_language = request.headers.get("accept-language")
    query_lang = request.query_params.get("lang")
    lang = detect_language(accept_language, query_lang)
    t = get_translations(lang)

    try:
        logger.debug("Fetching health data...")
        health_data = await get_health_data()
        logger.debug(
            f"Health data fetched: status={health_data.get('system_status')}, projects={len(health_data.get('projects_health', {}))}"
        )

        # Render partial HTML for projects health table
        return templates.TemplateResponse(
            "dashboard/health/projects-partial.html",
            {
                "request": request,
                "lang": lang,
                "t": t,
                "system_status": health_data["system_status"],
                "alerts": health_data["alerts"],
                "projects_health": health_data["projects_health"],
                "projects_summary": health_data["projects_summary"],
            },
        )
    except Exception as e:
        logger.error(f"Error getting projects health: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return HTMLResponse(
            f"<tr><td colspan='5' class='text-red-400 text-center py-4'>Error: {e}</td></tr>",
            status_code=500,
        )


async def dashboard_api_health(request: Request) -> Response:
    """API endpoint for health data."""
    auth = get_dashboard_auth()

    # Check authentication
    session = auth.get_session_from_request(request) or auth.get_user_session_from_request(request)
    if not session:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    try:
        health_data = await get_health_data()
        return JSONResponse(health_data)
    except Exception as e:
        logger.error(f"Error getting health data: {e}")
        return JSONResponse({"error": "Failed to get health data"}, status_code=500)


# =============================================================================
# K.5: Settings Page
# =============================================================================


def get_system_config() -> dict:
    """Get system configuration for display."""

    return {
        "server_mode": os.environ.get("MCP_SERVER_MODE", "streamable-http"),
        "port": os.environ.get("PORT", "8000"),
        "log_level": os.environ.get("LOG_LEVEL", "INFO"),
        "oauth_auth_mode": os.environ.get("OAUTH_AUTH_MODE", "trusted_domains"),
        "rate_limit_per_day": os.environ.get("RATE_LIMIT_PER_DAY", "1000"),
        "rate_limit_per_minute": os.environ.get("RATE_LIMIT_PER_MINUTE", "60"),
        "api_auth_enabled": os.environ.get("API_AUTH_ENABLED", "true").lower() == "true",
        "dashboard_secure_cookie": os.environ.get("DASHBOARD_SECURE_COOKIE", "false").lower()
        == "true",
        "oauth_trusted_domains": os.environ.get("OAUTH_TRUSTED_DOMAINS", "localhost"),
        "dashboard_session_expiry": os.environ.get("DASHBOARD_SESSION_EXPIRY_HOURS", "24"),
    }


_PLUGIN_DESCRIPTIONS = {
    "wordpress": "WordPress REST API management (posts, pages, media, users)",
    "woocommerce": "WooCommerce store management (products, orders, customers)",
    "wordpress_advanced": "WordPress Advanced operations (WP-CLI, database, bulk ops)",
    "gitea": "Gitea self-hosted Git management (repos, issues, PRs)",
    "n8n": "n8n workflow automation management",
    "supabase": "Supabase self-hosted backend (database, auth, storage)",
    "openpanel": "OpenPanel analytics and event tracking",
    "appwrite": "Appwrite backend services (databases, users, functions)",
    "directus": "Directus headless CMS management",
}


def get_registered_plugins() -> list:
    """Get list of registered plugins."""
    plugins = []

    try:
        from plugins import registry as plugin_registry

        # Use _plugin_classes dict and get_registered_types() method
        for name in plugin_registry.get_registered_types():
            plugin_cls = plugin_registry._plugin_classes.get(name)
            if plugin_cls:
                plugins.append(
                    {
                        "name": name,
                        "description": _PLUGIN_DESCRIPTIONS.get(name, "Plugin"),
                    }
                )
    except Exception as e:
        logger.warning(f"Error getting plugins: {e}")

    return plugins


def _get_project_version() -> str:
    """Read version from pyproject.toml, falling back to package metadata."""
    try:
        toml_path = os.path.join(os.path.dirname(os.path.dirname(TEMPLATES_DIR)), "pyproject.toml")
        with open(toml_path) as f:
            for line in f:
                if line.strip().startswith("version"):
                    return line.split("=")[1].strip().strip('"').strip("'")
    except Exception:
        pass
    try:
        from importlib.metadata import version

        return version("mcphub-server")
    except Exception:
        return "unknown"


def get_about_info() -> dict:
    """Get about information."""
    import sys

    tools_count = 0
    try:
        from core.tool_registry import get_tool_registry

        tool_registry = get_tool_registry()
        tools_count = len(tool_registry.get_all())
    except Exception:
        pass

    return {
        "version": _get_project_version(),
        "mcp_version": "2024-11-05",
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "tools_count": tools_count,
    }


async def dashboard_settings_page(request: Request) -> Response:
    """Render settings page (admin only)."""
    session, redirect = _require_admin_session(request)
    if redirect:
        return redirect

    # Get language
    accept_language = request.headers.get("accept-language")
    query_lang = request.query_params.get("lang")
    lang = detect_language(accept_language, query_lang)
    t = get_translations(lang)

    # Get data
    config = get_system_config()
    plugins = get_registered_plugins()
    about = get_about_info()

    # Format session display info (for Session Information section)
    if isinstance(session, dict):
        session_display = {
            "user_type": session.get("type", "oauth_user"),
            "created_at": "",
            "expires_at": "",
        }
    else:
        session_display = {
            "user_type": session.user_type if session else "unknown",
            "created_at": session.created_at.isoformat() if session and session.created_at else "",
            "expires_at": session.expires_at.isoformat() if session and session.expires_at else "",
        }

    return templates.TemplateResponse(
        "dashboard/settings/index.html",
        {
            "request": request,
            "lang": lang,
            "t": t,
            "session": session,  # Original session for RBAC sidebar
            "session_display": session_display,  # Formatted for display
            "config": config,
            "plugins": plugins,
            "about": about,
            "current_page": "settings",
        },
    )


# =============================================================================
# E.2: OAuth Social Login Routes
# =============================================================================


async def auth_login_page(request: Request) -> Response:
    """Render the OAuth login page with GitHub + Google buttons."""
    auth = get_dashboard_auth()

    # Check if already logged in (admin or user session)
    session = auth.get_session_from_request(request) or auth.get_user_session_from_request(request)
    if session:
        return RedirectResponse(url="/dashboard", status_code=303)

    # Get language
    accept_language = request.headers.get("accept-language")
    query_lang = request.query_params.get("lang")
    lang = detect_language(accept_language, query_lang)
    t = get_translations(lang)

    error = request.query_params.get("error")

    # Get available providers
    providers = []
    try:
        from core.user_auth import get_user_auth

        user_auth = get_user_auth()
        providers = user_auth.available_providers()
    except RuntimeError:
        pass

    return templates.TemplateResponse(
        "dashboard/auth-login.html",
        {
            "request": request,
            "lang": lang,
            "t": t,
            "error": error,
            "providers": providers,
            "version": _get_project_version(),
        },
    )


async def auth_provider_redirect(request: Request) -> Response:
    """Redirect to OAuth provider (GitHub or Google)."""
    provider = request.path_params.get("provider", "")

    if provider in ("login", "logout", "callback"):
        return RedirectResponse(url=f"/auth/{provider}", status_code=303)

    try:
        from core.user_auth import get_user_auth

        user_auth = get_user_auth()
        auth_url, state = user_auth.get_authorization_url(provider)

        response = RedirectResponse(url=auth_url, status_code=302)
        response.set_cookie(
            key="oauth_state",
            value=state,
            max_age=600,
            httponly=True,
            secure=os.environ.get("DASHBOARD_SECURE_COOKIE", "true").lower() == "true",
            samesite="lax",
        )

        # Save return URL if provided (for OAuth consent flow redirect-back)
        next_url = request.query_params.get("next", "")
        if next_url:
            response.set_cookie(
                key="mcp_auth_next",
                value=next_url,
                max_age=600,
                httponly=True,
                secure=os.environ.get("DASHBOARD_SECURE_COOKIE", "true").lower() == "true",
                samesite="lax",
                path="/",
            )

        return response
    except (RuntimeError, ValueError) as e:
        logger.error("OAuth redirect failed for %s: %s", provider, e)
        return RedirectResponse(
            url="/auth/login?error=provider_unavailable",
            status_code=303,
        )


async def auth_callback(request: Request) -> Response:
    """Handle OAuth callback from provider."""
    provider = request.path_params.get("provider", "")
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    error = request.query_params.get("error")

    if error:
        logger.warning("OAuth callback error from %s: %s", provider, error)
        return RedirectResponse(url="/auth/login?error=oauth_denied", status_code=303)

    if not code or not state:
        return RedirectResponse(
            url="/auth/login?error=missing_params",
            status_code=303,
        )

    try:
        from core.user_auth import get_user_auth

        user_auth = get_user_auth()

        # Validate state (CSRF protection)
        if not user_auth.validate_state(state):
            logger.warning("OAuth callback: invalid state for %s", provider)
            return RedirectResponse(
                url="/auth/login?error=invalid_state",
                status_code=303,
            )

        # Exchange code for user info
        user_info = await user_auth.exchange_code(provider, code)

        if not user_info.get("email"):
            return RedirectResponse(
                url="/auth/login?error=no_email",
                status_code=303,
            )

        # Get client IP for rate limiting
        client_ip = get_client_ip(request)

        # Look up or create user in database
        from core.database import get_database

        db = get_database()

        existing_user = await db.get_user_by_provider(
            provider=user_info["provider"],
            provider_id=user_info["provider_id"],
        )

        if existing_user:
            await db.update_user_last_login(existing_user["id"])
            user = existing_user
        else:
            # Check if user exists by email (handle OAuth provider collision)
            user_by_email = await db.get_user_by_email(user_info["email"])
            if user_by_email:
                # Merge login: user is recognized by email regardless of provider
                await db.update_user_last_login(user_by_email["id"])
                user = user_by_email
                logger.info(
                    "User %s logged in with alternate provider %s (original: %s)",
                    user_info["email"],
                    provider,
                    user_by_email["provider"],
                )
            else:
                # New registration -- check rate limit
                if not user_auth.check_registration_rate(client_ip):
                    logger.warning(
                        "Registration rate limit hit for IP %s",
                        client_ip,
                    )
                    return RedirectResponse(
                        url="/auth/login?error=rate_limit",
                        status_code=303,
                    )

                user = await db.create_user(
                    email=user_info["email"],
                    name=user_info.get("name"),
                    provider=user_info["provider"],
                    provider_id=user_info["provider_id"],
                    avatar_url=user_info.get("avatar_url"),
                )
            user_auth.record_registration(client_ip)
            logger.info(
                "New user registered: %s via %s",
                user_info["email"],
                provider,
            )

        # Create session
        token = user_auth.create_user_session(
            user_id=user["id"],
            email=user["email"],
            name=user.get("name"),
            role=user.get("role", "user"),
        )

        # Check for return URL (OAuth consent flow redirect-back)
        next_url = request.cookies.get("mcp_auth_next", "")
        # Validate: must be relative URL or same-origin to prevent open redirect
        if next_url and next_url.startswith("/"):
            redirect_to = next_url
        else:
            redirect_to = "/dashboard"

        response = RedirectResponse(url=redirect_to, status_code=303)
        dashboard_auth = get_dashboard_auth()
        dashboard_auth.set_session_cookie(response, token)
        response.delete_cookie(key="oauth_state")
        response.delete_cookie(key="mcp_auth_next", path="/")

        logger.info(
            "OAuth login successful: %s via %s (redirect=%s)",
            user["email"],
            provider,
            redirect_to,
        )
        return response

    except ValueError as e:
        logger.error("OAuth callback failed for %s: %s", provider, e)
        return RedirectResponse(
            url="/auth/login?error=exchange_failed",
            status_code=303,
        )
    except Exception as e:
        logger.error(
            "OAuth callback unexpected error for %s: %s",
            provider,
            e,
        )
        return RedirectResponse(
            url="/auth/login?error=server_error",
            status_code=303,
        )


async def auth_logout(request: Request) -> Response:
    """Log out the current user (both admin and OAuth sessions)."""
    auth = get_dashboard_auth()
    response = RedirectResponse(url="/auth/login", status_code=303)
    auth.clear_session_cookie(response)
    return response


async def dashboard_profile_page(request: Request) -> Response:
    """Render the user profile page."""
    auth = get_dashboard_auth()

    # Check for OAuth user session
    user_session = auth.get_user_session_from_request(request)

    if not user_session:
        admin_session = auth.get_session_from_request(request)
        if not admin_session:
            return RedirectResponse(url="/auth/login", status_code=303)
        return RedirectResponse(url="/dashboard", status_code=303)

    # Get language
    accept_language = request.headers.get("accept-language")
    query_lang = request.query_params.get("lang")
    lang = detect_language(accept_language, query_lang)
    t = get_translations(lang)

    # Get full user from database
    user_data = None
    try:
        from core.database import get_database

        db = get_database()
        user_data = await db.get_user_by_id(user_session["user_id"])
    except Exception as e:
        logger.warning("Failed to fetch user profile: %s", e)

    return templates.TemplateResponse(
        "dashboard/profile.html",
        {
            "request": request,
            "lang": lang,
            "t": t,
            "session": user_session,
            "user": user_data,
            "current_page": "profile",
        },
    )


# ======================================================================
# Site Management Routes (E.3)
# ======================================================================


def _require_user_session(request: Request):
    """Get OAuth user session or return redirect. Helper for E.3 routes."""
    auth = get_dashboard_auth()
    user_session = auth.get_user_session_from_request(request)
    if not user_session:
        return None, RedirectResponse(url="/auth/login", status_code=303)
    return user_session, None


def _require_admin_session(request: Request):
    """Get admin session or redirect to dashboard. Helper for admin-only routes."""
    auth = get_dashboard_auth()
    session = auth.get_session_from_request(request)
    if session and is_admin_session(session):
        return session, None
    # Not admin — redirect to dashboard home
    return None, RedirectResponse(url="/dashboard", status_code=303)


async def dashboard_sites_list(request: Request) -> Response:
    """Render the My Sites page."""
    auth = get_dashboard_auth()
    # Allow both OAuth users and admin
    admin_session = auth.get_session_from_request(request)
    user_session = auth.get_user_session_from_request(request)
    if not user_session and not admin_session:
        return RedirectResponse(url="/auth/login", status_code=303)
    # For admin, we don't have user sites — redirect to projects
    if admin_session and not user_session:
        return RedirectResponse(url="/dashboard/projects", status_code=303)

    accept_language = request.headers.get("accept-language")
    query_lang = request.query_params.get("lang")
    lang = detect_language(accept_language, query_lang)
    t = get_translations(lang)

    from core.site_api import PLUGIN_DISPLAY_NAMES as SITE_PLUGIN_NAMES
    from core.site_api import get_user_sites

    # Flash messages from query params
    msg = request.query_params.get("msg")
    error = request.query_params.get("error")

    try:
        sites = await get_user_sites(user_session["user_id"])
    except RuntimeError:
        sites = []
        error = error or (
            "Site storage is not configured. Contact the administrator."
            if lang != "fa"
            else "ذخیره‌سازی سایت‌ها پیکربندی نشده. با مدیر تماس بگیرید."
        )

    return templates.TemplateResponse(
        "dashboard/sites/list.html",
        {
            "request": request,
            "lang": lang,
            "t": t,
            "session": user_session,
            "sites": sites,
            "plugin_names": SITE_PLUGIN_NAMES,
            "current_page": "my_sites",
            "msg": msg,
            "error": error,
        },
    )


async def dashboard_sites_add(request: Request) -> Response:
    """Render the Add Site form."""
    user_session, redirect = _require_user_session(request)
    if redirect:
        return redirect

    accept_language = request.headers.get("accept-language")
    query_lang = request.query_params.get("lang")
    lang = detect_language(accept_language, query_lang)
    t = get_translations(lang)

    import json

    from core.site_api import get_user_credential_fields, get_user_plugin_names

    # Non-admin users get a filtered list (no wordpress_advanced)
    plugin_fields = get_user_credential_fields()
    plugin_names = get_user_plugin_names()

    return templates.TemplateResponse(
        "dashboard/sites/add.html",
        {
            "request": request,
            "lang": lang,
            "t": t,
            "session": user_session,
            "plugin_fields": plugin_fields,
            "plugin_fields_json": json.dumps(plugin_fields),
            "plugin_names": plugin_names,
            "current_page": "my_sites",
        },
    )


async def dashboard_connect_page(request: Request) -> Response:
    """Render the Connect page (config snippets + API key management)."""
    user_session, redirect = _require_user_session(request)
    if redirect:
        return redirect

    accept_language = request.headers.get("accept-language")
    query_lang = request.query_params.get("lang")
    lang = detect_language(accept_language, query_lang)
    t = get_translations(lang)

    from core.config_snippets import get_supported_clients
    from core.site_api import get_user_sites
    from core.user_keys import get_user_key_manager

    sites = await get_user_sites(user_session["user_id"])

    keys = []
    try:
        key_mgr = get_user_key_manager()
        keys = await key_mgr.list_keys(user_session["user_id"])
    except RuntimeError:
        pass

    # Flash messages
    new_key = request.query_params.get("new_key")

    return templates.TemplateResponse(
        "dashboard/connect.html",
        {
            "request": request,
            "lang": lang,
            "t": t,
            "session": user_session,
            "sites": sites,
            "api_keys": keys,
            "clients": get_supported_clients(),
            "current_page": "connect",
            "new_key": new_key,
        },
    )


# ======================================================================
# Site Management API Routes (E.3)
# ======================================================================


async def api_create_site(request: Request) -> Response:
    """POST /api/sites — Create a new site."""
    user_session, redirect = _require_user_session(request)
    if redirect:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    # Verify user exists in DB (guards against stale JWT from old container)
    try:
        from core.database import get_database

        db = get_database()
        user = await db.get_user_by_id(user_session["user_id"])
        if user is None:
            response = JSONResponse(
                {"error": "Session expired. Please log in again."}, status_code=401
            )
            response.delete_cookie("mcp_user_session")
            return response
    except RuntimeError:
        pass  # Database not initialized — will fail later with clear error

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    from core.site_api import create_user_site

    try:
        site = await create_user_site(
            user_id=user_session["user_id"],
            plugin_type=body.get("plugin_type", ""),
            alias=body.get("alias", ""),
            url=body.get("url", "").strip().rstrip("/"),
            credentials=body.get("credentials", {}),
        )
        return JSONResponse({"site": site, "message": "Site created"})
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except RuntimeError as e:
        # Encryption or database not configured
        logger.error("Site storage not configured: %s", e)
        return JSONResponse(
            {"error": "Site storage is not configured. Contact the administrator."},
            status_code=503,
        )
    except Exception as e:
        error_msg = str(e)
        if "FOREIGN KEY constraint failed" in error_msg:
            logger.warning("Stale session — user %s not in DB", user_session["user_id"])
            response = JSONResponse(
                {"error": "Session expired. Please log in again."}, status_code=401
            )
            response.delete_cookie("mcp_user_session")
            return response
        logger.error("Failed to create site: %s", e, exc_info=True)
        return JSONResponse({"error": "Internal error"}, status_code=500)


async def api_list_sites(request: Request) -> Response:
    """GET /api/sites — List user's sites."""
    user_session, redirect = _require_user_session(request)
    if redirect:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    from core.site_api import get_user_sites

    sites = await get_user_sites(user_session["user_id"])
    return JSONResponse({"sites": sites})


async def api_delete_site(request: Request) -> Response:
    """DELETE /api/sites/{id} — Delete a site."""
    user_session, redirect = _require_user_session(request)
    if redirect:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    site_id = request.path_params.get("id", "")
    from core.site_api import delete_user_site

    deleted = await delete_user_site(site_id, user_session["user_id"])
    if deleted:
        return JSONResponse({"message": "Site deleted"})
    return JSONResponse({"error": "Site not found"}, status_code=404)


async def api_test_site(request: Request) -> Response:
    """POST /api/sites/{id}/test — Test site connection."""
    user_session, redirect = _require_user_session(request)
    if redirect:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    site_id = request.path_params.get("id", "")
    from core.site_api import test_site_connection

    try:
        ok, msg = await test_site_connection(site_id, user_session["user_id"])
        return JSONResponse({"ok": ok, "message": msg})
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=404)
    except Exception as e:
        logger.error("Test connection failed: %s", e, exc_info=True)
        return JSONResponse({"error": "Internal error"}, status_code=500)


async def api_create_key(request: Request) -> Response:
    """POST /api/keys — Create a new user API key."""
    user_session, redirect = _require_user_session(request)
    if redirect:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    from core.user_keys import get_user_key_manager

    try:
        key_mgr = get_user_key_manager()
        result = await key_mgr.create_key(
            user_id=user_session["user_id"],
            name=body.get("name", "Default"),
            scopes=body.get("scopes", "read write"),
            expires_in_days=body.get("expires_in_days"),
        )
        return JSONResponse({"key": result})
    except RuntimeError as e:
        return JSONResponse({"error": str(e)}, status_code=503)
    except Exception as e:
        logger.error("Failed to create API key: %s", e, exc_info=True)
        return JSONResponse({"error": "Internal error"}, status_code=500)


async def api_list_keys(request: Request) -> Response:
    """GET /api/keys — List user's API keys."""
    user_session, redirect = _require_user_session(request)
    if redirect:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    from core.user_keys import get_user_key_manager

    try:
        key_mgr = get_user_key_manager()
        keys = await key_mgr.list_keys(user_session["user_id"])
        return JSONResponse({"keys": keys})
    except RuntimeError:
        return JSONResponse({"keys": []})


async def api_delete_key(request: Request) -> Response:
    """DELETE /api/keys/{id} — Delete an API key."""
    user_session, redirect = _require_user_session(request)
    if redirect:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    key_id = request.path_params.get("id", "")
    from core.user_keys import get_user_key_manager

    try:
        key_mgr = get_user_key_manager()
        deleted = await key_mgr.delete_key(key_id, user_session["user_id"])
        if deleted:
            return JSONResponse({"message": "Key deleted"})
        return JSONResponse({"error": "Key not found"}, status_code=404)
    except RuntimeError as e:
        return JSONResponse({"error": str(e)}, status_code=503)


async def api_get_config(request: Request) -> Response:
    """GET /api/config/{alias} — Get config snippets for a site."""
    user_session, redirect = _require_user_session(request)
    if redirect:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    alias = request.path_params.get("alias", "")
    client_type = request.query_params.get("client", "claude_desktop")

    import os

    from core.config_snippets import generate_config

    base_url = os.getenv("PUBLIC_URL", "http://localhost:8000")

    try:
        snippet = generate_config(
            base_url=base_url,
            user_id=user_session["user_id"],
            alias=alias,
            api_key="mhu_YOUR_API_KEY_HERE",
            client_type=client_type,
        )
        return JSONResponse({"config": snippet, "client_type": client_type})
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)


def register_dashboard_routes(mcp):
    """
    Register dashboard routes with the MCP server.

    Args:
        mcp: FastMCP instance to register routes with.
    """
    logger.info("Registering dashboard routes...")

    # Auth routes (E.2: OAuth Social Login)
    mcp.custom_route("/auth/login", methods=["GET"])(auth_login_page)
    mcp.custom_route("/auth/callback/{provider}", methods=["GET"])(auth_callback)
    mcp.custom_route("/auth/logout", methods=["GET", "POST"])(auth_logout)
    mcp.custom_route("/auth/{provider}", methods=["GET"])(auth_provider_redirect)

    # Profile page
    mcp.custom_route("/dashboard/profile", methods=["GET"])(dashboard_profile_page)

    # Login routes
    mcp.custom_route("/dashboard/login", methods=["GET"])(dashboard_login_page)
    mcp.custom_route("/dashboard/login", methods=["POST"])(dashboard_login_submit)
    mcp.custom_route("/dashboard/logout", methods=["GET", "POST"])(dashboard_logout)

    # Dashboard pages
    mcp.custom_route("/dashboard", methods=["GET"])(dashboard_home)
    mcp.custom_route("/dashboard/", methods=["GET"])(dashboard_home)

    # Projects routes
    mcp.custom_route("/dashboard/projects", methods=["GET"])(dashboard_projects_list)
    mcp.custom_route("/dashboard/projects/{project_id:path}", methods=["GET"])(
        dashboard_project_detail
    )

    # API Keys routes
    mcp.custom_route("/dashboard/api-keys", methods=["GET"])(dashboard_api_keys_list)

    # OAuth Clients routes
    mcp.custom_route("/dashboard/oauth-clients", methods=["GET"])(dashboard_oauth_clients_list)

    # Audit Logs routes
    mcp.custom_route("/dashboard/audit-logs", methods=["GET"])(dashboard_audit_logs_list)

    # Health Monitoring routes
    mcp.custom_route("/dashboard/health", methods=["GET"])(dashboard_health_page)

    # Settings routes
    mcp.custom_route("/dashboard/settings", methods=["GET"])(dashboard_settings_page)

    # API endpoints
    mcp.custom_route("/api/dashboard/stats", methods=["GET"])(dashboard_api_stats)
    mcp.custom_route("/api/dashboard/projects", methods=["GET"])(dashboard_api_projects)
    # Note: health-check must be registered BEFORE the generic project_id path route
    mcp.custom_route("/api/dashboard/projects/{project_id:path}/health-check", methods=["POST"])(
        dashboard_project_health_check
    )
    mcp.custom_route("/api/dashboard/projects/{project_id:path}", methods=["GET"])(
        dashboard_api_project_detail
    )
    mcp.custom_route("/api/dashboard/api-keys/create", methods=["POST"])(dashboard_api_keys_create)
    mcp.custom_route("/api/dashboard/api-keys/{key_id}/revoke", methods=["POST"])(
        dashboard_api_keys_revoke
    )
    mcp.custom_route("/api/dashboard/api-keys/{key_id}", methods=["DELETE"])(
        dashboard_api_keys_delete
    )
    mcp.custom_route("/api/dashboard/oauth-clients/create", methods=["POST"])(
        dashboard_oauth_clients_create
    )
    mcp.custom_route("/api/dashboard/oauth-clients/{client_id}", methods=["DELETE"])(
        dashboard_oauth_clients_delete
    )
    mcp.custom_route("/api/dashboard/audit-logs", methods=["GET"])(dashboard_api_audit_logs)
    mcp.custom_route("/api/dashboard/health", methods=["GET"])(dashboard_api_health)
    mcp.custom_route("/api/dashboard/health/projects", methods=["GET"])(
        dashboard_health_projects_partial
    )

    # Site Management routes (E.3)
    mcp.custom_route("/dashboard/sites", methods=["GET"])(dashboard_sites_list)
    mcp.custom_route("/dashboard/sites/add", methods=["GET"])(dashboard_sites_add)
    mcp.custom_route("/dashboard/connect", methods=["GET"])(dashboard_connect_page)

    # Site Management API (E.3)
    mcp.custom_route("/api/sites", methods=["GET"])(api_list_sites)
    mcp.custom_route("/api/sites", methods=["POST"])(api_create_site)
    mcp.custom_route("/api/sites/{id}/test", methods=["POST"])(api_test_site)
    mcp.custom_route("/api/sites/{id}", methods=["DELETE"])(api_delete_site)

    # User API Key routes (E.3)
    mcp.custom_route("/api/keys", methods=["GET"])(api_list_keys)
    mcp.custom_route("/api/keys", methods=["POST"])(api_create_key)
    mcp.custom_route("/api/keys/{id}", methods=["DELETE"])(api_delete_key)

    # Config snippet API (E.3)
    mcp.custom_route("/api/config/{alias}", methods=["GET"])(api_get_config)

    logger.info("Dashboard routes registered successfully")
