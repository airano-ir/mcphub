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

from .auth import get_dashboard_auth

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
        "login_subtitle": "Enter your Master API Key to access the dashboard",
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
        "login_subtitle": "کلید API مستر خود را برای دسترسی وارد کنید",
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
    },
}


def detect_language(accept_language: str | None, query_lang: str | None = None) -> str:
    """Detect language from Accept-Language header or query parameter."""
    if query_lang and query_lang in DASHBOARD_TRANSLATIONS:
        return query_lang

    if accept_language:
        # Check for Persian/Farsi
        if "fa" in accept_language.lower() or "fa-ir" in accept_language.lower():
            return "fa"

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

        # Read recent entries from audit log
        entries = audit_logger.get_recent_entries(limit=limit)

        for entry in entries:
            activity.append(
                {
                    "timestamp": entry.get("timestamp", ""),
                    "type": entry.get("event_type", "unknown"),
                    "message": entry.get("message", ""),
                    "project": entry.get("metadata", {}).get("project_id", "-"),
                    "level": entry.get("level", "INFO"),
                }
            )

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
    session = auth.get_session_from_request(request)
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


async def dashboard_logout(request: Request) -> Response:
    """Handle dashboard logout."""
    auth = get_dashboard_auth()
    client_ip = get_client_ip(request)

    response = RedirectResponse(url="/dashboard/login", status_code=303)
    auth.clear_session_cookie(response)

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


async def dashboard_home(request: Request) -> Response:
    """Render dashboard home page."""
    auth = get_dashboard_auth()

    # Check authentication
    redirect = auth.require_auth(request)
    if redirect:
        return redirect

    session = auth.get_session_from_request(request)

    # Get language
    accept_language = request.headers.get("accept-language")
    query_lang = request.query_params.get("lang")
    lang = detect_language(accept_language, query_lang)
    t = get_translations(lang)

    # Get dashboard data
    stats = await get_dashboard_stats()
    projects_by_type = await get_projects_by_type()
    recent_activity = await get_recent_activity(limit=5)
    health_summary = await get_health_summary()

    return templates.TemplateResponse(
        "dashboard/index.html",
        {
            "request": request,
            "lang": lang,
            "t": t,
            "session": session,
            "stats": stats,
            "projects_by_type": projects_by_type,
            "recent_activity": recent_activity,
            "health_summary": health_summary,
            "current_page": "dashboard",
        },
    )


async def dashboard_api_stats(request: Request) -> Response:
    """API endpoint for dashboard stats."""
    auth = get_dashboard_auth()

    # Check authentication
    session = auth.get_session_from_request(request)
    if not session:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    stats = await get_dashboard_stats()
    projects_by_type = await get_projects_by_type()
    health_summary = await get_health_summary()

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
            return {"status": "unknown", "last_check": None, "error_rate": 0}

        # Get cached metrics (last 24 hours)
        metrics = health_monitor.get_project_metrics(project_id, hours=24)

        if not metrics or metrics.get("total_requests", 0) == 0:
            return {"status": "unknown", "last_check": None, "error_rate": 0}

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

        return {"status": status, "last_check": last_check, "error_rate": error_rate}
    except Exception as e:
        logger.warning(f"Error getting cached health for {project_id}: {e}")
        return {"status": "unknown", "last_check": None, "error_rate": 0}


async def get_all_projects(
    plugin_type: str | None = None,
    search: str | None = None,
    status_filter: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> dict:
    """Get all projects with optional filtering."""
    projects = []
    available_plugin_types = set()

    try:
        from core.site_manager import get_site_manager

        site_manager = get_site_manager()
        sites = site_manager.list_all_sites()

        for site in sites:
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
        recent_entries = audit_logger.get_recent_entries(limit=20)
        project_activity = [
            e
            for e in recent_entries
            if e.get("metadata", {}).get("project_id") == project_id
            or e.get("metadata", {}).get("site") == site_id
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
    """Render projects list page."""
    auth = get_dashboard_auth()

    # Check authentication
    redirect = auth.require_auth(request)
    if redirect:
        return redirect

    session = auth.get_session_from_request(request)

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

    session = auth.get_session_from_request(request)

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
    session = auth.get_session_from_request(request)
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
    )

    return JSONResponse(projects_data)


async def dashboard_api_project_detail(request: Request) -> Response:
    """API endpoint for project detail."""
    auth = get_dashboard_auth()

    # Check authentication
    session = auth.get_session_from_request(request)
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
    session = auth.get_session_from_request(request)
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
    """Render API keys list page."""
    auth = get_dashboard_auth()

    # Check authentication
    redirect = auth.require_auth(request)
    if redirect:
        return redirect

    session = auth.get_session_from_request(request)

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
    """API endpoint to create a new API key."""
    auth = get_dashboard_auth()

    # Check authentication
    session = auth.get_session_from_request(request)
    if not session:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

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
    """API endpoint to revoke an API key."""
    auth = get_dashboard_auth()

    # Check authentication
    session = auth.get_session_from_request(request)
    if not session:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

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
    """API endpoint to delete an API key."""
    auth = get_dashboard_auth()

    # Check authentication
    session = auth.get_session_from_request(request)
    if not session:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

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
    """Render OAuth clients list page."""
    auth = get_dashboard_auth()

    # Check authentication
    redirect = auth.require_auth(request)
    if redirect:
        return redirect

    session = auth.get_session_from_request(request)

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
    """API endpoint to create OAuth client."""
    auth = get_dashboard_auth()

    # Check authentication
    session = auth.get_session_from_request(request)
    if not session:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

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
    """API endpoint to delete OAuth client."""
    auth = get_dashboard_auth()

    # Check authentication
    session = auth.get_session_from_request(request)
    if not session:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

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
    """Render audit logs list page."""
    auth = get_dashboard_auth()

    # Check authentication
    redirect = auth.require_auth(request)
    if redirect:
        return redirect

    session = auth.get_session_from_request(request)

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
    session = auth.get_session_from_request(request)
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
    Render health monitoring page.

    By default, shows cached health data (fast load).
    If ?refresh=true, performs live health checks (slower but accurate).
    """
    try:
        auth = get_dashboard_auth()

        # Check authentication
        redirect = auth.require_auth(request)
        if redirect:
            return redirect

        session = auth.get_session_from_request(request)

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
    """HTMX endpoint for projects health data (HTML partial)."""
    logger.debug("Health projects partial endpoint called")

    auth = get_dashboard_auth()

    # Check authentication
    session = auth.get_session_from_request(request)
    if not session:
        logger.warning("Health projects partial: Unauthorized - no session")
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
    session = auth.get_session_from_request(request)
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
        "server_mode": os.environ.get("MCP_SERVER_MODE", "sse"),
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
                        "description": getattr(plugin_cls, "description", "No description"),
                    }
                )
    except Exception as e:
        logger.warning(f"Error getting plugins: {e}")

    return plugins


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
        "version": "1.0.0",
        "mcp_version": "2024-11-05",
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "tools_count": tools_count,
    }


async def dashboard_settings_page(request: Request) -> Response:
    """Render settings page."""
    auth = get_dashboard_auth()

    # Check authentication
    redirect = auth.require_auth(request)
    if redirect:
        return redirect

    session = auth.get_session_from_request(request)

    # Get language
    accept_language = request.headers.get("accept-language")
    query_lang = request.query_params.get("lang")
    lang = detect_language(accept_language, query_lang)
    t = get_translations(lang)

    # Get data
    config = get_system_config()
    plugins = get_registered_plugins()
    about = get_about_info()

    # Format session info
    session_info = {
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
            "session": session_info,
            "config": config,
            "plugins": plugins,
            "about": about,
            "current_page": "settings",
        },
    )


def register_dashboard_routes(mcp):
    """
    Register dashboard routes with the MCP server.

    Args:
        mcp: FastMCP instance to register routes with.
    """
    logger.info("Registering dashboard routes...")

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

    logger.info("Dashboard routes registered successfully")
