"""
Dashboard module for MCP Hub Web UI.

Phase K: Web UI Dashboard
"""

from .auth import DashboardAuth, get_dashboard_auth
from .routes import (
    dashboard_api_audit_logs,
    dashboard_api_health,
    dashboard_api_keys_create,
    dashboard_api_keys_delete,
    # K.3: API Keys routes
    dashboard_api_keys_list,
    dashboard_api_keys_revoke,
    dashboard_api_project_detail,
    dashboard_api_projects,
    dashboard_api_stats,
    # K.4: Audit Logs routes
    dashboard_audit_logs_list,
    # K.5: Health Monitoring routes
    dashboard_health_page,
    dashboard_health_projects_partial,
    dashboard_home,
    # K.1: Core routes
    dashboard_login_page,
    dashboard_login_submit,
    dashboard_logout,
    dashboard_oauth_clients_create,
    dashboard_oauth_clients_delete,
    # K.4: OAuth Clients routes
    dashboard_oauth_clients_list,
    dashboard_project_detail,
    dashboard_project_health_check,
    # K.2: Projects routes
    dashboard_projects_list,
    # K.5: Settings routes
    dashboard_settings_page,
    register_dashboard_routes,
)

__all__ = [
    "DashboardAuth",
    "get_dashboard_auth",
    "register_dashboard_routes",
    # K.1
    "dashboard_login_page",
    "dashboard_login_submit",
    "dashboard_logout",
    "dashboard_home",
    "dashboard_api_stats",
    # K.2
    "dashboard_projects_list",
    "dashboard_project_detail",
    "dashboard_api_projects",
    "dashboard_api_project_detail",
    "dashboard_project_health_check",
    # K.3
    "dashboard_api_keys_list",
    "dashboard_api_keys_create",
    "dashboard_api_keys_revoke",
    "dashboard_api_keys_delete",
    # K.4 OAuth
    "dashboard_oauth_clients_list",
    "dashboard_oauth_clients_create",
    "dashboard_oauth_clients_delete",
    # K.4 Audit
    "dashboard_audit_logs_list",
    "dashboard_api_audit_logs",
    # K.5
    "dashboard_health_page",
    "dashboard_api_health",
    "dashboard_health_projects_partial",
    "dashboard_settings_page",
]
