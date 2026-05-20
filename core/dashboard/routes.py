"""
Dashboard Routes - Web UI routes for MCP Hub.

Phase K.1: Core Infrastructure
"""

import logging
import os
from datetime import UTC, datetime
from typing import Any

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
    "wordpress_specialist": "WordPress Specialist",
    "woocommerce": "WooCommerce",
    "directus": "Directus",
    "supabase": "Supabase",
    "gitea": "Gitea",
    "openpanel": "OpenPanel",
    "appwrite": "Appwrite",
    "coolify": "Coolify",
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
        "services": "Services",
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
        "site_updated": "Site updated successfully",
        "site_deleted": "Site deleted",
        "edit_site": "Edit Site",
        "updating_site": "Updating site...",
        "keep_existing": "Leave blank to keep current value",
        "leave_blank_to_clear": "Leave blank to clear (optional field)",
        "connection_ok": "Connection OK",
        "connection_failed": "Connection failed",
        "last_tested": "Last tested",
        "never_tested": "Not tested yet",
        "just_now": "just now",
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
        "sites.limit_reached_body": (
            "You have reached the maximum of {limit} services for this account. "
            "Delete an existing service or ask an administrator to raise the limit."
        ),
        "sites.limit_reached_body_unknown": (
            "You have reached the maximum number of services for this account. "
            "Delete an existing service or ask an administrator to raise the limit."
        ),
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
        "keys": "API Keys",
        # Workspace / breadcrumbs
        "workspace": "Workspace",
        # Sidebar nav groups (G round)
        "nav.manage": "Manage",
        "nav.access": "Access",
        "nav.observability": "Observability",
        "nav.account": "Account",
        # Sidebar nav items
        "nav.overview": "Overview",
        "nav.sites": "Sites",
        "nav.connect": "Connect",
        "nav.api_keys": "API Keys",
        "nav.oauth_clients": "OAuth Clients",
        "nav.health": "Health",
        "nav.audit": "Audit Logs",
        "nav.settings": "Settings",
        "nav.jump_to": "Jump to…",
        "nav.logout": "Log out",
        # Overview greeting (split from `welcome` so eyebrow + h1 don't duplicate)
        "welcome_eyebrow": "Welcome back",
        "welcome_greeting": "Hello",
        # Overview stat cards
        "card.active_sites_label": "Active sites",
        "card.active_sites_caption": "Sites you manage",
        "card.api_keys_label": "API keys",
        "card.api_keys_caption": "Personal & client keys",
        "card.tools_label": "Tools available",
        "card.tools_caption": "Across enabled plugins",
        "card.healthy_sites_label": "Healthy sites",
        "card.healthy_sites_caption": "Sites passing connection tests",
        "card.uptime_label": "Uptime (days)",
        "card.uptime_caption": "Hub availability",
        # Overview sites table
        "your_sites": "Your sites",
        "health_connection_status": "Health and connection status",
        "manage": "Manage",
        "add_site_short": "Add site",
        "connect_client": "Connect client",
        "register_first_site_body": (
            "Register a Coolify project, WordPress site, "
            "or other supported plugin to get started."
        ),
        "table.site": "Site",
        "table.type": "Type",
        "table.status": "Status",
        "table.last_tested": "Last tested",
        # Status badges
        "status_healthy": "healthy",
        "status_warning": "warning",
        "status_error": "error",
        "status_unknown": "unknown",
        "status_untested": "untested",
        # Topbar
        "topbar.toggle_sidebar": "Toggle sidebar",
        "topbar.cycle_theme": "Switch theme",
        "topbar.change_language": "Change language",
        "topbar.notifications": "Notifications",
        # Theme labels (mode picker)
        "theme.dark": "Dark",
        "theme.light": "Light",
        "theme.system": "System",
        # Login (SPA)
        "login.welcome": "Welcome back",
        "login.subtitle": "Sign in to your MCP Hub",
        "login.continue_github": "Continue with GitHub",
        "login.continue_google": "Continue with Google",
        "login.or_admin_key": "or admin key",
        "login.master_key_label": "Master API key",
        "login.sign_in": "Sign in",
        "login.signing_in": "Signing in…",
        "login.failed": "Sign in failed",
        "login.invalid_key": "Invalid API key",
        "login.footer": "© mcphub.dev · Self-hosted · Open source",
        "login.testimonial": (
            "“My six AI tools now share one key, one audit log, one revoke "
            "button. I shouldn't be this happy about a dashboard.”"
        ),
        "login.testimonial_author": "Lena K.",
        "login.testimonial_role": "Staff eng, self-hosted everything",
        # Onboarding
        "onboarding.have_account": "Already have an account?",
        "onboarding.step_signin": "Sign in",
        "onboarding.step_add_site": "Add a site",
        "onboarding.step_get_key": "Get your key",
        "onboarding.step_n_of": "Step {n} of {total}",
        "onboarding.signin_title": "Sign in with your GitHub or Google account",
        "onboarding.signin_body": (
            "We use OAuth — no passwords, no email verification dance. " "Takes a few seconds."
        ),
        "onboarding.skip_signed_in": "Skip — already signed in",
        "onboarding.add_site_title": "Add your first site",
        "onboarding.add_site_body": (
            "Pick a Coolify project, WordPress site, Gitea instance, or any "
            "other supported plugin. You can add more later."
        ),
        "onboarding.add_site_cta": "Add a site",
        "onboarding.skip": "Skip",
        "onboarding.done_title": "You're set",
        "onboarding.done_body": (
            "Head over to API keys to create one, or jump to Connect to wire " "up an AI client."
        ),
        "onboarding.connect_client": "Connect a client",
        "onboarding.go_dashboard": "Go to dashboard",
        # Common verbs & section labels
        "view.grid": "Grid",
        "view.list": "List",
        "table.tier": "Tier",
        "table.description": "Description",
        "table.prefix": "Prefix",
        "table.created": "Created",
        "table.last_used": "Last used",
        "table.expiry": "Expires",
        "table.project": "Project",
        "table.latency": "Latency",
        "table.uptime": "Uptime",
        "table.tools": "Tools",
        "table.last_check": "Last check",
        "table.scope": "Scope",
        "action.revoke": "Revoke",
        "action.copy": "Copy",
        "action.create": "Create",
        "action.new_key": "New key",
        "action.new_client": "New client",
        "action.add_site_cta": "Add a site",
        "action.save": "Save",
        "action.reset": "Reset",
        # Scope tier names (shared by ApiKeys, OAuthClients, Connect)
        "tier.read": "Read",
        "tier.read_sensitive": "Read sensitive",
        "tier.deploy": "Deploy",
        "tier.editor": "Editor",
        "tier.settings": "Settings",
        "tier.settings_scope": "Settings",
        "tier.install": "Installer",
        "tier.write": "Write",
        "tier.admin": "Admin",
        "tier.custom": "Custom",
        # Sites page
        "sites.intro": (
            "Every site your AI agents can see. Capabilities are scoped per " "site and per key."
        ),
        "sites.add_tile_title": "Add a site",
        "sites.add_tile_desc": ("Register a Coolify project, WordPress site, or other plugin"),
        "sites.empty_body": (
            "Register a Coolify project, WordPress site, or other supported "
            "plugin so your AI clients can use it."
        ),
        "filter.healthy": "Healthy",
        "filter.untested": "Untested",
        # Health page
        "health.intro": "Hub and per-site status. Auto-refreshing every 30 seconds.",
        "health.all_operational": "All systems operational",
        "health.degraded": "Degraded",
        "health.down": "Down",
        "health.projects_label": "Projects",
        "health.alerts_label": "Alerts",
        "health.total_requests": "Total requests",
        "health.per_minute": "Per minute",
        "health.error_rate": "Error rate",
        "health.avg_response": "Avg response",
        "health.recent_alerts": "Recent alerts",
        "health.metrics_title": "Request metrics",
        "health.metrics_subtitle": "Across the live process",
        "health.no_alerts": "No active alerts.",
        "health.no_projects": "No projects to monitor yet.",
        "health.registered": "registered",
        "health.up": "Up",
        "health.last_check": "Last check",
        "status.live": "live",
        # OAuth clients page
        "oauth.title": "OAuth 2.1 clients",
        "oauth.intro": (
            "Register third-party apps that authorize users against your "
            "hub. Each client has its own credentials and scopes."
        ),
        "oauth.redirect_uris": "Redirect URIs",
        "oauth.redirect_uris_one_per_line": "Redirect URIs (one per line)",
        # Settings tabs
        "settings.tab_profile": "Profile",
        "settings.tab_appearance": "Appearance",
        "settings.tab_limits": "Limits",
        "settings.tab_plugins": "Public plugin visibility",
        "settings.tab_danger": "Danger zone",
        "settings.appearance_subtitle": (
            "Theme, language, brand hue, density. Changes apply immediately " "and persist locally."
        ),
        "settings.brand_color": "Brand color",
        "settings.density": "Density",
        # Settings page (Round 2 i18n)
        "settings.intro": "Your profile, hub preferences, and integrations.",
        "settings.intro_admin_suffix": "Admin-only sections are flagged in the sidebar.",
        "settings.profile_title": "Profile",
        "settings.profile_subtitle": "Used across the hub and for audit attribution",
        "settings.profile_footnote": (
            "Profile details come from your OAuth provider and aren't editable here. "
            "Sign out and reconnect to update them."
        ),
        "settings.field_full_name": "Full name",
        "settings.field_email": "Email",
        "settings.field_session_type": "Session type",
        "settings.field_role": "Role",
        "settings.limits_title": "User limits",
        "settings.limits_subtitle": (
            "Maximum sites and rate limits per registered user. "
            "Persists in the SQLite settings table."
        ),
        "settings.no_managed_limits": "No managed limits found.",
        "settings.plugins_title": "Public plugin visibility",
        "settings.plugins_subtitle": (
            "Toggle which plugin types non-admin users can see. Admins always see everything."
        ),
        "settings.plugins_unavailable": "ENABLED_PLUGINS setting not available.",
        "settings.source_label": "Source",
        "settings.default_label": "default",
        "settings.reset_default": "Reset to default",
        "settings.plugin.wordpress": "Posts, pages, media, comments.",
        "settings.plugin.woocommerce": "Products, orders, customers, reports.",
        "settings.plugin.wordpress_specialist": "Companion-backed: blocks, theme files, plugins, DB.",
        "settings.plugin.supabase": "DB, auth, storage, functions.",
        "settings.plugin.openpanel": "Product analytics and event exports.",
        "settings.plugin.gitea": "Repos, issues, PRs, releases.",
        "settings.plugin.n8n": "Workflows and executions.",
        "settings.plugin.coolify": "Apps, deployments, servers, services.",
        "settings.plugin.appwrite": "Hidden by default. Enable only for custom deployments.",
        "settings.plugin.directus": "Hidden by default. Enable only for custom deployments.",
        "settings.danger_title": "Danger zone",
        "settings.danger_subtitle": (
            "Actions in this section affect every user of the hub. Confirm twice before acting."
        ),
        "settings.reset_all_title": "Reset managed settings",
        "settings.reset_all_body": (
            "Delete database overrides for user limits and public plugin visibility. "
            "Environment values still win over defaults."
        ),
        "settings.reset_all_action": "Reset all managed settings",
        "settings.reset_all_confirm": (
            "Reset all managed settings to environment/default values? This affects every user."
        ),
        "settings.reset_all_done": "Managed settings reset",
        "settings.reset_all_failed": "Reset failed: {error}",
        "badge.admin_lc": "admin",
        "toggle.on": "on",
        "toggle.off": "off",
        "status.saving": "saving…",
        # NotFound page
        "notfound.title": "Not found",
        "notfound.body": "The page you were looking for doesn't exist or has moved.",
        "notfound.cta": "Back to dashboard",
        # Connect clients
        "connect.intro": "Wire up an AI client to your hub.",
        "connect.custom_name": "Custom client",
        "connect.custom_desc": "Any MCP client",
        "connect.tool_access": "Tool Access",
        "connect.tool_access_subtitle": "Pick the tier of MCP tools this site exposes.",
        "connect.tool_access_pick_site": "Select a site above to manage tool access.",
        "connect.service_select_label": "Service",
        "connect.confirm_scope_change": 'Change tool access for "{site}" from "{from}" to "{to}"?',
        "connect.client.claude-ai.desc": "Browser · URL only",
        "connect.client.claude-desktop.desc": "Desktop app · JSON config",
        "connect.client.github-codex.desc": "config.toml · Remote HTTP",
        "connect.desktop.open_step": "Open Claude Desktop",
        "connect.desktop.open_body": (
            "Use this shortcut to switch into Claude Desktop, then return here if your "
            "app still needs the local MCP server config."
        ),
        "connect.desktop.open_button": "Open Claude Desktop",
        "connect.desktop.open_fallback": (
            "If your browser does not open the desktop app, continue with the config steps below."
        ),
        "connect.desktop.step1": "Create or select an MCP Hub API key",
        "connect.desktop.step1_body": (
            "Claude Desktop uses a local config file. Store the mhu_ key in an "
            "environment variable instead of pasting it directly into JSON."
        ),
        "connect.desktop.step2": "Add this server to claude_desktop_config.json",
        "connect.desktop.config_paths": (
            "macOS: ~/Library/Application Support/Claude/claude_desktop_config.json · "
            "Windows: %APPDATA%\\Claude\\claude_desktop_config.json"
        ),
        "connect.desktop.step3": "Restart Claude Desktop and verify tools",
        "connect.desktop.step3_body": (
            "Quit Claude Desktop completely, reopen it, then ask Claude to list the "
            "available MCP Hub tools for the selected service."
        ),
        "connect.desktop.oauth_note": (
            "Claude.ai Connectors are browser-based and only need the URL. Claude Desktop "
            "needs this local JSON config plus a bearer token."
        ),
        "connect.chatgpt.step1": "Use this ChatGPT connector URL",
        "connect.chatgpt.step1_body": (
            "Copy this service URL. ChatGPT only needs the MCP endpoint URL; MCP Hub "
            "handles authentication when ChatGPT connects."
        ),
        "connect.chatgpt.connector_tip": (
            "Tip: You only need the URL above. When connecting, authenticate with an "
            "API Key or GitHub/Google."
        ),
        "connect.chatgpt.step2": "Enable Developer mode in ChatGPT",
        "connect.chatgpt.step2_body": (
            "In chatgpt.com settings, enable Developer mode first. Then open Apps and "
            "choose Create app."
        ),
        "connect.chatgpt.step3": "Create the ChatGPT app",
        "connect.chatgpt.step3_body": (
            "Set Authorization to OAuth mode, which is the default, then paste the URL "
            "above as the MCP server URL and finish the app setup."
        ),
        "connect.no_services_title": "Add a service before connecting clients",
        "connect.no_services_body": (
            "MCP clients need at least one WordPress, WooCommerce, Coolify, or other service "
            "to route tools to. Add your first service from Sites, then return here for the "
            "client URL and setup steps."
        ),
        "connect.json.create_key_title": "Create an API key first",
        "connect.json.create_key_body": (
            "Generate an API key from API Keys, copy it when it is shown once, then replace "
            "mhu_••••••• in this config. You can delete and recreate keys from API Keys."
        ),
        "table.service": "Service",
        "never": "Never",
        "all_sites": "All sites",
        "status.expired": "expired",
        "api_keys.select_service": "Select a service",
        "api_keys.service_hint": "The key is limited to the selected service. Tool tiers are managed on that service's Tool Access page.",
        "api_keys.no_services_title": "Add a service before creating API keys",
        "api_keys.no_services_body": (
            "API keys authenticate clients to your services. Add your first service from Sites, "
            "then create a key for that service or all services."
        ),
        "connect.codex.env_var_title": "Codex reads the token from an environment variable",
        "connect.codex.env_var_body": "Set bearer_token_env_var to the variable name, not the mhu_ token value. Restart Codex after adding new environment variables.",
        "connect.codex.step1": "Export the token for this service",
        "connect.codex.step2": "Add this to ~/.codex/config.toml",
        "connect.codex.step3": "Claude-style JSON is different",
        "connect.codex.claude_difference": "Use the TOML block for Codex. The JSON block is shown only to clarify how Claude-style headers differ.",
        "connect.codex.troubleshooting_title": "Troubleshooting online code environments",
        "connect.codex.troubleshooting_body": "Run codex mcp list, verify bubblewrap/bwrap is available, and restart the Codex session after changing env vars. Missing sandbox dependencies can look like MCP auth failures.",
        "landing.continue_dashboard": "Continue to dashboard",
        "landing.hero_badge": "MCP 1.0 · Claude · ChatGPT · Cursor · Gemini",
        "landing.hero_title_line1": "One hub for every",
        "landing.hero_title_em": "AI connection",
        "landing.hero_title_line2": "to your sites.",
        "landing.hero_body": (
            "MCP Hub is the control plane between your self-hosted services and the AI tools "
            "that work on them. Issue keys, connect Claude.ai, Claude Desktop, ChatGPT, Cursor, "
            "or Codex, and review every call from one clean surface."
        ),
        "landing.nav.features": "Features",
        "landing.nav.integrations": "Integrations",
        "landing.nav.docs": "Docs",
        "landing.nav.blog": "Blog",
        "landing.start_60": "Start in 60 seconds",
        "landing.get_started": "Get started",
        "landing.create_account": "Create account",
        "landing.integrations.eyebrow": "Integrations",
        "landing.integrations.title": "Service-specific tools, one MCP surface.",
        "landing.integrations.tile": "Scoped tools, keys, health, and audit logs.",
        "landing.features_eyebrow": "Features",
        "landing.features_title": "Everything your AI agents need, nothing they don't.",
        "landing.feature.sites.title": "Services as first-class objects",
        "landing.feature.sites.desc": (
            "Register WordPress, WooCommerce, WordPress Specialist, Supabase, OpenPanel, Gitea, "
            "n8n, and Coolify. Each service becomes a discoverable MCP resource with its own "
            "tools and access level."
        ),
        "landing.feature.sites.tag": "Core",
        "landing.feature.keys.title": "Scoped API keys",
        "landing.feature.keys.desc": (
            "Create keys for one service or all sites. Tool tiers stay service-specific and can "
            "be tightened later."
        ),
        "landing.feature.keys.tag": "Security",
        "landing.feature.oauth.title": "OAuth 2.1 + PKCE",
        "landing.feature.oauth.desc": (
            "Connect browser-based clients like Claude.ai Connectors and ChatGPT, while desktop "
            "clients can use direct URLs or bearer tokens."
        ),
        "landing.feature.oauth.tag": "Auth",
        "landing.feature.health.title": "Service health",
        "landing.feature.health.desc": (
            "Track credential checks, latency, and service status so agents know what is "
            "available before they act."
        ),
        "landing.feature.health.tag": "Observability",
        "landing.feature.audit.title": "Full audit trail",
        "landing.feature.audit.desc": (
            "Every tool call, auth event, and settings change is searchable and tied back to "
            "the user or key."
        ),
        "landing.feature.audit.tag": "Compliance",
        "landing.feature.protocol.title": "MCP-native tools",
        "landing.feature.protocol.desc": (
            "Expose plugin tools through MCP without forcing users to learn every service API by hand."
        ),
        "landing.feature.protocol.tag": "Protocol",
        "landing.cta_title": "Spin up your hub, in a minute.",
        "landing.cta_body": "Deploy on any Coolify instance. Free for personal use. Self-hosted forever.",
        "landing.footer_tagline": "The self-hosted MCP control plane for WordPress, Coolify, Gitea, and more.",
        "support_mcphub": "Support MCP Hub",
        "connect.claude_ai.step1": "Use this Claude.ai connector URL",
        "connect.claude.connector_tip": (
            "Tip: You only need the URL above. When connecting, you can authenticate with an API Key "
            "or GitHub/Google."
        ),
        "tools.preset_subtitle": (
            "Choose a service preset or Custom, then fine-tune individual tools below."
        ),
        "sites.empty_search_title": "No sites match this search",
        "sites.empty_search_body": "Try a different alias or clear the search field.",
        "sites.empty_healthy_title": "No healthy sites",
        "sites.empty_healthy_body": "Run a connection test or clear the filter to see every site.",
        "sites.empty_untested_title": "No untested sites",
        "sites.empty_untested_body": "Every site has been tested. Clear the filter to see all sites.",
        "sites.selected_service": "selected service",
        "sites.show_advanced_for_service": "Show advanced {service} fields",
        "sites.hide_advanced_for_service": "Hide advanced {service} fields",
        # Site Tools page (G.5c)
        "tools.eyebrow": "Tool access",
        "tools.back_to_sites": "Back to sites",
        "tools.intro": (
            "Toggle individual MCP tools this site exposes. Scope-tier presets in Connect "
            "are easier for the common case — use this page to fine-tune."
        ),
        "tools.search_placeholder": "Filter tools…",
        "tools.scope_filter_all": "All scopes",
        "tools.empty": "This plugin doesn't expose any tools yet.",
        "tools.group_subtitle": "{n} tool(s) in this tier",
        "tools.unavailable": "Unavailable",
        "tools.needs_provider_key": "Needs an AI provider key — configure one above.",
        "tools.configure_provider_key": "Configure key",
        "tools.readiness_title": "Service readiness",
        "tools.readiness_subtitle": (
            "Credential and health checks determine which tools are exposed to MCP clients."
        ),
        "tools.capability_status": "Capability check",
        "tools.capability_ok": "credential fits selected tier",
        "tools.capability_warning": "credential below selected tier",
        "tools.capability_unavailable": "probe unavailable",
        "tools.capability_unknown_tier": "tier not probed",
        "tools.capability_missing": "Missing",
        "tools.capability_probe_reason": "Reason",
        "tools.capability_ai_providers": "Configured AI providers",
        "tools.credential_requirement_title": "Credential requirement for {scope}",
        "tools.credential_guide.wordpress.read": (
            "The Application Password saved in service credentials should belong to a WordPress "
            "user with at least Editor role. Basic read tools do not require CRUD capabilities."
        ),
        "tools.credential_guide.wordpress.admin": (
            "The Application Password saved in service credentials must belong to a WordPress "
            "Administrator for full CRUD. SEO and companion-backed tools may also require their "
            "corresponding plugins to be active."
        ),
        "tools.credential_guide.wordpress_specialist.read": (
            "The Application Password must belong to a WordPress user with manage_options "
            "(Administrator). Airano MCP Bridge v2.11.0+ must be installed and active for "
            "companion-backed tools."
        ),
        "tools.credential_guide.wordpress_specialist.editor": (
            "Same prerequisites as Read, plus Airano MCP Bridge v2.13.0+ for page editing "
            "and v2.14.0+ for theme file CRUD. Tool calls still check edit_posts/edit_themes."
        ),
        "tools.credential_guide.wordpress_specialist.settings": (
            "Same prerequisites as Editor. Settings, identity, permalink, and cron tools require "
            "an Administrator Application Password with manage_options."
        ),
        "tools.credential_guide.wordpress_specialist.install": (
            "Same prerequisites as Settings, plus Airano MCP Bridge v2.14.0+ for theme "
            "install/activate/delete and v2.15.0+ for plugin install/activate/update."
        ),
        "tools.credential_guide.wordpress_specialist.admin": (
            "Same prerequisites as Installer, plus destructive routes such as delete and URL/zip "
            "installs. PHP file edits require DISALLOW_FILE_EDIT to be unset or false."
        ),
        "tools.credential_guide.woocommerce.read": (
            "The WooCommerce REST API Consumer Key and Secret saved in service credentials must "
            "have Read permission. The creating WordPress user should be at least Shop Manager "
            "to see orders and customers."
        ),
        "tools.credential_guide.woocommerce.admin": (
            "The WooCommerce REST API key must have Read/Write permission and belong to an "
            "Administrator or Shop Manager. Media and AI image upload tools additionally need "
            "WordPress username and Application Password credentials."
        ),
        "tools.tier_warning_title": "Warning",
        "tools.tier_warning.install": (
            "Installer grants the AI agent permission to install and activate plugins or themes "
            "from curated repositories. Test on staging first and review installed extensions regularly."
        ),
        "tools.tier_warning.admin": (
            "Admin grants the full destructive surface: arbitrary installs, deletes, user CRUD, "
            "and other operations that may not have undo. Use only where mistakes are recoverable "
            "from backups."
        ),
        "tools.reason.provider_key": "needs AI provider key",
        "tools.reason.provider_key_detail": "Configure a provider key in AI Image Generation.",
        "tools.reason.companion_route": "needs companion plugin",
        "tools.reason.companion_route_detail": (
            "Install or update Airano MCP Bridge and run a connection test."
        ),
        "tools.reason.feature": "needs SEO plugin",
        "tools.reason.feature_detail": "Install Rank Math or Yoast support before enabling this tool.",
        "tools.reason.wp_credentials": "needs WP App Password",
        "tools.reason.wp_credentials_detail": (
            "Add WordPress username and Application Password in service credentials for media uploads."
        ),
        "tools.reason.probe_unknown": "needs health probe",
        "tools.reason.probe_unknown_detail": (
            "Run a connection test so MCP Hub can verify service capabilities."
        ),
        "tools.toast_failed": "Failed to update tool: {error}",
        "tools.sensitivity.destructive": "destructive",
        "tools.sensitivity.sensitive": "sensitive",
        "providers.title": "AI Image Generation",
        "providers.subtitle": (
            "Store provider API keys for this service. Image generation tools stay "
            "unavailable until a provider key is set and the service connection is healthy."
        ),
        "providers.status_set": "Set",
        "providers.status_unset": "Unset",
        "providers.new_key_placeholder": "New API key",
        "providers.remove": "Remove",
        "providers.encrypted_note": "Keys are encrypted at rest and scoped to this service only.",
        "providers.toast_saved": "Provider key saved",
        "providers.toast_save_failed": "Save failed: {error}",
        "providers.toast_removed": "Provider key removed",
        "providers.toast_remove_failed": "Remove failed: {error}",
        "providers.confirm_remove": "Remove this provider key?",
        "providers.hint.openai": "Save a new key to replace the stored value.",
        "providers.hint.stability": "Save a new key to replace the stored value.",
        "providers.hint.replicate": "Save a new key to replace the stored value.",
        "providers.hint.openrouter": (
            "Supports image-capable OpenRouter models. Save the key here, "
            "then choose a default model for this service."
        ),
        "providers.model.loading": "Loading image models…",
        "providers.model.failed": (
            "Could not load OpenRouter image models. The tool remains disabled if the "
            "provider connection is not healthy."
        ),
        "providers.model.empty": "No image-capable OpenRouter models were found for this key.",
        "providers.model.default_label": "Default image model",
        "providers.model.select": "Select a model",
        "providers.model.set_default": "Set default",
        "providers.model.clear": "Clear",
        "providers.model.current": "Current default: {model}",
        "providers.model.toast_saved": "Default image model saved",
        "providers.model.toast_cleared": "Default image model cleared",
        "providers.model.toast_failed": "Model update failed: {error}",
        "sites.ai_image.title": "AI Image Generation",
        "sites.ai_image.create_body": (
            "After creating this service, open Tool access to add an OpenAI, Stability AI, "
            "Replicate, or OpenRouter key. The image generation tool stays unavailable until "
            "a provider key is saved and the service connection is healthy."
        ),
        "sites.ai_image.edit_body": (
            "Image generation is configured per service in Tool access. Add an OpenAI, "
            "Stability AI, Replicate, or OpenRouter key there; OpenRouter can also use a "
            "default image model."
        ),
        "sites.ai_image.open_tools": "Open AI Image Generation settings",
        # Site Add/Edit dialog (G.12)
        "sites.guidance.wordpress_title": "WordPress requirements",
        "sites.guidance.wordpress_specialist_title": "WordPress Specialist requirements",
        "sites.guidance.woocommerce_title": "WooCommerce requirements",
        "sites.guidance.wp_username": (
            "Username: WordPress admin username that owns the Application Password. Required."
        ),
        "sites.guidance.wp_app_password": (
            "Application Password: WP Admin -> Users -> Profile -> Application Passwords. "
            "User must have manage_options. Required."
        ),
        "sites.guidance.bridge_version": (
            "Airano MCP Bridge v2.11.0+ is recommended for companion-backed tools."
        ),
        "sites.guidance.bridge_lag": (
            "The WordPress.org plugin page can lag behind repository builds while "
            "publishing/review completes; do not assume the newest repo feature is "
            "already available there."
        ),
        "sites.guidance.companion_copy": (
            "Airano MCP Bridge — companion plugin (optional but recommended). Installing "
            "it unlocks larger uploads, unified site-health snapshot, cache purge, "
            "transient flush, bulk meta writes, structured export, capability probe, "
            "and audit-hook webhooks. Without it, basic tools still work but these "
            "features remain unavailable."
        ),
        "sites.guidance.wc_consumer_key": (
            "Consumer Key: WooCommerce -> Settings -> Advanced -> REST API -> Add Key. "
            "Read/Write permission. Required."
        ),
        "sites.guidance.wc_consumer_secret": (
            "Consumer Secret: shown once, starts with cs_, save immediately. Required."
        ),
        "sites.guidance.wc_no_extra_key": "No extra API key field exists for WooCommerce REST auth.",
        "sites.guidance.wc_media_username": (
            "WordPress Username for media tools: only required for AI/media tools like "
            "upload_and_attach_to_product, attach_media_to_product, set_featured_image, "
            "generate_and_upload_image with attach_to_post. Optional."
        ),
        "sites.guidance.wc_media_password": (
            "WordPress Application Password for media tools: required only for WC media "
            "uploads to /wp/v2/media; Consumer Key/Secret do not work for that. Optional."
        ),
        "api_keys.user_intro": "Use these to authenticate MCP clients to your hub.",
        "api_keys.admin_intro": "Personal and machine keys for MCP clients. Each key has separate access and an independent log.",
        "api_keys.admin_empty_cta": "Create one to authenticate MCP clients.",
        "api_keys.admin_warning": (
            "Admin access grants full system control including destructive operations "
            "(delete, write env, system tools). Anyone with this key can act on all your "
            "sites. Unless the client truly needs it, choose a narrower scope."
        ),
        "api_keys.user_empty_cta": "Create one to connect a client.",
        "api_keys.description": "Description",
        "api_keys.description_placeholder": "What is this key for?",
        "api_keys.expiry_label": "Expiry (days, optional)",
        "api_keys.expiry_placeholder": "Leave blank for no expiry",
        "api_keys.sensitive_warning": (
            "Reads backup files and environment variables that often contain sensitive data. "
            "Treat this key like a credential and do not share it over unencrypted channels."
        ),
        "api_keys.confirm_delete": 'Permanently delete "{name}"?\nThis cannot be undone.',
        "api_keys.confirm_delete_user": 'Delete "{name}"?\nThis key will stop working immediately.',
        "api_keys.confirm_revoke": 'Revoke "{name}"?\nThis key will stop working immediately.',
        "api_keys.toast_deleted": "Key deleted",
        "api_keys.toast_revoked": "Key revoked",
        # Audit log
        "audit.intro": (
            "Every authentication, tool call, and settings change. GDPR-compliant. "
            "Filters are applied server-side."
        ),
        "audit.col.time": "Time",
        "audit.col.actor": "User",
        "audit.col.event": "Event",
        "audit.col.level": "Level",
        "audit.col.message": "Message",
        "audit.col.result": "Result",
        "audit.col.target": "Target",
        "audit.col.duration": "Duration",
        "audit.search_placeholder": "Search user / event / target / message…",
        "audit.event_type_placeholder": "Event type (e.g. tool_call)",
        "audit.date_filter_title": "Filter by a day (YYYY-MM-DD)",
        "audit.level.info": "Info",
        "audit.level.warn": "Warning",
        "audit.no_entries": "No entries found.",
        "audit.zero_entries": "No entries",
        "audit.clear_filters": "Clear filters",
        "audit.page_label": "Page",
        "audit.page_size": "Page size",
        "audit.per_page": "{n} per page",
        "audit.range_of": "{from}–{to} of {total}",
        # Badges
        "badge.admin": "Admin",
        "badge.elevated": "Elevated",
        "badge.sensitive": "Sensitive",
        # Connect page
        "connect.connect_x": "Connect {name}",
        "connect.client.claude-code.desc": "CLI · Developer",
        "connect.client.vscode.desc": "Extension · Preview",
        "connect.client.cursor.desc": "JSON config",
        "connect.client.chatgpt.desc": "OAuth · Apps SDK",
        "connect.client.gemini.desc": "CLI · Token",
        "connect.client.custom.name": "Custom client",
        "connect.client.custom.desc": "Any MCP client",
        "connect.json.paste_into": "Paste this into your {name} MCP config",
        "connect.json.location_hint": "Settings → MCP Servers · File path differs by client",
        "connect.json.compatible": "Compatible:",
        "connect.json.custom_mcp": "Custom MCP",
        "connect.json.token_once": "Token shown only once",
        "connect.json.token_once_body": "Save it somewhere safe. You can rotate it anytime from API Keys.",
        "connect.claude.step1": "Use this connector URL",
        "connect.claude.step1_body": "Enter this URL in Claude.ai Connectors in your browser when it asks for the MCP endpoint.",
        "connect.claude.step2": "Confirm in Claude.ai",
        "connect.claude.step2_body_prefix": "Claude will show:",
        "connect.claude.step2_body_suffix": "Confirm to continue.",
        "connect.claude.step3": "You're connected",
        "connect.claude.step3_body": "You'll see the new client in your overview. Ask Claude to list your sites.",
        "connect.claude.prompt_text": "MCP Hub wants access to N tools",
        "connect.claude.open_desktop": "Open Claude Desktop",
        "connect.claude.link_lifetime": "Link valid for 10 minutes · One-time use",
        "connect.cli.step1": "Run this in your terminal",
        "connect.cli.step2": "Confirm",
        "connect.oauth.register_btn": "Register OAuth client",
        "connect.oauth.step1": "Register the OAuth app (once)",
        "connect.oauth.step1_body": "The hub creates an OAuth client and gives you a Redirect URL to paste into your AI tool manifest.",
        "connect.oauth.step2": "Sign in via the AI client",
        "connect.oauth.step2_body": 'Users see a "Sign in with MCP Hub" button. You confirm access once; the token refreshes automatically.',
        "connect.tier.admin_warning": (
            "Admin exposes destructive operations (delete posts, set options, install plugins, "
            "write env) on this site. Anyone with this site's token can act with full access. "
            "Unless the agent needs everything, choose a narrower scope."
        ),
        "connect.tier.install_warning": (
            "Installer is an elevated scope — installs run code from the WordPress/theme "
            "repository on your site. Only use when the client needs this access."
        ),
        "connect.tier.sensitive_warning": (
            "Sensitive reads is an elevated scope — includes backups and environment variables. "
            "Only use when the client needs this access."
        ),
        "connect.toast.scope_updated": "Tool access updated to {scope}",
        "connect.toast.scope_failed": "Update failed: {error}",
        # OAuth clients
        "oauth.empty": "You have no OAuth clients yet.",
        "oauth.register_first": "Register your first client",
        "oauth.none": "— None —",
        "oauth.allowed_scope": "Allowed scope",
        "oauth.confirm_delete": 'Delete OAuth client "{name}"?\nUsers signed in via this client will be disconnected.',
        "oauth.admin_warning": (
            "Admin scope on a third-party OAuth client allows that app to act on all your "
            "sites on behalf of users. Only use for trusted applications you control."
        ),
        "oauth.sensitive_warning": "Sensitive reads exposes backups and environment variables to the OAuth client.",
        "oauth.invalid_uris": "{n} URI is not a valid http(s) address:",
        "oauth.valid_uris": "{n} valid URI.",
        "oauth.toast_created": "Client created",
        "oauth.toast_deleted": "Client deleted",
        "oauth.toast_delete_failed": "Delete failed: {error}",
        "oauth.toast_create_failed": "Create failed: {error}",
        # Sites
        "sites.dialog_add_title": "Add site",
        "sites.dialog_add_submit": "Add site",
        "sites.dialog_edit_title": "Edit site",
        "sites.dialog_edit_submit": "Save changes",
        "sites.field_plugin_type": "Plugin",
        "sites.field_url": "URL",
        "sites.field_alias": "Alias",
        "sites.alias_placeholder": "short-site-id",
        "sites.alias_hint": "Short ID the AI sees as `site=…`. Lowercase letters, digits and hyphens only.",
        "sites.credentials": "Credentials",
        "sites.cred_unchanged": "Leave blank to keep the current value",
        "sites.show_advanced": "Show advanced fields",
        "sites.hide_advanced": "Hide advanced fields",
        "sites.manage_tools": "Manage tools",
        "sites.toast_created": "Site created",
        "sites.toast_updated": "Site updated",
        # Tier hints (used on the Connect page scope selector)
        "tier.read.hint": "List and inspect resources — read-only.",
        "tier.read_sensitive.hint": "Includes backups, environment variables, and other sensitive reads.",
        "tier.write.hint": "Create / update / delete resources and configuration.",
        "tier.editor.hint": "Pages, posts, content editing (wordpress_specialist F.19.5).",
        "tier.settings.hint": "Options, databases, identity, cron (wordpress_specialist F.19.6).",
        "tier.install.hint": "Install plugins/themes from the repository. Treat as elevated access.",
        "tier.deploy.hint": "Run deployments and lifecycle, without editing.",
        "tier.admin.hint": "Full system control including destructive operations.",
        "tier.custom.hint": "After selecting this, enable/disable tools manually.",
        # Pagination
        "previous": "Previous",
        "next": "Next",
        # Status labels
        "status.revoked": "Revoked",
        # Audit / generic
        "event_type": "Event type",
        "level": "Level",
        "date": "Date",
        "language": "Language",
        "theme": "Theme",
        "scope": "Scope",
        "saved": "Saved",
        "msg": "Message",
        "site_not_found": "Site not found",
    },
    "fa": {
        # Navigation
        "dashboard": "داشبورد",
        "projects": "پروژه‌ها",
        "api_keys": "کلیدهای API",
        "oauth_clients": "کلاینت‌های OAuth",
        "audit_logs": "لاگ‌های ممیزی",
        "health": "سلامت",
        "services": "سرویس‌ها",
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
        "site_updated": "سایت با موفقیت بروزرسانی شد",
        "site_deleted": "سایت حذف شد",
        "edit_site": "ویرایش سایت",
        "updating_site": "در حال بروزرسانی...",
        "keep_existing": "خالی بگذارید تا مقدار فعلی حفظ شود",
        "leave_blank_to_clear": "خالی بگذارید برای حذف مقدار (فیلد اختیاری)",
        "connection_ok": "اتصال برقرار",
        "connection_failed": "اتصال ناموفق",
        "last_tested": "آخرین تست",
        "never_tested": "هنوز تست نشده",
        "just_now": "همین الان",
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
        "sites.limit_reached_body": (
            "به سقف {limit} سرویس برای این حساب رسیده‌اید. یک سرویس موجود را حذف کنید "
            "یا از مدیر بخواهید این محدودیت را افزایش دهد."
        ),
        "sites.limit_reached_body_unknown": (
            "به سقف تعداد سرویس‌های این حساب رسیده‌اید. یک سرویس موجود را حذف کنید "
            "یا از مدیر بخواهید این محدودیت را افزایش دهد."
        ),
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
        "keys": "کلیدهای API",
        # Workspace / breadcrumbs
        "workspace": "فضای کاری",
        # Sidebar nav groups (G round)
        "nav.manage": "مدیریت",
        "nav.access": "دسترسی",
        "nav.observability": "پایش",
        "nav.account": "حساب",
        # Sidebar nav items
        "nav.overview": "نمای کلی",
        "nav.sites": "سایت‌ها",
        "nav.connect": "اتصال",
        "nav.api_keys": "کلیدهای API",
        "nav.oauth_clients": "کلاینت‌های OAuth",
        "nav.health": "سلامت",
        "nav.audit": "لاگ‌های ممیزی",
        "nav.settings": "تنظیمات",
        "nav.jump_to": "پرش به…",
        "nav.logout": "خروج",
        # Overview greeting (split from `welcome` so eyebrow + h1 don't duplicate)
        "welcome_eyebrow": "خوش آمدید مجدد",
        "welcome_greeting": "سلام",
        # Overview stat cards
        "card.active_sites_label": "سایت‌های فعال",
        "card.active_sites_caption": "سایت‌هایی که مدیریت می‌کنید",
        "card.api_keys_label": "کلیدهای API",
        "card.api_keys_caption": "کلیدهای شخصی و کلاینت",
        "card.tools_label": "ابزارهای در دسترس",
        "card.tools_caption": "از پلاگین‌های فعال",
        "card.healthy_sites_label": "سایت‌های سالم",
        "card.healthy_sites_caption": "سایت‌های موفق در تست اتصال",
        "card.uptime_label": "آپتایم (روز)",
        "card.uptime_caption": "دسترس‌پذیری هاب",
        # Overview sites table
        "your_sites": "سایت‌های شما",
        "health_connection_status": "وضعیت سلامت و اتصال",
        "manage": "مدیریت",
        "add_site_short": "افزودن سایت",
        "connect_client": "اتصال کلاینت",
        "register_first_site_body": (
            "یک پروژهٔ Coolify، سایت WordPress یا "
            "پلاگین پشتیبانی‌شدهٔ دیگر را ثبت کنید تا شروع کنید."
        ),
        "table.site": "سایت",
        "table.type": "نوع",
        "table.status": "وضعیت",
        "table.last_tested": "آخرین تست",
        # Status badges
        "status_healthy": "سالم",
        "status_warning": "هشدار",
        "status_error": "خطا",
        "status_unknown": "نامشخص",
        "status_untested": "تست‌نشده",
        # Topbar
        "topbar.toggle_sidebar": "نمایش/مخفی منو",
        "topbar.cycle_theme": "تغییر تم",
        "topbar.change_language": "تغییر زبان",
        "topbar.notifications": "اعلان‌ها",
        # Theme labels (mode picker)
        "theme.dark": "تاریک",
        "theme.light": "روشن",
        "theme.system": "سیستم",
        # Login (SPA)
        "login.welcome": "خوش آمدید مجدد",
        "login.subtitle": "به هاب MCP خود وارد شوید",
        "login.continue_github": "ادامه با GitHub",
        "login.continue_google": "ادامه با Google",
        "login.or_admin_key": "یا کلید مدیر",
        "login.master_key_label": "کلید API مستر",
        "login.sign_in": "ورود",
        "login.signing_in": "در حال ورود…",
        "login.failed": "ورود ناموفق",
        "login.invalid_key": "کلید API نامعتبر",
        "login.footer": "© mcphub.dev · خود-میزبان · متن‌باز",
        "login.testimonial": (
            "«شش ابزار AI من حالا یک کلید، یک لاگ ممیزی، یک دکمه‌ی ابطال "
            "مشترک دارند. نباید این‌قدر برای یک داشبورد هیجان‌زده باشم.»"
        ),
        "login.testimonial_author": "لنا ک.",
        "login.testimonial_role": "مهندس ارشد، همه چیز خود-میزبان",
        # Onboarding
        "onboarding.have_account": "حساب دارید؟",
        "onboarding.step_signin": "ورود",
        "onboarding.step_add_site": "افزودن سایت",
        "onboarding.step_get_key": "دریافت کلید",
        "onboarding.step_n_of": "مرحله {n} از {total}",
        "onboarding.signin_title": "با حساب GitHub یا Google خود وارد شوید",
        "onboarding.signin_body": (
            "ما از OAuth استفاده می‌کنیم — بدون رمز عبور و بدون فرآیند تأیید "
            "ایمیل. چند ثانیه طول می‌کشد."
        ),
        "onboarding.skip_signed_in": "رد کردن — قبلاً وارد شده‌ام",
        "onboarding.add_site_title": "اولین سایت خود را اضافه کنید",
        "onboarding.add_site_body": (
            "یک پروژه Coolify، سایت WordPress، نمونه Gitea یا هر پلاگین "
            "پشتیبانی‌شدهٔ دیگری را انتخاب کنید. بعداً می‌توانید بیشتر اضافه کنید."
        ),
        "onboarding.add_site_cta": "افزودن سایت",
        "onboarding.skip": "رد کردن",
        "onboarding.done_title": "آماده‌اید",
        "onboarding.done_body": (
            "به بخش «کلیدهای API» بروید تا یک کلید بسازید، یا مستقیم به "
            "«اتصال» بروید و کلاینت AI خود را وصل کنید."
        ),
        "onboarding.connect_client": "اتصال کلاینت",
        "onboarding.go_dashboard": "رفتن به داشبورد",
        # Common verbs & section labels
        "view.grid": "گرید",
        "view.list": "لیست",
        "table.tier": "سطح",
        "table.description": "توضیح",
        "table.prefix": "پیشوند",
        "table.created": "ایجاد شده",
        "table.last_used": "آخرین استفاده",
        "table.expiry": "انقضا",
        "table.project": "پروژه",
        "table.latency": "تأخیر",
        "table.uptime": "آپتایم",
        "table.tools": "ابزارها",
        "table.last_check": "آخرین بررسی",
        "table.scope": "دسترسی",
        "action.revoke": "ابطال",
        "action.copy": "کپی",
        "action.create": "ایجاد",
        "action.new_key": "کلید جدید",
        "action.new_client": "کلاینت جدید",
        "action.add_site_cta": "افزودن سایت",
        "action.save": "ذخیره",
        "action.reset": "بازنشانی",
        # Scope tier names
        "tier.read": "خواندن",
        "tier.read_sensitive": "خواندن حساس",
        "tier.deploy": "استقرار",
        "tier.editor": "ویرایش‌گر",
        "tier.settings": "تنظیمات",
        "tier.settings_scope": "تنظیمات",
        "tier.install": "نصب‌کننده",
        "tier.write": "نوشتن",
        "tier.admin": "مدیر",
        "tier.custom": "سفارشی",
        # Sites page
        "sites.intro": (
            "همهٔ سایت‌هایی که عامل‌های AI شما می‌بینند. سطح دسترسی برای هر "
            "سایت و هر کلید جداگانه تنظیم می‌شود."
        ),
        "sites.add_tile_title": "افزودن سایت",
        "sites.add_tile_desc": ("پروژهٔ Coolify، سایت WordPress یا پلاگین دیگر را ثبت کنید"),
        "sites.empty_body": (
            "یک پروژهٔ Coolify، سایت WordPress یا پلاگین پشتیبانی‌شدهٔ دیگر "
            "را ثبت کنید تا کلاینت‌های AI شما بتوانند از آن استفاده کنند."
        ),
        "filter.healthy": "سالم",
        "filter.untested": "تست‌نشده",
        # Health page
        "health.intro": "وضعیت هاب و هر سایت. هر ۳۰ ثانیه به‌روزرسانی می‌شود.",
        "health.all_operational": "همه سرویس‌ها عملیاتی هستند",
        "health.degraded": "اختلال جزئی",
        "health.down": "از کار افتاده",
        "health.projects_label": "پروژه‌ها",
        "health.alerts_label": "هشدارها",
        "health.total_requests": "کل درخواست‌ها",
        "health.per_minute": "در دقیقه",
        "health.error_rate": "نرخ خطا",
        "health.avg_response": "میانگین پاسخ",
        "health.recent_alerts": "هشدارهای اخیر",
        "health.metrics_title": "متریک‌های درخواست",
        "health.metrics_subtitle": "در فرآیند زنده",
        "health.no_alerts": "هیچ هشدار فعالی نیست.",
        "health.no_projects": "هنوز پروژه‌ای برای پایش نیست.",
        "health.registered": "ثبت‌شده",
        "health.up": "آپتایم",
        "health.last_check": "آخرین بررسی",
        "status.live": "زنده",
        # OAuth clients page
        "oauth.title": "کلاینت‌های OAuth 2.1",
        "oauth.intro": (
            "اپلیکیشن‌های شخص ثالث را که کاربران را در برابر هاب شما "
            "احراز هویت می‌کنند ثبت کنید. هر کلاینت credentials و دسترسی‌های خود را دارد."
        ),
        "oauth.redirect_uris": "آدرس‌های بازگشت (Redirect URIs)",
        "oauth.redirect_uris_one_per_line": "آدرس‌های بازگشت (هر کدام در یک خط)",
        # Settings tabs
        "settings.tab_profile": "پروفایل",
        "settings.tab_appearance": "ظاهر",
        "settings.tab_limits": "محدودیت‌ها",
        "settings.tab_plugins": "نمایش عمومی پلاگین‌ها",
        "settings.tab_danger": "منطقه خطر",
        "settings.appearance_subtitle": (
            "تم، زبان، رنگ برند، چگالی. تغییرات فوری اعمال می‌شوند و "
            "به‌صورت محلی ذخیره می‌گردند."
        ),
        "settings.brand_color": "رنگ برند",
        "settings.density": "چگالی",
        # Settings page (Round 2 i18n)
        "settings.intro": "پروفایل شما، تنظیمات هاب و یکپارچه‌سازی‌ها.",
        "settings.intro_admin_suffix": "بخش‌های مخصوص ادمین در نوار کناری مشخص شده‌اند.",
        "settings.profile_title": "پروفایل",
        "settings.profile_subtitle": "در سراسر هاب و برای ثبت رویدادهای ممیزی استفاده می‌شود",
        "settings.profile_footnote": (
            "اطلاعات پروفایل از طرف ارائه‌دهنده OAuth شما می‌آید و در این‌جا قابل ویرایش نیست. "
            "برای به‌روزرسانی، خارج شوید و دوباره وصل شوید."
        ),
        "settings.field_full_name": "نام کامل",
        "settings.field_email": "ایمیل",
        "settings.field_session_type": "نوع نشست",
        "settings.field_role": "نقش",
        "settings.limits_title": "محدودیت‌های کاربر",
        "settings.limits_subtitle": (
            "بیشینه‌ی سایت‌ها و محدودیت نرخ برای هر کاربر ثبت‌شده. "
            "در جدول تنظیمات SQLite ذخیره می‌شود."
        ),
        "settings.no_managed_limits": "محدودیت مدیریت‌شده‌ای یافت نشد.",
        "settings.plugins_title": "نمایان‌بودن پلاگین‌های عمومی",
        "settings.plugins_subtitle": (
            "انتخاب کنید کاربران غیر ادمین کدام پلاگین‌ها را ببینند. "
            "ادمین‌ها همیشه همه را می‌بینند."
        ),
        "settings.plugins_unavailable": "تنظیم ENABLED_PLUGINS در دسترس نیست.",
        "settings.source_label": "منبع",
        "settings.default_label": "پیش‌فرض",
        "settings.reset_default": "بازنشانی به پیش‌فرض",
        "settings.plugin.wordpress": "نوشته‌ها، برگه‌ها، رسانه و دیدگاه‌ها.",
        "settings.plugin.woocommerce": "محصولات، سفارش‌ها، مشتریان و گزارش‌ها.",
        "settings.plugin.wordpress_specialist": "متکی به پلاگین همراه: بلوک‌ها، فایل‌های قالب، پلاگین‌ها و دیتابیس.",
        "settings.plugin.supabase": "دیتابیس، احراز هویت، فضای ذخیره‌سازی و توابع.",
        "settings.plugin.openpanel": "آنالیتیکس محصول و خروجی رویدادها.",
        "settings.plugin.gitea": "مخزن‌ها، issueها، pull requestها و releaseها.",
        "settings.plugin.n8n": "گردش‌کارها و اجراها.",
        "settings.plugin.coolify": "اپلیکیشن‌ها، استقرارها، سرورها و سرویس‌ها.",
        "settings.plugin.appwrite": "به‌صورت پیش‌فرض پنهان است. فقط برای استقرارهای سفارشی فعال کنید.",
        "settings.plugin.directus": "به‌صورت پیش‌فرض پنهان است. فقط برای استقرارهای سفارشی فعال کنید.",
        "settings.danger_title": "منطقه خطر",
        "settings.danger_subtitle": (
            "اقدامات این بخش روی همه کاربران هاب اثر می‌گذارد. قبل از انجام، دو بار تأیید کنید."
        ),
        "settings.reset_all_title": "بازنشانی تنظیمات مدیریت‌شده",
        "settings.reset_all_body": (
            "overrideهای دیتابیس برای محدودیت‌های کاربر و نمایش عمومی پلاگین‌ها حذف می‌شود. "
            "مقدارهای env همچنان نسبت به پیش‌فرض اولویت دارند."
        ),
        "settings.reset_all_action": "بازنشانی همه تنظیمات مدیریت‌شده",
        "settings.reset_all_confirm": (
            "همه تنظیمات مدیریت‌شده به مقدار env/پیش‌فرض برگردند؟ این کار روی همه کاربران اثر می‌گذارد."
        ),
        "settings.reset_all_done": "تنظیمات مدیریت‌شده بازنشانی شد",
        "settings.reset_all_failed": "بازنشانی ناموفق بود: {error}",
        "badge.admin_lc": "مدیر",
        "toggle.on": "روشن",
        "toggle.off": "خاموش",
        "status.saving": "در حال ذخیره…",
        # NotFound page
        "notfound.title": "یافت نشد",
        "notfound.body": "صفحه‌ای که به دنبال آن بودید وجود ندارد یا جابه‌جا شده است.",
        "notfound.cta": "بازگشت به داشبورد",
        # Connect clients
        "connect.intro": "کلاینت AI خود را به هاب وصل کنید.",
        "connect.custom_name": "کلاینت سفارشی",
        "connect.custom_desc": "هر کلاینت MCP",
        "connect.tool_access": "دسترسی به ابزارها",
        "connect.tool_access_subtitle": "سطح ابزارهای MCP که این سایت در اختیار قرار می‌دهد را انتخاب کنید.",
        "connect.tool_access_pick_site": "ابتدا یک سایت را از بالا انتخاب کنید.",
        "connect.service_select_label": "سرویس",
        "connect.confirm_scope_change": "دسترسی ابزارهای «{site}» از «{from}» به «{to}» تغییر کند؟",
        "connect.client.claude-ai.desc": "مرورگر · فقط URL",
        "connect.client.claude-desktop.desc": "برنامه دسکتاپ · پیکربندی JSON",
        "connect.client.github-codex.desc": "config.toml · HTTP راه دور",
        "connect.desktop.open_step": "باز کردن Claude Desktop",
        "connect.desktop.open_body": (
            "با این میانبر وارد Claude Desktop شوید، سپس اگر برنامه همچنان به پیکربندی "
            "محلی سرور MCP نیاز داشت به این صفحه برگردید."
        ),
        "connect.desktop.open_button": "باز کردن Claude Desktop",
        "connect.desktop.open_fallback": (
            "اگر مرورگر برنامه دسکتاپ را باز نکرد، مراحل پیکربندی زیر را ادامه دهید."
        ),
        "connect.desktop.step1": "یک کلید API برای MCP Hub بسازید یا انتخاب کنید",
        "connect.desktop.step1_body": (
            "Claude Desktop از فایل پیکربندی محلی استفاده می‌کند. کلید mhu_ را به‌جای "
            "قراردادن مستقیم در JSON، در متغیر محیطی نگه دارید."
        ),
        "connect.desktop.step2": "این سرور را به claude_desktop_config.json اضافه کنید",
        "connect.desktop.config_paths": (
            "macOS: ~/Library/Application Support/Claude/claude_desktop_config.json · "
            "Windows: %APPDATA%\\Claude\\claude_desktop_config.json"
        ),
        "connect.desktop.step3": "Claude Desktop را دوباره اجرا کنید و ابزارها را بررسی کنید",
        "connect.desktop.step3_body": (
            "Claude Desktop را کامل ببندید، دوباره باز کنید، سپس از Claude بخواهید ابزارهای "
            "MCP Hub برای سرویس انتخاب‌شده را فهرست کند."
        ),
        "connect.desktop.oauth_note": (
            "Claude.ai Connectors مرورگری است و فقط URL لازم دارد. Claude Desktop به این "
            "پیکربندی JSON محلی و bearer token نیاز دارد."
        ),
        "table.service": "سرویس",
        "never": "هرگز",
        "all_sites": "همه سایت‌ها",
        "status.expired": "منقضی",
        "api_keys.select_service": "یک سرویس انتخاب کنید",
        "api_keys.service_hint": "این کلید به سرویس انتخاب‌شده محدود می‌شود. سطح ابزارها در صفحه دسترسی ابزار همان سرویس مدیریت می‌شود.",
        "connect.codex.env_var_title": "Codex توکن را از متغیر محیطی می‌خواند",
        "connect.codex.env_var_body": "bearer_token_env_var باید نام متغیر محیطی باشد، نه مقدار توکن mhu_. بعد از افزودن متغیرهای محیطی، Codex را دوباره اجرا کنید.",
        "connect.codex.step1": "توکن این سرویس را export کنید",
        "connect.codex.step2": "این بخش را به ~/.codex/config.toml اضافه کنید",
        "connect.codex.step3": "پیکربندی JSON کلود متفاوت است",
        "connect.codex.claude_difference": "برای Codex از بلوک TOML استفاده کنید. بلوک JSON فقط برای نمایش تفاوت headerهای سبک Claude آمده است.",
        "connect.codex.troubleshooting_title": "عیب‌یابی محیط‌های کدنویسی آنلاین",
        "connect.codex.troubleshooting_body": "codex mcp list را اجرا کنید، وجود bubblewrap/bwrap را بررسی کنید، و بعد از تغییر env varها نشست Codex را دوباره شروع کنید. کمبود وابستگی‌های sandbox ممکن است شبیه خطای احراز هویت MCP دیده شود.",
        "landing.continue_dashboard": "ادامه در داشبورد",
        "landing.hero_badge": "MCP 1.0 · Claude · ChatGPT · Cursor · Gemini",
        "landing.hero_title_line1": "یک هاب برای همه",
        "landing.hero_title_em": "اتصال‌های AI",
        "landing.hero_title_line2": "به سرویس‌های شما.",
        "landing.hero_body": (
            "MCP Hub لایه کنترل بین سرویس‌های self-hosted شما و ابزارهای AI است که با آن‌ها کار می‌کنند. "
            "کلید بسازید، Claude.ai، Claude Desktop، ChatGPT، Cursor یا Codex را وصل کنید و همه فراخوانی‌ها "
            "را از یک سطح تمیز بررسی کنید."
        ),
        "landing.nav.features": "ویژگی‌ها",
        "landing.nav.integrations": "یکپارچه‌سازی‌ها",
        "landing.nav.docs": "مستندات",
        "landing.nav.blog": "بلاگ",
        "landing.start_60": "شروع در ۶۰ ثانیه",
        "landing.get_started": "شروع کنید",
        "landing.create_account": "ایجاد حساب",
        "landing.integrations.eyebrow": "یکپارچه‌سازی‌ها",
        "landing.integrations.title": "ابزارهای مخصوص هر سرویس، در یک سطح MCP.",
        "landing.integrations.tile": "ابزارها، کلیدها، سلامت و ممیزی با دسترسی محدود.",
        "landing.features_eyebrow": "ویژگی‌ها",
        "landing.features_title": "هرچه عامل‌های AI شما نیاز دارند، بدون شلوغی اضافه.",
        "landing.feature.sites.title": "سرویس‌ها به‌عنوان موجودیت اصلی",
        "landing.feature.sites.desc": (
            "WordPress، WooCommerce، WordPress Specialist، Supabase، OpenPanel، Gitea، n8n و Coolify "
            "را ثبت کنید. هر سرویس به یک منبع MCP قابل کشف با ابزارها و سطح دسترسی خودش تبدیل می‌شود."
        ),
        "landing.feature.sites.tag": "هسته",
        "landing.feature.keys.title": "کلیدهای API محدودشده",
        "landing.feature.keys.desc": (
            "برای یک سرویس یا همه سایت‌ها کلید بسازید. سطح ابزارها همچنان مخصوص همان سرویس می‌ماند "
            "و بعداً قابل محدودتر شدن است."
        ),
        "landing.feature.keys.tag": "امنیت",
        "landing.feature.oauth.title": "OAuth 2.1 + PKCE",
        "landing.feature.oauth.desc": (
            "کلاینت‌های مرورگری مثل Claude.ai Connectors و ChatGPT را وصل کنید؛ کلاینت‌های دسکتاپ "
            "هم می‌توانند از URL مستقیم یا bearer token استفاده کنند."
        ),
        "landing.feature.oauth.tag": "احراز هویت",
        "landing.feature.health.title": "سلامت سرویس",
        "landing.feature.health.desc": (
            "وضعیت اعتبارنامه‌ها، latency و سلامت سرویس را ببینید تا عامل‌ها قبل از اقدام بدانند چه چیزی در دسترس است."
        ),
        "landing.feature.health.tag": "پایش",
        "landing.feature.audit.title": "ردپای کامل ممیزی",
        "landing.feature.audit.desc": (
            "هر فراخوانی ابزار، رویداد احراز هویت و تغییر تنظیمات قابل جست‌وجو است و به کاربر یا کلید مربوط وصل می‌شود."
        ),
        "landing.feature.audit.tag": "انطباق",
        "landing.feature.protocol.title": "ابزارهای بومی MCP",
        "landing.feature.protocol.desc": (
            "ابزارهای پلاگین‌ها را از طریق MCP ارائه کنید، بدون اینکه کاربر مجبور باشد API هر سرویس را دستی یاد بگیرد."
        ),
        "landing.feature.protocol.tag": "پروتکل",
        "landing.cta_title": "هاب خود را در یک دقیقه راه‌اندازی کنید.",
        "landing.cta_body": "روی هر نمونه Coolify مستقر کنید. برای استفاده شخصی رایگان. همیشه self-hosted.",
        "landing.footer_tagline": "لایه کنترل MCP self-hosted برای WordPress، Coolify، Gitea و سرویس‌های بیشتر.",
        "support_mcphub": "حمایت از MCP Hub",
        "connect.claude_ai.step1": "از URL کانکتور Claude.ai استفاده کنید",
        "sites.empty_search_title": "هیچ سایتی با این جست‌وجو پیدا نشد",
        "sites.empty_search_body": "نام مستعار دیگری امتحان کنید یا جست‌وجو را پاک کنید.",
        "sites.empty_healthy_title": "سایت سالمی وجود ندارد",
        "sites.empty_healthy_body": "تست اتصال را اجرا کنید یا فیلتر را پاک کنید تا همه سایت‌ها دیده شوند.",
        "sites.empty_untested_title": "سایت تست‌نشده‌ای وجود ندارد",
        "sites.empty_untested_body": "همه سایت‌ها تست شده‌اند. فیلتر را پاک کنید تا همه سایت‌ها دیده شوند.",
        "sites.selected_service": "سرویس انتخاب‌شده",
        "sites.show_advanced_for_service": "نمایش فیلدهای پیشرفته {service}",
        "sites.hide_advanced_for_service": "پنهان‌کردن فیلدهای پیشرفته {service}",
        "api_keys.user_intro": "از این کلیدها برای احراز هویت کلاینت‌های MCP استفاده کنید.",
        # Audit / generic
        "event_type": "نوع رویداد",
        "level": "سطح",
        "date": "تاریخ",
        "language": "زبان",
        "theme": "تم",
        "scope": "دسترسی",
        "saved": "ذخیره شد",
        "msg": "پیام",
        "site_not_found": "سایت یافت نشد",
        # Audit logs page (SPA)
        "audit.intro": (
            "هر احراز هویت، فراخوانی ابزار و تغییر تنظیمات. سازگار با GDPR. "
            "فیلترها در سمت سرور اعمال می‌شوند."
        ),
        "audit.search_placeholder": "جست‌وجوی کاربر / رویداد / هدف / پیام…",
        "audit.event_type_placeholder": "نوع رویداد (مثلاً tool_call)",
        "audit.date_filter_title": "فیلتر بر اساس یک روز (YYYY-MM-DD)",
        "audit.level.info": "اطلاع",
        "audit.level.warn": "هشدار",
        "audit.page_size": "اندازه‌ی صفحه",
        "audit.per_page": "{n} در صفحه",
        "audit.col.time": "زمان",
        "audit.col.actor": "کاربر",
        "audit.col.event": "رویداد",
        "audit.col.target": "هدف",
        "audit.col.message": "پیام",
        "audit.col.result": "نتیجه",
        "audit.col.level": "سطح",
        "audit.col.duration": "مدت",
        "audit.no_entries": "موردی یافت نشد.",
        "audit.clear_filters": "پاک کردن فیلترها",
        "audit.range_of": "{from}–{to} از {total}",
        "audit.zero_entries": "بدون مورد",
        "audit.page_label": "صفحه",
        "previous": "قبلی",
        "next": "بعدی",
        # API Keys page (SPA)
        "api_keys.admin_intro": (
            "کلیدهای شخصی و ماشینی برای کلاینت‌های MCP. " "هر کلید دسترسی مجزا و لاگ مستقل دارد."
        ),
        "api_keys.admin_empty_cta": "یکی بسازید تا کلاینت‌های MCP احراز هویت شوند.",
        "api_keys.user_empty_cta": "یکی بسازید تا یک کلاینت متصل شود.",
        "api_keys.no_services_title": "قبل از ساخت کلید API یک سرویس اضافه کنید",
        "api_keys.no_services_body": (
            "کلیدهای API کلاینت‌ها را به سرویس‌های شما متصل و احراز هویت می‌کنند. "
            "ابتدا از بخش سایت‌ها یک سرویس اضافه کنید، سپس برای همان سرویس یا همه سرویس‌ها کلید بسازید."
        ),
        "api_keys.description": "توضیح",
        "api_keys.description_placeholder": "این کلید برای چیست؟",
        "api_keys.expiry_label": "انقضا (روز، اختیاری)",
        "api_keys.expiry_placeholder": "خالی بگذارید برای بدون انقضا",
        "api_keys.admin_warning": (
            "دسترسی Admin کنترل کامل سامانه شامل عملیات مخرب (حذف، نوشتن env، "
            "ابزارهای سیستمی) را می‌دهد. هر کس این کلید را داشته باشد می‌تواند به جای شما "
            "روی همه‌ی سایت‌ها عمل کند. مگر اینکه کلاینت واقعاً نیاز داشته باشد، سطح محدودتری را انتخاب کنید."
        ),
        "api_keys.sensitive_warning": (
            "فایل‌های بک‌آپ و متغیرهای محیطی را می‌خواند که اغلب حاوی اطلاعات حساس هستند. "
            "این کلید را مانند یک اعتبارنامه تلقی کنید و در کانال‌های رمزنگاری‌نشده به اشتراک نگذارید."
        ),
        "api_keys.confirm_revoke": "لغو «{name}»؟\nاین کلید فوراً از کار خواهد افتاد.",
        "api_keys.confirm_delete": "حذف دائمی «{name}»؟\nاین عمل بازگشت‌پذیر نیست.",
        "api_keys.confirm_delete_user": "حذف «{name}»؟\nاین کلید فوراً از کار خواهد افتاد.",
        "api_keys.toast_revoked": "کلید لغو شد",
        "api_keys.toast_deleted": "کلید حذف شد",
        "status.revoked": "لغوشده",
        "badge.admin": "ادمین",
        "badge.sensitive": "حساس",
        "badge.elevated": "ارتقایافته",
        # Connect page — client tile descriptions
        "connect.client.claude-code.desc": "CLI · توسعه‌دهنده",
        "connect.client.cursor.desc": "پیکربندی JSON",
        "connect.client.chatgpt.desc": "OAuth · Apps SDK",
        "connect.client.gemini.desc": "CLI · توکن",
        "connect.client.vscode.desc": "افزونه · پیش‌نمایش",
        "connect.client.custom.desc": "هر کلاینت MCP",
        "connect.client.custom.name": "کلاینت سفارشی",
        "connect.no_services_title": "قبل از اتصال کلاینت‌ها یک سرویس اضافه کنید",
        "connect.no_services_body": (
            "کلاینت‌های MCP برای مسیردهی ابزارها حداقل به یک سرویس مثل WordPress، WooCommerce، "
            "Coolify یا سرویس دیگر نیاز دارند. ابتدا از سایت‌ها اولین سرویس را اضافه کنید، "
            "سپس برای URL کلاینت و مراحل راه‌اندازی به اینجا برگردید."
        ),
        "connect.connect_x": "اتصال {name}",
        # Connect — Claude flow
        "connect.claude.step1": "از این URL کانکتور استفاده کنید",
        "connect.claude.step1_body": (
            "این URL سرویس را در Claude.ai Connectors داخل مرورگر وارد کنید، وقتی نقطه پایانی MCP را می‌خواهد."
        ),
        "connect.claude.connector_tip": (
            "نکته: فقط به URL بالا نیاز دارید. هنگام اتصال می‌توانید با API Key یا GitHub/Google "
            "احراز هویت کنید."
        ),
        "connect.claude.open_desktop": "باز کردن Claude Desktop",
        "connect.claude.link_lifetime": "لینک ۱۰ دقیقه اعتبار دارد · فقط یک‌بار",
        "connect.claude.step2": "در Claude.ai تأیید کنید",
        "connect.claude.step2_body_prefix": "Claude نمایش می‌دهد:",
        "connect.claude.prompt_text": "MCP Hub می‌خواهد به N ابزار دسترسی داشته باشد",
        "connect.claude.step2_body_suffix": "برای ادامه تأیید کنید.",
        "connect.claude.step3": "متصل شدید",
        "connect.claude.step3_body": (
            "کلاینت جدید را در نمای کلی خود خواهید دید. از Claude بخواهید سایت‌های شما را فهرست کند."
        ),
        "connect.chatgpt.step1": "از URL کانکتور ChatGPT استفاده کنید",
        "connect.chatgpt.step1_body": (
            "این URL سرویس را کپی کنید. ChatGPT فقط به URL نقطه پایانی MCP نیاز دارد؛ MCP Hub "
            "هنگام اتصال ChatGPT احراز هویت را انجام می‌دهد."
        ),
        "connect.chatgpt.connector_tip": (
            "نکته: فقط به URL بالا نیاز دارید. هنگام اتصال با API Key یا GitHub/Google احراز هویت کنید."
        ),
        "connect.chatgpt.step2": "Developer mode را در ChatGPT فعال کنید",
        "connect.chatgpt.step2_body": (
            "در تنظیمات chatgpt.com ابتدا Developer mode را فعال کنید. سپس بخش Apps را باز کنید "
            "و گزینه Create app را انتخاب کنید."
        ),
        "connect.chatgpt.step3": "اپلیکیشن ChatGPT را بسازید",
        "connect.chatgpt.step3_body": (
            "Authorization را روی حالت OAuth بگذارید، که پیش‌فرض است، سپس URL بالا را به‌عنوان "
            "MCP server URL وارد کنید و تنظیمات اپلیکیشن را کامل کنید."
        ),
        # Connect — CLI flow
        "connect.cli.step1": "این را در ترمینال اجرا کنید",
        "connect.cli.step2": "تأیید کنید",
        # Connect — JSON flow
        "connect.json.paste_into": "این را در پیکربندی MCP {name} الصاق کنید",
        "connect.json.location_hint": "Settings → MCP Servers · مسیر فایل در هر کلاینت متفاوت است",
        "connect.json.token_once": "توکن فقط یک‌بار نمایش داده می‌شود",
        "connect.json.token_once_body": (
            "آن را جای امنی ذخیره کنید. هر زمان بخواهید می‌توانید از کلیدهای API بچرخانیدش."
        ),
        "connect.json.create_key_title": "ابتدا یک کلید API بسازید",
        "connect.json.create_key_body": (
            "از بخش کلیدهای API یک کلید بسازید، همان لحظه که فقط یک‌بار نمایش داده می‌شود کپی کنید، "
            "و سپس مقدار mhu_••••••• را در این پیکربندی جایگزین کنید. کلیدها را می‌توانید از "
            "کلیدهای API حذف و دوباره بسازید."
        ),
        "connect.json.compatible": "سازگار:",
        "connect.json.custom_mcp": "MCP سفارشی",
        # Connect — OAuth flow
        "connect.oauth.step1": "اپلیکیشن OAuth را ثبت کنید (یک‌بار)",
        "connect.oauth.step1_body": (
            "هاب یک کلاینت OAuth ایجاد می‌کند و یک Redirect URL در اختیار شما می‌گذارد "
            "تا در مانیفست ابزار AI الصاق کنید."
        ),
        "connect.oauth.register_btn": "ثبت کلاینت OAuth",
        "connect.oauth.step2": "از طریق کلاینت AI وارد شوید",
        "connect.oauth.step2_body": (
            "کاربران دکمه‌ی «Sign in with MCP Hub» را می‌بینند. یک‌بار دسترسی‌ها را تأیید می‌کنید؛ "
            "توکن خودش تجدید می‌شود."
        ),
        # Connect — tier warnings
        "connect.tier.admin_warning": (
            "Admin عملیات مخرب (حذف پست، تنظیم گزینه‌ها، نصب پلاگین، نوشتن env) را در دسترس قرار می‌دهد. "
            "هر کس توکن این سایت را داشته باشد می‌تواند با دسترسی کامل عمل کند. "
            "مگر اینکه ایجنت به همه‌ی ابزارها نیاز داشته باشد، سطح محدودتری را انتخاب کنید."
        ),
        "connect.tier.install_warning": (
            "Installer یک سطح ارتقایافته است — نصب‌ها کد را از مخزن WordPress / تم روی سایت شما اجرا می‌کنند. "
            "فقط زمانی استفاده کنید که کلاینت به این دسترسی نیاز دارد."
        ),
        "connect.tier.sensitive_warning": (
            "Sensitive reads یک سطح ارتقایافته است — خواندن‌های حساس شامل بک‌آپ‌ها و متغیرهای محیطی است. "
            "فقط زمانی استفاده کنید که کلاینت به این دسترسی نیاز دارد."
        ),
        "connect.toast.scope_updated": "دسترسی به ابزارها به {scope} به‌روز شد",
        "connect.toast.scope_failed": "به‌روزرسانی ناموفق: {error}",
        # Tier hints (shared between ApiKeys + Connect + OAuth dialogs)
        "tier.read.hint": "فهرست‌کردن و بازرسی فقط‌خواندنی روی منابع.",
        "tier.read_sensitive.hint": "شامل بک‌آپ‌ها، متغیرهای محیطی و سایر خواندن‌های حساس.",
        "tier.deploy.hint": "اجرای دیپلوی و چرخه‌ی حیات، بدون ویرایش.",
        "tier.editor.hint": "صفحات، پست‌ها، ویرایش محتوا (wordpress_specialist F.19.5).",
        "tier.settings.hint": "گزینه‌ها، پایگاه‌ها، هویت، کرون (wordpress_specialist F.19.6).",
        "tier.install.hint": "نصب پلاگین / تم از مخزن. به‌عنوان دسترسی بالا تلقی شود.",
        "tier.write.hint": "ایجاد / به‌روزرسانی / حذف منابع و پیکربندی.",
        "tier.admin.hint": "کنترل کامل سامانه شامل عملیات مخرب.",
        "tier.custom.hint": "بعد از انتخاب این، ابزارها را به‌صورت دستی فعال/غیرفعال کنید.",
        # OAuth Clients page
        "oauth.empty": "هنوز کلاینت OAuth ندارید.",
        "oauth.register_first": "ثبت اولین کلاینت",
        "oauth.none": "— هیچ‌کدام —",
        "oauth.invalid_uris": "{n} URI آدرس http(s) معتبر نیست:",
        "oauth.valid_uris": "{n} URI معتبر.",
        "oauth.allowed_scope": "دسترسی مجاز",
        "oauth.admin_warning": (
            "دسترسی Admin روی کلاینت OAuth شخص ثالث به آن اپ اجازه می‌دهد به جای کاربر "
            "روی همه‌ی سایت‌ها عمل کند. فقط برای اپلیکیشن‌های مورد اعتماد که تحت کنترل خودتان هستند استفاده کنید."
        ),
        "oauth.sensitive_warning": (
            "Sensitive reads بک‌آپ‌ها و متغیرهای محیطی را در اختیار کلاینت OAuth قرار می‌دهد."
        ),
        "oauth.confirm_delete": (
            "حذف کلاینت OAuth «{name}»؟\nکاربرانی که از طریق این کلاینت وارد شده‌اند قطع می‌شوند."
        ),
        "oauth.toast_deleted": "کلاینت حذف شد",
        "oauth.toast_created": "کلاینت ایجاد شد",
        "oauth.toast_delete_failed": "حذف ناموفق: {error}",
        "oauth.toast_create_failed": "ایجاد ناموفق: {error}",
        # Site Tools page (G.5c)
        "tools.eyebrow": "دسترسی به ابزارها",
        "tools.back_to_sites": "بازگشت به سایت‌ها",
        "tools.intro": (
            "هر یک از ابزارهای MCP که این سایت در اختیار می‌گذارد را فعال یا غیرفعال کنید. "
            "برای حالت متداول، تنظیم سطح در صفحه‌ی Connect ساده‌تر است — این صفحه برای ریزتنظیم است."
        ),
        "tools.preset_subtitle": (
            "یک پیش‌فرض سرویس یا گزینه سفارشی را انتخاب کنید، سپس ابزارهای جداگانه را پایین‌تر تنظیم کنید."
        ),
        "tools.search_placeholder": "فیلتر ابزارها…",
        "tools.scope_filter_all": "همه‌ی سطوح",
        "tools.empty": "این پلاگین هنوز ابزاری در دسترس نمی‌گذارد.",
        "tools.group_subtitle": "{n} ابزار در این سطح",
        "tools.unavailable": "در دسترس نیست",
        "tools.needs_provider_key": "نیاز به کلید ارائه‌دهنده‌ی AI دارد — بالای همین صفحه پیکربندی کنید.",
        "tools.configure_provider_key": "پیکربندی کلید",
        "tools.readiness_title": "آمادگی سرویس",
        "tools.readiness_subtitle": (
            "بررسی اعتبارنامه و سلامت تعیین می‌کند کدام ابزارها به کلاینت‌های MCP نمایش داده شوند."
        ),
        "tools.capability_status": "بررسی قابلیت‌ها",
        "tools.capability_ok": "اعتبارنامه برای سطح انتخاب‌شده کافی است",
        "tools.capability_warning": "اعتبارنامه پایین‌تر از سطح انتخاب‌شده است",
        "tools.capability_unavailable": "probe در دسترس نیست",
        "tools.capability_unknown_tier": "این سطح probe نشده است",
        "tools.capability_missing": "ناموجود",
        "tools.capability_probe_reason": "دلیل",
        "tools.capability_ai_providers": "ارائه‌دهنده‌های AI تنظیم‌شده",
        "tools.credential_requirement_title": "نیازمندی اعتبارنامه برای {scope}",
        "tools.credential_guide.wordpress.read": (
            "Application Password ذخیره‌شده در اعتبارنامه‌های سرویس بهتر است متعلق به کاربر WordPress "
            "با حداقل نقش Editor باشد. ابزارهای خواندنی پایه به قابلیت‌های CRUD نیاز ندارند."
        ),
        "tools.credential_guide.wordpress.admin": (
            "Application Password ذخیره‌شده در اعتبارنامه‌های سرویس برای CRUD کامل باید متعلق به "
            "Administrator وردپرس باشد. ابزارهای SEO و ابزارهای متکی به companion ممکن است به فعال بودن "
            "پلاگین متناظر هم نیاز داشته باشند."
        ),
        "tools.credential_guide.wordpress_specialist.read": (
            "Application Password باید متعلق به کاربر WordPress با manage_options (Administrator) باشد. "
            "برای ابزارهای companion-backed افزونه Airano MCP Bridge v2.11.0+ باید نصب و فعال باشد."
        ),
        "tools.credential_guide.wordpress_specialist.editor": (
            "همان پیش‌نیازهای Read، به‌علاوه Airano MCP Bridge v2.13.0+ برای ویرایش صفحه و "
            "v2.14.0+ برای CRUD فایل قالب. فراخوانی ابزارها همچنان edit_posts/edit_themes را بررسی می‌کنند."
        ),
        "tools.credential_guide.wordpress_specialist.settings": (
            "همان پیش‌نیازهای Editor. ابزارهای تنظیمات، هویت، پیوند یکتا و cron به Application Password "
            "مدیر با manage_options نیاز دارند."
        ),
        "tools.credential_guide.wordpress_specialist.install": (
            "همان پیش‌نیازهای Settings، به‌علاوه Airano MCP Bridge v2.14.0+ برای نصب/فعال‌سازی/حذف قالب "
            "و v2.15.0+ برای نصب/فعال‌سازی/به‌روزرسانی پلاگین."
        ),
        "tools.credential_guide.wordpress_specialist.admin": (
            "همان پیش‌نیازهای Installer، به‌علاوه مسیرهای مخرب مثل حذف و نصب از URL/zip. ویرایش فایل PHP "
            "نیاز دارد DISALLOW_FILE_EDIT تنظیم نشده یا false باشد."
        ),
        "tools.credential_guide.woocommerce.read": (
            "Consumer Key و Consumer Secret ذخیره‌شده برای WooCommerce REST API باید مجوز Read داشته باشند. "
            "کاربر سازنده در وردپرس بهتر است حداقل Shop Manager باشد تا سفارش‌ها و مشتری‌ها دیده شوند."
        ),
        "tools.credential_guide.woocommerce.admin": (
            "کلید WooCommerce REST API باید مجوز Read/Write داشته و متعلق به Administrator یا Shop Manager باشد. "
            "ابزارهای رسانه و تولید تصویر AI علاوه بر آن به WordPress username و Application Password نیاز دارند."
        ),
        "tools.tier_warning_title": "هشدار",
        "tools.tier_warning.install": (
            "Installer به عامل AI اجازه نصب و فعال‌سازی پلاگین یا قالب از مخزن‌های curated را می‌دهد. "
            "ابتدا روی staging تست کنید و افزونه‌های نصب‌شده را منظم مرور کنید."
        ),
        "tools.tier_warning.admin": (
            "Admin سطح کامل عملیات مخرب را می‌دهد: نصب دلخواه، حذف، CRUD کاربر و عملیات دیگری که ممکن است undo نداشته باشند. "
            "فقط جایی استفاده کنید که خطاها از بک‌آپ قابل بازیابی هستند."
        ),
        "tools.reason.provider_key": "نیاز به کلید ارائه‌دهنده AI",
        "tools.reason.provider_key_detail": "یک کلید ارائه‌دهنده را در بخش تولید تصویر با هوش مصنوعی پیکربندی کنید.",
        "tools.reason.companion_route": "نیاز به پلاگین همراه",
        "tools.reason.companion_route_detail": (
            "Airano MCP Bridge را نصب یا به‌روزرسانی کنید و تست اتصال را اجرا کنید."
        ),
        "tools.reason.feature": "نیاز به پلاگین SEO",
        "tools.reason.feature_detail": "قبل از فعال‌سازی این ابزار، پشتیبانی Rank Math یا Yoast را نصب کنید.",
        "tools.reason.wp_credentials": "نیاز به WP App Password",
        "tools.reason.wp_credentials_detail": (
            "برای آپلودهای رسانه، WordPress username و Application Password را در اعتبارنامه‌های سرویس اضافه کنید."
        ),
        "tools.reason.probe_unknown": "نیاز به بررسی سلامت",
        "tools.reason.probe_unknown_detail": (
            "تست اتصال را اجرا کنید تا MCP Hub قابلیت‌های سرویس را تأیید کند."
        ),
        "tools.toast_failed": "به‌روزرسانی ابزار ناموفق بود: {error}",
        "tools.sensitivity.destructive": "مخرب",
        "tools.sensitivity.sensitive": "حساس",
        "providers.title": "تولید تصویر با هوش مصنوعی",
        "providers.subtitle": (
            "کلید API ارائه‌دهنده‌ها را برای همین سرویس ذخیره کنید. ابزارهای تولید تصویر "
            "تا زمانی که کلید ارائه‌دهنده تنظیم نشده و اتصال سرویس سالم نباشد در دسترس نیستند."
        ),
        "providers.status_set": "تنظیم‌شده",
        "providers.status_unset": "تنظیم‌نشده",
        "providers.new_key_placeholder": "کلید API جدید",
        "providers.remove": "حذف",
        "providers.encrypted_note": "کلیدها رمزگذاری می‌شوند و فقط به همین سرویس محدود هستند.",
        "providers.toast_saved": "کلید ارائه‌دهنده ذخیره شد",
        "providers.toast_save_failed": "ذخیره ناموفق بود: {error}",
        "providers.toast_removed": "کلید ارائه‌دهنده حذف شد",
        "providers.toast_remove_failed": "حذف ناموفق بود: {error}",
        "providers.confirm_remove": "این کلید ارائه‌دهنده حذف شود؟",
        "providers.hint.openai": "برای جایگزینی مقدار ذخیره‌شده، کلید جدید ذخیره کنید.",
        "providers.hint.stability": "برای جایگزینی مقدار ذخیره‌شده، کلید جدید ذخیره کنید.",
        "providers.hint.replicate": "برای جایگزینی مقدار ذخیره‌شده، کلید جدید ذخیره کنید.",
        "providers.hint.openrouter": (
            "از مدل‌های تصویری OpenRouter پشتیبانی می‌کند. کلید را اینجا ذخیره کنید، "
            "سپس مدل پیش‌فرض این سرویس را انتخاب کنید."
        ),
        "providers.model.loading": "در حال دریافت مدل‌های تصویری…",
        "providers.model.failed": (
            "دریافت مدل‌های تصویری OpenRouter ناموفق بود. اگر اتصال ارائه‌دهنده سالم نباشد، ابزار غیرفعال می‌ماند."
        ),
        "providers.model.empty": "هیچ مدل تصویری OpenRouter برای این کلید پیدا نشد.",
        "providers.model.default_label": "مدل تصویری پیش‌فرض",
        "providers.model.select": "انتخاب مدل",
        "providers.model.set_default": "تنظیم پیش‌فرض",
        "providers.model.clear": "پاک کردن",
        "providers.model.current": "پیش‌فرض فعلی: {model}",
        "providers.model.toast_saved": "مدل تصویری پیش‌فرض ذخیره شد",
        "providers.model.toast_cleared": "مدل تصویری پیش‌فرض پاک شد",
        "providers.model.toast_failed": "به‌روزرسانی مدل ناموفق بود: {error}",
        "sites.ai_image.title": "تولید تصویر با هوش مصنوعی",
        "sites.ai_image.create_body": (
            "پس از ایجاد این سرویس، در Tool access کلید OpenAI، Stability AI، Replicate یا OpenRouter "
            "را اضافه کنید. ابزار تولید تصویر تا زمان ذخیره کلید ارائه‌دهنده و سالم بودن اتصال سرویس "
            "در دسترس نیست."
        ),
        "sites.ai_image.edit_body": (
            "تولید تصویر برای هر سرویس در Tool access پیکربندی می‌شود. کلید OpenAI، Stability AI، "
            "Replicate یا OpenRouter را آنجا اضافه کنید؛ برای OpenRouter می‌توان مدل تصویری پیش‌فرض "
            "هم انتخاب کرد."
        ),
        "sites.ai_image.open_tools": "باز کردن تنظیمات تولید تصویر",
        "sites.manage_tools": "مدیریت ابزارها",
        # Site Add/Edit dialog (G.12)
        "sites.dialog_add_title": "افزودن سایت",
        "sites.dialog_edit_title": "ویرایش سایت",
        "sites.dialog_add_submit": "افزودن سایت",
        "sites.dialog_edit_submit": "ذخیره‌ی تغییرات",
        "sites.field_plugin_type": "پلاگین",
        "sites.field_alias": "شناسه (alias)",
        "sites.field_url": "آدرس",
        "sites.alias_placeholder": "شناسه‌ی-کوتاه-سایت",
        "sites.alias_hint": (
            "شناسه‌ی کوتاهی که AI آن را به‌صورت `site=…` می‌بیند. فقط حروف کوچک، رقم و خط تیره."
        ),
        "sites.credentials": "اعتبارها",
        "sites.cred_unchanged": "خالی بگذارید تا مقدار فعلی حفظ شود",
        "sites.guidance.wordpress_title": "نیازمندی‌های WordPress",
        "sites.guidance.wordpress_specialist_title": "نیازمندی‌های WordPress Specialist",
        "sites.guidance.woocommerce_title": "نیازمندی‌های WooCommerce",
        "sites.guidance.wp_username": (
            "Username: نام کاربری مدیر وردپرس که مالک Application Password است. الزامی."
        ),
        "sites.guidance.wp_app_password": (
            "Application Password: از WP Admin -> Users -> Profile -> Application Passwords بسازید. "
            "کاربر باید manage_options داشته باشد. الزامی."
        ),
        "sites.guidance.bridge_version": (
            "Airano MCP Bridge v2.11.0+ برای ابزارهای companion-backed توصیه می‌شود."
        ),
        "sites.guidance.bridge_lag": (
            "صفحه افزونه در WordPress.org ممکن است به‌دلیل فرایند انتشار/بازبینی از نسخه‌های "
            "مخزن عقب‌تر باشد؛ فرض نکنید تازه‌ترین قابلیت مخزن همان‌جا هم منتشر شده است."
        ),
        "sites.guidance.companion_copy": (
            "Airano MCP Bridge — companion plugin (اختیاری اما توصیه‌شده). نصب آن آپلودهای بزرگ‌تر، "
            "site-health یکپارچه، cache purge، transient flush، bulk meta writes، structured export، "
            "capability probe و audit-hook webhooks را فعال می‌کند. بدون آن، ابزارهای پایه همچنان "
            "کار می‌کنند اما این قابلیت‌ها در دسترس نیستند."
        ),
        "sites.guidance.wc_consumer_key": (
            "Consumer Key: در WooCommerce -> Settings -> Advanced -> REST API -> Add Key بسازید. "
            "مجوز Read/Write. الزامی."
        ),
        "sites.guidance.wc_consumer_secret": (
            "Consumer Secret: فقط یک‌بار نمایش داده می‌شود، با cs_ شروع می‌شود و باید همان لحظه ذخیره شود. الزامی."
        ),
        "sites.guidance.wc_no_extra_key": "برای احراز هویت WooCommerce REST فیلد API key جداگانه‌ای وجود ندارد.",
        "sites.guidance.wc_media_username": (
            "WordPress Username برای ابزارهای رسانه فقط برای ابزارهای AI/media مثل "
            "upload_and_attach_to_product، attach_media_to_product، set_featured_image و "
            "generate_and_upload_image با attach_to_post لازم است. اختیاری."
        ),
        "sites.guidance.wc_media_password": (
            "WordPress Application Password برای ابزارهای رسانه فقط هنگام آپلود WC به /wp/v2/media لازم است؛ "
            "Consumer Key/Secret برای این مسیر کار نمی‌کنند. اختیاری."
        ),
        "sites.show_advanced": "نمایش فیلدهای پیشرفته",
        "sites.hide_advanced": "پنهان‌کردن فیلدهای پیشرفته",
        "sites.toast_created": "سایت ایجاد شد",
        "sites.toast_updated": "سایت به‌روز شد",
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


def resolve_public_base_url(request: Request) -> str:
    """Return the canonical public base URL for this MCPHub instance.

    Order of precedence:
      1. ``PUBLIC_URL`` env var when set AND non-empty.
      2. The incoming request, honouring ``X-Forwarded-Proto`` and
         ``X-Forwarded-Host`` (set by Cloudflare / Coolify Traefik /
         most reverse proxies). This makes ``/u/{user}/{alias}/mcp``
         render with the public hostname even on test deployments
         where the operator forgot to set ``PUBLIC_URL``.
      3. Hard fallback to ``http://localhost:8000`` for the bare
         ``python server.py`` development workflow.

    The previous ``os.environ.get("PUBLIC_URL", "http://localhost:8000")``
    pattern silently broke when ``PUBLIC_URL=''`` was set in env vars
    (the empty string is still a value, so the default never fires) —
    that's the bug behind the missing host on dashboard MCP-endpoint
    URLs reported on mcp-test 2026-05-01.
    """
    env_url = os.environ.get("PUBLIC_URL", "").strip().rstrip("/")
    if env_url:
        return env_url

    proto = (request.headers.get("x-forwarded-proto") or request.url.scheme).split(",")[0].strip()
    host = (
        (
            request.headers.get("x-forwarded-host")
            or request.headers.get("host")
            or request.url.netloc
        )
        .split(",")[0]
        .strip()
    )
    if proto and host:
        return f"{proto}://{host}".rstrip("/")
    return "http://localhost:8000"


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

    # Platform stats (registered users + their sites)
    try:
        from core.database import get_database

        db = get_database()
        stats["users_count"] = await db.count_all_users()
        stats["user_sites_count"] = await db.count_all_sites()
        stats["recent_users_count"] = await db.count_recent_users(days=7)
    except Exception as e:
        logger.debug(f"Error getting platform stats: {e}")
        stats.setdefault("users_count", 0)
        stats.setdefault("user_sites_count", 0)
        stats.setdefault("recent_users_count", 0)

    return stats


async def get_user_dashboard_stats(user_id: str) -> dict:
    """Get dashboard statistics for an OAuth user."""
    stats = {
        "sites_count": 0,
        "active_sites_count": 0,
        "api_keys_count": 0,
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
        return RedirectResponse(url="/dashboard/overview", status_code=303)

    # Get language
    accept_language = request.headers.get("accept-language")
    query_lang = request.query_params.get("lang")
    lang = detect_language(accept_language, query_lang)
    t = get_translations(lang)

    error = request.query_params.get("error")
    next_url = request.query_params.get("next", "/dashboard")

    return templates.TemplateResponse(
        request,
        "dashboard/login.html",
        {
            "lang": lang,
            "t": t,
            "error": error,
            "next_url": next_url,
            "version": _get_project_version(),
        },
    )


async def _ensure_master_key_user(auth) -> str | None:
    """Ensure a user record exists for master key admin.

    Creates a user with provider='master_key' if none exists,
    then returns a user session JWT so the admin can use My Sites, Connect, etc.

    Returns:
        User session JWT token, or None if creation failed.
    """
    from core.database import get_database
    from core.user_auth import get_user_auth

    db = get_database()
    user_auth = get_user_auth()

    # Check if master key user already exists
    user = await db.get_user_by_provider("master_key", "master")
    if not user:
        # Create user record for master key admin
        user = await db.create_user(
            email="admin@localhost",
            name="Admin",
            provider="master_key",
            provider_id="master",
            role="admin",
        )
        logger.info("Created user record for master key admin: %s", user["id"])
    else:
        # Update last login
        await db.update_user_last_login(user["id"])

    # Create user session JWT (same as OAuth users get)
    token = user_auth.create_user_session(
        user_id=user["id"],
        email=user["email"],
        name=user.get("name"),
        role="admin",
    )
    return token


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
            url=f"/dashboard-legacy/login?error=rate_limit&lang={lang}",
            status_code=303,
        )

    # Record login attempt
    auth.record_login_attempt(client_ip)

    # Get form data
    form = await request.form()
    api_key = form.get("api_key", "")
    next_url = form.get("next", "/dashboard/overview")

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
            url=f"/dashboard-legacy/login?error=invalid&next={next_url}&lang={lang}",
            status_code=303,
        )

    # Create session
    token = auth.create_session(user_type, key_id)

    # For master key login: auto-create user record + user session
    # so master key admin can access My Sites, Connect, etc.
    if user_type == "master":
        try:
            user_token = await _ensure_master_key_user(auth)
            if user_token:
                token = user_token  # Use user session instead of admin session
        except Exception as e:
            logger.warning("Failed to create master key user record: %s", e)
            # Fall back to admin-only session (sites won't work, but dashboard will)

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


async def dashboard_api_login(request: Request) -> Response:
    """POST /api/dashboard/login — JSON variant of the master-key login form.

    Accepts JSON or form-encoded ``api_key``. Returns JSON instead of a 303
    redirect so the SPA can call it via fetch without a full reload. The
    session cookie is set on success exactly the same way as the legacy form
    handler; the SPA then navigates client-side to ``next``.

    Response shapes::

        200 {"ok": true, "next": "/dashboard/overview"}
        401 {"ok": false, "error": "invalid"}
        429 {"ok": false, "error": "rate_limit"}
    """
    from starlette.responses import JSONResponse

    auth = get_dashboard_auth()
    client_ip = get_client_ip(request)

    # Rate limit before doing any work.
    if not auth.check_rate_limit(client_ip):
        logger.warning(f"Dashboard login rate limit exceeded for {client_ip}")
        return JSONResponse({"ok": False, "error": "rate_limit"}, status_code=429)

    auth.record_login_attempt(client_ip)

    # Accept JSON or form-encoded — both common from a fetch() call.
    api_key = ""
    next_url = "/dashboard/overview"
    content_type = (request.headers.get("content-type") or "").lower()
    if "application/json" in content_type:
        try:
            body = await request.json()
            api_key = str(body.get("api_key") or "")
            next_url = str(body.get("next") or "/dashboard/overview")
        except Exception:
            return JSONResponse({"ok": False, "error": "invalid_body"}, status_code=400)
    else:
        form = await request.form()
        api_key = str(form.get("api_key") or "")
        next_url = str(form.get("next") or "/dashboard/overview")

    is_valid, user_type, key_id = auth.validate_api_key(api_key)
    if not is_valid:
        logger.warning(f"Dashboard login failed for {client_ip}")
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
        return JSONResponse({"ok": False, "error": "invalid"}, status_code=401)

    # Mirror the legacy handler: create admin session, then upgrade to user
    # session for master-key logins so My Sites / Connect work.
    token = auth.create_session(user_type, key_id)
    if user_type == "master":
        try:
            user_token = await _ensure_master_key_user(auth)
            if user_token:
                token = user_token
        except Exception as e:
            logger.warning("Failed to create master key user record: %s", e)

    response = JSONResponse({"ok": True, "next": next_url})
    auth.set_session_cookie(response, token)

    try:
        from core.audit_log import get_audit_logger

        audit_logger = get_audit_logger()
        if audit_logger:
            audit_logger.log_authentication(success=True, ip_address=client_ip)
    except Exception as e:
        logger.warning(f"Failed to log auth event: {e}")
        logger.info(f"Dashboard login successful (api): type={user_type}, ip={client_ip}")
    return response


async def auth_logout(request: Request) -> Response:
    """Clear OAuth user session cookie."""
    from core.dashboard.auth import get_dashboard_auth

    auth = get_dashboard_auth()
    response = RedirectResponse(url="/dashboard/login", status_code=303)
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

    return templates.TemplateResponse(request, "dashboard/index.html", context)


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

        is_admin = False
        current_user_id = None
        if user_session:
            if (
                hasattr(user_session, "user_type")
                and user_session.user_type == "master"
                or isinstance(user_session, dict)
                and user_session.get("role") == "admin"
            ):
                is_admin = True
            elif isinstance(user_session, dict) and "user_id" in user_session:
                current_user_id = user_session["user_id"]

        for site in sites:
            # Tenant isolation checks
            site_user_id = site.get("user_id")
            if not is_admin:
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
        request,
        "dashboard/projects/list.html",
        {
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
            request,
            "dashboard/projects/list.html",
            {
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
        request,
        "dashboard/projects/detail.html",
        {
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
        request,
        "dashboard/api-keys/list.html",
        {
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


async def dashboard_api_keys_list_json(request: Request) -> Response:
    """GET /api/dashboard/api-keys — JSON list of admin API keys.

    Track G companion to the legacy ``/dashboard/api-keys`` HTML page. The SPA
    consumes ``keys`` as an array; pagination metadata is returned alongside it
    for callers that need it.
    """
    session, redirect = _require_admin_session(request)
    if redirect:
        return JSONResponse({"error": "Admin access required"}, status_code=403)

    project_filter = request.query_params.get("project", "")
    status_filter = request.query_params.get("status", "active")
    search = request.query_params.get("search", "")
    page = int(request.query_params.get("page", 1))

    keys_data = await get_all_api_keys(
        project_id=project_filter if project_filter else None,
        status=status_filter,
        search=search if search else None,
        page=page,
    )
    return JSONResponse(
        {
            "keys": keys_data["api_keys"],
            "total_count": keys_data["total_count"],
            "total_pages": keys_data["total_pages"],
            "current_page": keys_data["current_page"],
            "per_page": keys_data["per_page"],
        }
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
                    "owner_user_id": getattr(client, "owner_user_id", None),
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
    """Render OAuth clients list page (admin and user)."""
    # Try admin session first, then user session
    auth = get_dashboard_auth()
    session = None
    is_admin = False
    user_id = None

    admin_session = auth.get_session_from_request(request)
    if admin_session and is_admin_session(admin_session):
        session = admin_session
        is_admin = True
    else:
        user_session = auth.get_user_session_from_request(request)
        if user_session:
            session = user_session
            is_admin = is_admin_session(user_session)
            user_id = user_session.get("user_id")

    if not session:
        return RedirectResponse(url="/dashboard/login", status_code=303)

    # Get language
    accept_language = request.headers.get("accept-language")
    query_lang = request.query_params.get("lang")
    lang = detect_language(accept_language, query_lang)
    t = get_translations(lang)

    # Get clients data — admin sees all, user sees own
    clients_data = await get_oauth_clients_data()
    if not is_admin and user_id:
        clients_data["clients"] = [
            c for c in clients_data["clients"] if c.get("owner_user_id") == user_id
        ]
        clients_data["total_count"] = len(clients_data["clients"])

    return templates.TemplateResponse(
        request,
        "dashboard/oauth-clients/list.html",
        {
            "lang": lang,
            "t": t,
            "session": session,
            "clients": clients_data["clients"],
            "total_count": clients_data["total_count"],
            "current_page": "oauth_clients",
            "is_admin": is_admin,
        },
    )


async def dashboard_oauth_clients_list_json(request: Request) -> Response:
    """GET /api/dashboard/oauth-clients — JSON list of OAuth clients.

    Track G companion to the legacy ``/dashboard/oauth-clients`` HTML page.
    Admin sees every client; OAuth users see only the clients they own.
    """
    auth = get_dashboard_auth()
    is_admin = False
    user_id: str | None = None

    admin_session = auth.get_session_from_request(request)
    if admin_session and is_admin_session(admin_session):
        is_admin = True
    else:
        user_session = auth.get_user_session_from_request(request)
        if user_session:
            is_admin = is_admin_session(user_session)
            user_id = user_session.get("user_id") if isinstance(user_session, dict) else None
        else:
            return JSONResponse({"error": "Authentication required"}, status_code=401)

    clients_data = await get_oauth_clients_data()
    if not is_admin and user_id:
        clients_data["clients"] = [
            c for c in clients_data["clients"] if c.get("owner_user_id") == user_id
        ]
        clients_data["total_count"] = len(clients_data["clients"])

    return JSONResponse(
        {
            "clients": clients_data["clients"],
            "total_count": clients_data["total_count"],
        }
    )


async def dashboard_oauth_clients_create(request: Request) -> Response:
    """API endpoint to create OAuth client (admin and user)."""
    # Accept both admin and user sessions
    auth = get_dashboard_auth()
    owner_user_id = None

    admin_session = auth.get_session_from_request(request)
    user_session = auth.get_user_session_from_request(request)

    if admin_session and is_admin_session(admin_session):
        pass  # Admin — no owner_user_id
    elif user_session:
        owner_user_id = user_session.get("user_id")
    else:
        return JSONResponse({"error": "Authentication required"}, status_code=403)

    try:
        data = await request.json()
        client_name = data.get("client_name") or data.get("name")
        # Support both single redirect_uri and multiple redirect_uris
        redirect_uris = data.get("redirect_uris") or []
        if not redirect_uris and data.get("redirect_uri"):
            redirect_uris = [data.get("redirect_uri")]
        # OAuth clients are app registrations, not the tool-access boundary.
        # Issue them broad/system capability; per-service Tool Access and
        # per-tool toggles narrow the actual MCP surface at request time.
        scopes = [
            "read",
            "read:sensitive",
            "deploy",
            "editor",
            "settings",
            "install",
            "write",
            "admin",
        ]

        if not client_name or not redirect_uris:
            return JSONResponse({"error": "Missing required fields"}, status_code=400)

        from core.oauth.client_registry import get_client_registry

        client_registry = get_client_registry()

        create_kwargs = {
            "client_name": client_name,
            "redirect_uris": redirect_uris,
            "allowed_scopes": scopes,
        }
        if owner_user_id:
            create_kwargs["owner_user_id"] = owner_user_id

        client_id, client_secret = client_registry.create_client(**create_kwargs)

        # Log the action
        from core.audit_log import get_audit_logger

        audit_logger = get_audit_logger()
        audit_logger.log_system_event(
            event=f"OAuth client created: {client_name}",
            details={"client_id": client_id, "owner_user_id": owner_user_id},
        )

        return JSONResponse(
            {
                "success": True,
                "client_id": client_id,
                "client_secret": client_secret,
                "client": {
                    "client_id": client_id,
                    "client_name": client_name,
                    "redirect_uris": redirect_uris,
                    "grant_types": ["authorization_code", "refresh_token"],
                    "allowed_scopes": scopes,
                    "created_at": "",
                    "owner_user_id": owner_user_id,
                },
            }
        )

    except Exception as e:
        logger.error(f"Error creating OAuth client: {e}")
        return JSONResponse({"error": "Failed to create client"}, status_code=500)


async def dashboard_oauth_clients_delete(request: Request) -> Response:
    """API endpoint to delete OAuth client (admin and user)."""
    # Accept both admin and user sessions
    auth = get_dashboard_auth()
    is_admin_user = False
    user_id = None

    admin_session = auth.get_session_from_request(request)
    user_session = auth.get_user_session_from_request(request)

    if admin_session and is_admin_session(admin_session):
        is_admin_user = True
    elif user_session:
        user_id = user_session.get("user_id")
        is_admin_user = is_admin_session(user_session)
    else:
        return JSONResponse({"error": "Authentication required"}, status_code=403)

    try:
        client_id = request.path_params.get("client_id", "")

        from core.oauth.client_registry import get_client_registry

        client_registry = get_client_registry()

        # Non-admin users can only delete their own clients
        if not is_admin_user and user_id:
            client = client_registry.get_client(client_id)
            if not client:
                return JSONResponse({"error": "Client not found"}, status_code=404)
            if getattr(client, "owner_user_id", None) != user_id:
                return JSONResponse({"error": "Access denied"}, status_code=403)

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
        request,
        "dashboard/audit-logs/list.html",
        {
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


# Map the SPA's lowercase level filter values ("info"/"warn"/"error") to the
# uppercase LogLevel enum values stored on disk. The legacy Jinja form sends
# raw enum values, so passthrough is preserved for any unknown value.
_SPA_LEVEL_TO_BACKEND: dict[str, str] = {
    "info": "INFO",
    "warn": "WARNING",
    "warning": "WARNING",
    "error": "ERROR",
    "critical": "CRITICAL",
}


def _transform_audit_entry_for_spa(entry: dict) -> dict:
    """Map a raw audit log row to the AuditEntry shape the SPA expects.

    The on-disk schema differs per event_type (tool_call has tool_name + site,
    auth has ip_address + reason, etc.) so the SPA can't render columns like
    Target/Message/Result/Actor without this normalisation pass.
    """
    event_type = entry.get("event_type") or "unknown"
    level_raw = (entry.get("level") or "").upper()
    if level_raw in ("ERROR", "CRITICAL"):
        level: str = "error"
    elif level_raw in ("WARN", "WARNING"):
        level = "warn"
    else:
        level = "info"

    actor: str | None = None
    target: str | None = None
    message: str | None = None
    result: str | None = None
    success = entry.get("success")

    if event_type == "tool_call":
        actor = entry.get("user_id") or "system"
        site = entry.get("site")
        tool = entry.get("tool_name")
        target = f"{tool} @ {site}" if tool and site else (tool or site)
        message = entry.get("error") or entry.get("result_summary")
        result = "ok" if success else "error"
    elif event_type == "authentication":
        actor = entry.get("project_id") or "anonymous"
        target = entry.get("project_id")
        message = entry.get("reason") or ("ok" if success else "denied")
        result = "ok" if success else "denied"
    elif event_type == "error":
        actor = "system"
        target = entry.get("error_type")
        message = entry.get("error_message")
        result = "error"
    elif event_type == "system":
        actor = "system"
        target = entry.get("event")
        details = entry.get("details")
        if isinstance(details, dict):
            message = details.get("message") or details.get("event")
        result = "ok"

    return {
        "id": entry.get("id"),
        "timestamp": entry.get("timestamp"),
        "event_type": event_type,
        "level": level,
        "actor": actor,
        "target": target,
        "message": message,
        "ip": entry.get("ip_address"),
        "duration_ms": entry.get("duration_ms"),
        "result": result,
    }


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

        if level:
            level = _SPA_LEVEL_TO_BACKEND.get(level.lower(), level)

        logs_data = await get_audit_logs_data(
            event_type=event_type,
            level=level,
            date=date,
            search=search,
            page=page,
        )

        logs_data["logs"] = [_transform_audit_entry_for_spa(e) for e in logs_data.get("logs", [])]

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
            request,
            "dashboard/health/index.html",
            {
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
            request,
            "dashboard/health/projects-partial.html",
            {
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
    "wordpress_specialist": "WordPress specialist management — plugins, themes, users, options, cron, maintenance, page editing, site config + layout, db inspection, bulk fan-out. Companion-backed (Airano MCP Bridge v2.18.0+); no Docker socket required.",
    "gitea": "Gitea self-hosted Git management (repos, issues, PRs)",
    "n8n": "n8n workflow automation management",
    "supabase": "Supabase self-hosted backend (database, auth, storage)",
    "openpanel": "OpenPanel analytics and event tracking",
    "appwrite": "Appwrite backend services (databases, users, functions)",
    "directus": "Directus headless CMS management",
    "coolify": "Coolify deployment platform — apps, deployments, servers, databases.",
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

    # Get managed settings (4C.3)
    from core.settings import get_all_managed_settings

    managed_settings = await get_all_managed_settings()

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
        request,
        "dashboard/settings/index.html",
        {
            "lang": lang,
            "t": t,
            "session": session,  # Original session for RBAC sidebar
            "session_display": session_display,  # Formatted for display
            "config": config,
            "plugins": plugins,
            "about": about,
            "managed_settings": managed_settings,
            "current_page": "settings",
        },
    )


async def api_get_settings(request: Request) -> Response:
    """GET /api/dashboard/settings — Return all managed settings.

    Track G companion to the legacy ``/dashboard/settings`` HTML page.
    Admin-only (same as the POST handler) so non-admins never see hub-wide
    config such as ENABLED_PLUGINS.
    """
    session, redirect = _require_admin_session(request)
    if redirect:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    del session

    from core.settings import get_all_managed_settings

    settings = await get_all_managed_settings()
    return JSONResponse({"settings": settings})


async def api_save_setting(request: Request) -> Response:
    """POST /api/dashboard/settings — Save a managed setting."""
    session, redirect = _require_admin_session(request)
    if redirect:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    key = body.get("key", "")
    value = body.get("value", "")
    action = body.get("action", "save")  # "save" or "reset"

    from core.settings import SETTING_DEFAULTS, delete_setting_value, save_setting

    if key not in SETTING_DEFAULTS:
        return JSONResponse({"error": f"Unknown setting: {key}"}, status_code=400)

    if action == "reset":
        await delete_setting_value(key)
        return JSONResponse({"message": f"Setting '{key}' reset to default"})

    if not value.strip():
        return JSONResponse({"error": "Value cannot be empty"}, status_code=400)
    if key in {"MAX_SITES_PER_USER", "USER_RATE_LIMIT_PER_MIN", "USER_RATE_LIMIT_PER_HR"}:
        try:
            parsed_value = int(str(value).strip())
        except ValueError:
            return JSONResponse({"error": f"{key} must be a positive integer"}, status_code=400)
        if parsed_value <= 0:
            return JSONResponse({"error": f"{key} must be a positive integer"}, status_code=400)

    await save_setting(key, value.strip())
    return JSONResponse({"message": f"Setting '{key}' saved"})


async def api_reset_settings(request: Request) -> Response:
    """POST /api/dashboard/settings/reset — Reset all managed DB overrides."""
    session, redirect = _require_admin_session(request)
    if redirect:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    del session

    from core.settings import SETTING_DEFAULTS, delete_setting_value

    deleted = 0
    for key in SETTING_DEFAULTS:
        if await delete_setting_value(key):
            deleted += 1

    return JSONResponse({"ok": True, "deleted": deleted})


# =============================================================================
# E.2: OAuth Social Login Routes
# =============================================================================


async def auth_login_page(request: Request) -> Response:
    """Render the OAuth login page with GitHub + Google buttons."""
    auth = get_dashboard_auth()

    # Check if already logged in (admin or user session)
    session = auth.get_session_from_request(request) or auth.get_user_session_from_request(request)
    if session:
        return RedirectResponse(url="/dashboard/overview", status_code=303)

    # Get language — default to English for auth page, only override via ?lang=
    query_lang = request.query_params.get("lang")
    lang = detect_language(None, query_lang)
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
        request,
        "dashboard/auth-login.html",
        {
            "lang": lang,
            "t": t,
            "error": error,
            "providers": providers,
            "version": _get_project_version(),
            "master_login_disabled": os.environ.get("DISABLE_MASTER_KEY_LOGIN", "false").lower()
            == "true",
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
            url="/dashboard/login?error=provider_unavailable",
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
        return RedirectResponse(url="/dashboard/login?error=oauth_denied", status_code=303)

    if not code or not state:
        return RedirectResponse(
            url="/dashboard/login?error=missing_params",
            status_code=303,
        )

    try:
        from core.user_auth import get_user_auth

        user_auth = get_user_auth()

        # Validate state (CSRF protection)
        if not user_auth.validate_state(state):
            logger.warning("OAuth callback: invalid state for %s", provider)
            return RedirectResponse(
                url="/dashboard/login?error=invalid_state",
                status_code=303,
            )

        # Exchange code for user info
        user_info = await user_auth.exchange_code(provider, code)

        if not user_info.get("email"):
            return RedirectResponse(
                url="/dashboard/login?error=no_email",
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
                        url="/dashboard/login?error=rate_limit",
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

        # Determine effective role: check ADMIN_EMAILS env var
        from core.admin_utils import is_admin_email

        db_role = user.get("role", "user")
        effective_role = "admin" if is_admin_email(user.get("email")) else db_role

        # Create session
        token = user_auth.create_user_session(
            user_id=user["id"],
            email=user["email"],
            name=user.get("name"),
            role=effective_role,
        )

        if effective_role == "admin":
            logger.info("Admin role granted to %s via ADMIN_EMAILS", user["email"])

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
            url="/dashboard/login?error=exchange_failed",
            status_code=303,
        )
    except Exception as e:
        logger.error(
            "OAuth callback unexpected error for %s: %s",
            provider,
            e,
        )
        return RedirectResponse(
            url="/dashboard/login?error=server_error",
            status_code=303,
        )


async def auth_logout(request: Request) -> Response:
    """Log out the current user (both admin and OAuth sessions)."""
    auth = get_dashboard_auth()
    response = RedirectResponse(url="/dashboard/login", status_code=303)
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
            return RedirectResponse(url="/dashboard/login", status_code=303)
        return RedirectResponse(url="/dashboard/overview", status_code=303)

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
        request,
        "dashboard/profile.html",
        {
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
        return None, RedirectResponse(url="/dashboard/login", status_code=303)
    return user_session, None


def _require_admin_session(request: Request):
    """Get admin session or redirect to dashboard. Helper for admin-only routes."""
    auth = get_dashboard_auth()
    # Check DashboardSession (master key / API key)
    session = auth.get_session_from_request(request)
    if session and is_admin_session(session):
        return session, None
    # Check OAuth user session (admin role)
    user_session = auth.get_user_session_from_request(request)
    if user_session and is_admin_session(user_session):
        return user_session, None
    # Not admin — redirect to dashboard home
    return None, RedirectResponse(url="/dashboard/overview", status_code=303)


async def dashboard_sites_list(request: Request) -> Response:
    """Render the My Sites page."""
    auth = get_dashboard_auth()
    # Allow both OAuth users and admin
    admin_session = auth.get_session_from_request(request)
    user_session = auth.get_user_session_from_request(request)
    if not user_session and not admin_session:
        return RedirectResponse(url="/dashboard/login", status_code=303)
    # For admin, we don't have user sites — redirect to projects
    if admin_session and not user_session:
        return RedirectResponse(url="/dashboard/overview", status_code=303)

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
        request,
        "dashboard/sites/list.html",
        {
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

    from core.site_api import (
        PLUGIN_CREDENTIAL_FIELDS,
        PLUGIN_DISPLAY_NAMES,
        get_user_credential_fields,
        get_user_plugin_names,
    )

    # Admin sees all plugins; regular users get filtered list
    if is_admin_session(user_session):
        plugin_fields = dict(PLUGIN_CREDENTIAL_FIELDS)
        plugin_names = dict(PLUGIN_DISPLAY_NAMES)
    else:
        plugin_fields = get_user_credential_fields()
        plugin_names = get_user_plugin_names()

    # Pre-select plugin type from query param (e.g., from service page)
    preselect_plugin = request.query_params.get("plugin_type", "")

    return templates.TemplateResponse(
        request,
        "dashboard/sites/add.html",
        {
            "lang": lang,
            "t": t,
            "session": user_session,
            "plugin_fields": plugin_fields,
            "plugin_fields_json": json.dumps(plugin_fields),
            "plugin_names": plugin_names,
            "current_page": "my_sites",
            "preselect_plugin": preselect_plugin,
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
        request,
        "dashboard/connect.html",
        {
            "lang": lang,
            "t": t,
            "session": user_session,
            "sites": sites,
            "api_keys": keys,
            "clients": get_supported_clients(),
            "current_page": "connect",
            "new_key": new_key,
            "public_url": resolve_public_base_url(request),
        },
    )


# ======================================================================
# Site View Route (F.7b session 2)
# ======================================================================


async def dashboard_sites_view(request: Request) -> Response:
    """GET /dashboard/sites/{id} — Unified site management page (F.7c).

    Combines connection settings, tool access, and connect/config snippets
    into a single page with 3 sections.
    """
    user_session, redirect = _require_user_session(request)
    if redirect:
        return redirect

    site_id = request.path_params.get("id", "")

    import json

    from core.config_snippets import get_supported_clients
    from core.site_api import (
        SITE_PROVIDERS,
        get_user_credential_fields,
        get_user_plugin_names,
        get_user_site,
        list_site_providers_set,
        site_supports_provider_keys,
    )
    from core.tool_access import get_scope_presets_for_plugin

    site = await get_user_site(site_id, user_session["user_id"])
    if site is None:
        # Bounce SPA visitors back into the SPA shell; legacy visitors stay on
        # the legacy list page.
        if request.query_params.get("from") in {"dashboard", "dashboard-v2"}:
            return RedirectResponse("/dashboard/sites?error=site_not_found", status_code=302)
        return RedirectResponse("/dashboard-legacy/sites?error=site_not_found", status_code=302)

    accept_language = request.headers.get("accept-language")
    query_lang = request.query_params.get("lang")
    lang = detect_language(accept_language, query_lang)
    t = get_translations(lang)

    public_url = resolve_public_base_url(request)
    mcp_url = f"{public_url}/u/{user_session['user_id']}/{site['alias']}/mcp"

    # F.19.1 (2026-05-01) — admin OAuth users need to see credential
    # fields for admin-only plugins (wordpress_specialist) otherwise
    # the manage page renders an empty form on revisit.
    is_admin_user = is_admin_session(user_session)
    plugin_fields = get_user_credential_fields(is_admin=is_admin_user)
    plugin_names = get_user_plugin_names(is_admin=is_admin_user)
    scope_presets = get_scope_presets_for_plugin(site["plugin_type"])

    # F.5a.9.x: per-site AI provider keys — only surface the section on
    # WordPress/WooCommerce sites (the only consumers of
    # wordpress_generate_and_upload_image).
    provider_keys_supported = site_supports_provider_keys(site["plugin_type"])
    provider_key_rows: list[dict[str, Any]] = []
    if provider_keys_supported:
        configured = await list_site_providers_set(site_id)
        # F.X.fix-pass3: pull each row's default_model so the UI can
        # render a "Set default" pill that's pre-highlighted on the
        # current selection. One query, all rows.
        default_models: dict[str, str | None] = {}
        try:
            from core.database import get_database

            db = get_database()
            rows = await db.list_site_provider_keys(site_id)
            for r in rows:
                default_models[r["provider"]] = r.get("default_model")
        except Exception as exc:  # noqa: BLE001
            logger.debug("default_model lookup skipped site=%s: %s", site_id, exc)
        _provider_labels = {
            "openai": "OpenAI",
            "stability": "Stability AI",
            "replicate": "Replicate",
            "openrouter": "OpenRouter (Gemini / multi-model)",
        }
        for provider in SITE_PROVIDERS:
            provider_key_rows.append(
                {
                    "provider": provider,
                    "label": _provider_labels.get(provider, provider.title()),
                    "status": "set" if provider in configured else "unset",
                    "default_model": default_models.get(provider),
                }
            )

    # F.20 prep: companion-plugin download hint, shown on WP/WC site
    # pages only. See dashboard_service_page for the matching hint on
    # the services catalogue.
    companion_download_url = None
    if site["plugin_type"] in {"wordpress", "woocommerce"}:
        companion_download_url = (
            "https://github.com/airano-ir/mcphub/raw/main/" "wordpress-plugin/airano-mcp-bridge.zip"
        )

    # F.7e: run the capability probe server-side so the manage page can
    # render the badge on first paint without a second round-trip. Any
    # failure falls through to "probe unavailable" so the page always
    # loads. The frontend Re-check button hits the same endpoint with
    # force=1 to bypass the 10-min cache.
    capability_probe = None
    try:
        from core.capability_probe import evaluate_tier_fit, probe_site_capabilities

        probe_payload = await probe_site_capabilities(
            site_id=site_id, user_id=user_session["user_id"]
        )
        fit = evaluate_tier_fit(
            plugin_type=site["plugin_type"],
            tier=site.get("tool_scope"),
            probe_payload=probe_payload,
        )
        capability_probe = {**probe_payload, "fit": fit}
    except Exception as exc:  # noqa: BLE001
        logger.warning("capability probe render failed for %s: %s", site_id, exc)
        capability_probe = {
            "probe_available": False,
            "granted": [],
            "source": "unavailable",
            "reason": f"render_error: {exc}",
            "fit": {"status": "probe_unavailable", "required": [], "missing": []},
        }

    # F.X.fix-pass5 — surface which credential fields are *currently
    # stored* (not the values themselves) so the form can show a
    # "✓ Stored" badge and require an explicit "Clear" action to
    # remove an existing value, instead of silently wiping it on a
    # blank-input save.
    cred_states: dict[str, bool] = {}
    try:
        from core.encryption import get_credential_encryption

        encryptor = get_credential_encryption()
        decrypted = encryptor.decrypt_credentials(site["credentials"], site_id)
        for field in plugin_fields.get(site["plugin_type"], []):
            value = decrypted.get(field["name"])
            cred_states[field["name"]] = bool(value and str(value).strip())
    except Exception as exc:  # noqa: BLE001
        logger.debug("cred_states lookup failed for site %s: %s", site_id, exc)
        cred_states = {}

    return templates.TemplateResponse(
        request,
        "dashboard/sites/manage.html",
        {
            "lang": lang,
            "t": t,
            "session": user_session,
            "site": site,
            "plugin_names": plugin_names,
            "plugin_fields": plugin_fields,
            "plugin_fields_json": json.dumps(plugin_fields),
            "scope_presets": scope_presets,
            "scope_presets_json": json.dumps(scope_presets),
            "mcp_url": mcp_url,
            "clients": get_supported_clients(),
            "current_page": "my_sites",
            "provider_keys_supported": provider_keys_supported,
            "provider_key_rows": provider_key_rows,
            "companion_download_url": companion_download_url,
            "capability_probe": capability_probe,
            "cred_states": cred_states,
            "cred_states_json": json.dumps(cred_states),
        },
    )


# ======================================================================
# Unified Keys Route (F.7b session 2)
# ======================================================================


async def dashboard_keys_unified(request: Request) -> Response:
    """GET /dashboard/keys — Unified API keys page (user or admin view)."""
    accept_language = request.headers.get("accept-language")
    query_lang = request.query_params.get("lang")
    lang = detect_language(accept_language, query_lang)
    t = get_translations(lang)

    auth = get_dashboard_auth()
    admin_session = auth.get_session_from_request(request)
    user_session = auth.get_user_session_from_request(request)

    if admin_session and is_admin_session(admin_session):
        # Admin view — reuse existing admin keys logic
        project_filter = request.query_params.get("project", "")
        status_filter = request.query_params.get("status", "active")
        search = request.query_params.get("search", "")
        page = int(request.query_params.get("page", 1))

        keys_data = await get_all_api_keys(
            project_id=project_filter if project_filter else None,
            status=status_filter,
            search=search if search else None,
            page=page,
        )

        from core.site_manager import get_site_manager

        site_manager = get_site_manager()
        available_projects = site_manager.list_all_sites()

        return templates.TemplateResponse(
            request,
            "dashboard/keys/list.html",
            {
                "lang": lang,
                "t": t,
                "session": admin_session,
                "is_admin": True,
                "api_keys": keys_data["api_keys"],
                "total_count": keys_data["total_count"],
                "total_pages": keys_data["total_pages"],
                "page_number": keys_data["current_page"],
                "per_page": keys_data["per_page"],
                "available_projects": available_projects,
                "selected_project": project_filter,
                "selected_status": status_filter,
                "search_query": search,
                "current_page": "keys",
            },
        )

    if user_session:
        # User view — personal keys + config snippets
        from core.config_snippets import get_supported_clients
        from core.site_api import get_user_sites
        from core.user_keys import get_user_key_manager

        user_keys = []
        try:
            key_mgr = get_user_key_manager()
            user_keys = await key_mgr.list_keys(user_session["user_id"])
        except RuntimeError:
            pass

        sites = await get_user_sites(user_session["user_id"])

        return templates.TemplateResponse(
            request,
            "dashboard/keys/list.html",
            {
                "lang": lang,
                "t": t,
                "session": user_session,
                "is_admin": False,
                "user_keys": user_keys,
                "sites": sites,
                "clients": get_supported_clients(),
                "current_page": "keys",
            },
        )

    return RedirectResponse(url="/dashboard/login", status_code=303)


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

    from core.settings import get_cached_max_sites
    from core.site_api import get_user_sites

    sites = await get_user_sites(user_session["user_id"])
    limit = get_cached_max_sites()
    return JSONResponse(
        {
            "sites": sites,
            "limit": limit,
            "remaining": max(0, limit - len(sites)),
        }
    )


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
        return JSONResponse(
            {
                "ok": ok,
                "message": msg,
                "status": "active" if ok else "error",
                "last_tested_at": datetime.now(UTC).isoformat(),
            }
        )
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=404)
    except Exception as e:
        logger.error("Test connection failed: %s", e, exc_info=True)
        return JSONResponse({"error": "Internal error"}, status_code=500)


async def dashboard_sites_edit(request: Request) -> Response:
    """GET /dashboard/sites/{id}/edit — Redirect to unified site page (F.7c).

    Preserves `lang` and `from` query params so the SPA-origin breadcrumb
    can return the user to /dashboard/sites instead of the legacy list.
    """
    site_id = request.path_params.get("id", "")
    query_lang = request.query_params.get("lang")
    came_from = request.query_params.get("from")
    url = f"/dashboard-legacy/sites/{site_id}"
    extras: list[str] = []
    if query_lang:
        extras.append(f"lang={query_lang}")
    if came_from:
        extras.append(f"from={came_from}")
    if extras:
        url += "?" + "&".join(extras)
    # 302, not 301: browsers aggressively cache 301s by exact URL including
    # query — and we want changes to /edit handling to take effect on reload.
    return RedirectResponse(url, status_code=302)


async def api_update_site(request: Request) -> Response:
    """PATCH /api/sites/{id} — Update site URL and credentials."""
    user_session, redirect = _require_user_session(request)
    if redirect:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    site_id = request.path_params.get("id", "")

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    from core.site_api import update_user_site

    try:
        site = await update_user_site(
            site_id=site_id,
            user_id=user_session["user_id"],
            url=body.get("url", "").strip().rstrip("/"),
            credentials=body.get("credentials", {}),
        )
        return JSONResponse({"site": site, "message": "Site updated"})
    except ValueError as e:
        return JSONResponse({"error": str(e)}, status_code=400)
    except RuntimeError as e:
        logger.error("Site update failed (runtime): %s", e)
        return JSONResponse(
            {"error": "Site storage is not configured. Contact the administrator."},
            status_code=503,
        )
    except Exception as e:
        logger.error("Failed to update site: %s", e, exc_info=True)
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

        # Validate site_id if provided (must belong to user)
        site_id = body.get("site_id")
        if site_id:
            from core.database import get_database

            db = get_database()
            site = await db.get_site(site_id, user_session["user_id"])
            if site is None:
                return JSONResponse({"error": "Site not found"}, status_code=404)

        # F.7c + F.19.2.2: All user keys get full access — tool visibility
        # is controlled per-site via ``tool_scope`` and per-tool toggles.
        # Enumerate every tier explicitly (read / editor / settings /
        # install / write / admin) so the key string mirrors the dashboard
        # Tool Access dropdown 1:1 and stays robust if the universal tier
        # closure changes in a future phase. The narrowing is the
        # intersection with site_scope at request time.
        result = await key_mgr.create_key(
            user_id=user_session["user_id"],
            name=body.get("name", "Default"),
            scopes="read editor settings install write admin",
            expires_in_days=body.get("expires_in_days"),
            site_id=site_id,
        )
        return JSONResponse(
            {
                "id": result["key_id"],
                "key": result["key"],
                "name": result["name"],
                "prefix": result["key"][4:12],
                "scope": result["scopes"],
                "scopes": result["scopes"],
                "created_at": result["created_at"],
                "expires_at": result["expires_at"],
                "site_id": result.get("site_id"),
            }
        )
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


# ----------------------------------------------------------------------
# F.7b: per-site tool visibility management
# ----------------------------------------------------------------------


_VALID_TOOL_SCOPES = {
    "read",
    "read:sensitive",
    "deploy",
    "editor",  # F.19.5 — page editing tier on wordpress_specialist
    "settings",  # F.19.6 — options / cron / identity / permalinks
    "install",  # F.19.2 — plugin / theme install from wp.org slug
    "write",
    "admin",
    "custom",
}


async def _require_owned_site(request: Request) -> tuple[dict | None, Response | None]:
    """Resolve ``{site_id}`` path param → site row owned by the current user.

    Returns ``(site, None)`` on success, or ``(None, error_response)``.
    """
    user_session, redirect = _require_user_session(request)
    if redirect:
        return None, JSONResponse({"error": "Unauthorized"}, status_code=401)

    site_id = request.path_params.get("site_id", "")
    if not site_id:
        return None, JSONResponse({"error": "Missing site_id"}, status_code=400)

    from core.database import get_database

    try:
        db = get_database()
    except RuntimeError:
        return None, JSONResponse({"error": "Database unavailable"}, status_code=503)

    site = await db.get_site(site_id, user_session["user_id"])
    if site is None:
        return None, JSONResponse({"error": "Site not found"}, status_code=404)
    return site, None


async def api_list_site_tools(request: Request) -> Response:
    """GET /api/sites/{site_id}/tools — list tools for a site with toggle state."""
    site, err = await _require_owned_site(request)
    if err:
        return err
    assert site is not None

    from core.site_api import list_site_providers_set
    from core.tool_access import get_scope_presets_for_plugin, get_tool_access_manager

    access = get_tool_access_manager()
    tools = await access.list_tools_for_site(site["id"], site["plugin_type"])
    scope_presets = get_scope_presets_for_plugin(site["plugin_type"])
    # F.X.fix #8: expose the site's configured AI-provider set so the
    # Tool Access template can render "Configure key for X" CTAs
    # without issuing a second /api/sites/{id}/provider-keys call.
    try:
        configured_providers = sorted(await list_site_providers_set(site["id"]))
    except Exception:  # noqa: BLE001
        configured_providers = []
    return JSONResponse(
        {
            "site_id": site["id"],
            "plugin_type": site["plugin_type"],
            "tool_scope": site.get("tool_scope", "admin"),
            "scope_presets": scope_presets,
            "configured_providers": configured_providers,
            "tools": tools,
        }
    )


async def api_patch_site_tool(request: Request) -> Response:
    """PATCH /api/sites/{site_id}/tools/{tool_name} — toggle a single tool."""
    site, err = await _require_owned_site(request)
    if err:
        return err
    assert site is not None

    tool_name = request.path_params.get("tool_name", "")
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    if "enabled" not in body or not isinstance(body["enabled"], bool):
        return JSONResponse({"error": "Missing boolean 'enabled' field"}, status_code=400)

    from core.tool_access import get_tool_access_manager
    from core.tool_registry import get_tool_registry

    tool_def = get_tool_registry().get_by_name(tool_name)
    if tool_def is None:
        return JSONResponse({"error": f"Unknown tool '{tool_name}'"}, status_code=404)
    if tool_def.plugin_type != site["plugin_type"]:
        return JSONResponse(
            {"error": f"Tool '{tool_name}' does not belong to this site's plugin"},
            status_code=400,
        )

    access = get_tool_access_manager()
    try:
        await access.toggle_tool(
            site["id"],
            tool_name,
            bool(body["enabled"]),
            body.get("reason"),
        )
    except RuntimeError as exc:
        return JSONResponse({"error": str(exc)}, status_code=503)

    return JSONResponse({"ok": True, "tool_name": tool_name, "enabled": body["enabled"]})


async def api_bulk_toggle_site_tools(request: Request) -> Response:
    """POST /api/sites/{site_id}/tools/bulk-toggle — toggle a category set."""
    site, err = await _require_owned_site(request)
    if err:
        return err
    assert site is not None

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    scope = body.get("scope")
    enabled = body.get("enabled")
    if not isinstance(scope, str) or not isinstance(enabled, bool):
        return JSONResponse(
            {"error": "Body must contain string 'scope' and bool 'enabled'"},
            status_code=400,
        )

    from core.tool_access import get_tool_access_manager

    access = get_tool_access_manager()
    try:
        affected = await access.bulk_toggle_by_scope(
            site["id"], scope, enabled, plugin_type=site["plugin_type"]
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)
    except RuntimeError as exc:
        return JSONResponse({"error": str(exc)}, status_code=503)

    return JSONResponse({"ok": True, "affected": affected})


async def api_set_site_tool_scope(request: Request) -> Response:
    """PATCH /api/sites/{site_id}/tool-scope — update the site's scope preset."""
    site, err = await _require_owned_site(request)
    if err:
        return err
    assert site is not None

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    scope = body.get("scope")
    if not isinstance(scope, str) or scope not in _VALID_TOOL_SCOPES:
        return JSONResponse(
            {
                "error": (
                    "Body must contain 'scope' with one of: "
                    + ", ".join(sorted(_VALID_TOOL_SCOPES))
                )
            },
            status_code=400,
        )

    from core.database import get_database

    db = get_database()
    await db.set_site_tool_scope(site["id"], scope)
    return JSONResponse({"ok": True, "site_id": site["id"], "tool_scope": scope})


async def api_scope_presets(request: Request) -> Response:
    """GET /api/scope-presets — static scope → categories mapping."""
    user_session, redirect = _require_user_session(request)
    if redirect:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    del user_session

    from core.tool_access import SCOPE_TO_CATEGORIES

    return JSONResponse({"presets": {k: sorted(v) for k, v in SCOPE_TO_CATEGORIES.items()}})


async def api_get_config(request: Request) -> Response:
    """GET /api/config/{alias} — Get config snippets for a site."""
    user_session, redirect = _require_user_session(request)
    if redirect:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    alias = request.path_params.get("alias", "")
    client_type = request.query_params.get("client", "claude_desktop")

    from core.config_snippets import generate_config

    base_url = resolve_public_base_url(request)

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


async def dashboard_user_oauth_clients_list(request: Request) -> Response:
    """GET /dashboard/connect/oauth-clients — Redirect to unified OAuth clients page."""
    return RedirectResponse(url="/dashboard-legacy/oauth-clients", status_code=303)


async def dashboard_user_oauth_clients_create(request: Request) -> Response:
    """POST /api/dashboard/user-oauth-clients/create — Forwards to unified create endpoint."""
    return await dashboard_oauth_clients_create(request)


async def dashboard_user_oauth_clients_delete(request: Request) -> Response:
    """DELETE /api/dashboard/user-oauth-clients/{client_id} — Forwards to unified delete endpoint."""
    return await dashboard_oauth_clients_delete(request)


async def get_service_page_data(plugin_type: str) -> dict | None:
    """Get data for a plugin service page."""
    from plugins import registry as plugin_registry

    if not plugin_registry.is_registered(plugin_type):
        return None

    display_name = get_plugin_display_name(plugin_type)

    # Get tools from registry
    tools = []
    try:
        from core.tool_registry import get_tool_registry

        tool_registry = get_tool_registry()
        tool_defs = tool_registry.get_by_plugin_type(plugin_type)
        for td in tool_defs:
            tools.append(
                {
                    "name": td.name,
                    "description": td.description,
                    "scope": td.required_scope,
                }
            )
    except Exception:
        pass

    # Fallback: get from plugin specs directly if registry had no tools
    if not tools:
        try:
            plugin_class = plugin_registry._plugin_classes[plugin_type]
            specs = plugin_class.get_tool_specifications()
            for spec in specs:
                tools.append(
                    {
                        "name": spec.get("name", ""),
                        "description": spec.get("description", ""),
                        "scope": spec.get("scope", "read"),
                    }
                )
        except Exception:
            pass

    # Sort tools by scope then name. Order mirrors UNIVERSAL_SCOPE_TIERS
    # so wordpress_specialist tools display read → editor → settings →
    # install → write → admin in the connect-page tools table.
    scope_order = {
        "read": 0,
        "editor": 1,
        "settings": 2,
        "install": 3,
        "write": 4,
        "admin": 5,
    }
    tools.sort(key=lambda t: (scope_order.get(t["scope"], 9), t["name"]))

    # Get credential fields
    credential_fields = []
    try:
        from core.site_api import PLUGIN_CREDENTIAL_FIELDS

        credential_fields = PLUGIN_CREDENTIAL_FIELDS.get(plugin_type, [])
    except Exception:
        pass

    from core.plugin_visibility import is_plugin_public

    # Per-plugin descriptions and notes
    service_descriptions = {
        "openpanel": {
            "en": (
                "OpenPanel product analytics management. "
                "Supports event tracking, data export, analytics reports, "
                "and project/client management via public REST APIs. "
                "Works with both self-hosted and cloud (openpanel.dev) instances."
            ),
            "fa": (
                "مدیریت آنالیتیکس محصول OpenPanel. "
                "پشتیبانی از ردیابی رویداد، خروجی داده، گزارش‌های آنالیتیکس، "
                "و مدیریت پروژه/کلاینت از طریق API‌های عمومی REST. "
                "هم نسخه خودمیزبان و هم نسخه cloud (openpanel.dev) پشتیبانی می‌شود."
            ),
            "notes_en": [
                "<strong>Site URL must be the API URL</strong>, not the dashboard URL. "
                "Cloud: <code>https://api.openpanel.dev</code> — "
                "Self-hosted: your API service URL (e.g., <code>https://analytics.example.com</code>).",
                "Client must have <strong>root</strong> mode for full access (tracking + export + manage). "
                "Use <strong>read</strong> mode for analytics only, or <strong>write</strong> mode for tracking only.",
                "If you have WordPress, install the <a href='/static/plugins/openpanel-self-hosted.zip' "
                "class='text-primary-400 hover:underline'>OpenPanel WordPress plugin</a> "
                "to automatically send analytics data to your OpenPanel instance.",
            ],
            "notes_fa": [
                "<strong>آدرس سایت باید آدرس API باشد</strong>، نه داشبورد. "
                "نسخه Cloud: <code>https://api.openpanel.dev</code> — "
                "خودمیزبان: آدرس سرویس API شما (مثلاً <code>https://analytics.example.com</code>).",
                "برای دسترسی کامل، کلاینت باید حالت <strong>root</strong> داشته باشد. "
                "از حالت <strong>read</strong> برای آنالیتیکس و <strong>write</strong> برای ردیابی استفاده کنید.",
                "اگر وردپرس دارید، افزونه <a href='/static/plugins/openpanel-self-hosted.zip' "
                "class='text-primary-400 hover:underline'>OpenPanel WordPress</a> "
                "را نصب کنید تا داده‌های آنالیتیکس به‌صورت خودکار به OpenPanel ارسال شود.",
            ],
        },
    }

    desc_data = service_descriptions.get(plugin_type, {})

    return {
        "plugin_type": plugin_type,
        "display_name": display_name,
        "tools": tools,
        "tools_count": len(tools),
        "credential_fields": credential_fields,
        "is_public": is_plugin_public(plugin_type),
        "description": desc_data,
    }


async def dashboard_services_list(request: Request) -> Response:
    """GET /dashboard/services — List available MCP services."""
    auth = get_dashboard_auth()
    redirect = auth.require_auth(request)
    if redirect:
        return redirect

    session = auth.get_session_from_request(request) or auth.get_user_session_from_request(request)
    admin = is_admin_session(session)
    display_info = get_session_display_info(session)

    accept_language = request.headers.get("accept-language")
    query_lang = request.query_params.get("lang")
    lang = detect_language(accept_language, query_lang)
    t = get_translations(lang)

    # Get plugin list based on user role
    if admin:
        from plugins import registry as plugin_registry

        plugin_types = plugin_registry.get_registered_types()
    else:
        from core.plugin_visibility import get_public_plugin_types

        plugin_types = sorted(get_public_plugin_types())

    services = []
    for pt in plugin_types:
        data = await get_service_page_data(pt)
        if data:
            services.append(data)

    return templates.TemplateResponse(
        request,
        "dashboard/services_list.html",
        {
            "lang": lang,
            "t": t,
            "session": session,
            "is_admin": admin,
            "display_info": display_info,
            "current_page": "services",
            "services": services,
        },
    )


async def dashboard_service_page(request: Request) -> Response:
    """GET /dashboard/services/{plugin_type} — Show plugin info page."""
    auth = get_dashboard_auth()
    redirect = auth.require_auth(request)
    if redirect:
        return redirect

    session = auth.get_session_from_request(request) or auth.get_user_session_from_request(request)
    admin = is_admin_session(session)
    display_info = get_session_display_info(session)

    plugin_type = request.path_params.get("plugin_type", "")

    # Non-admin users can only see public plugins
    if not admin:
        from core.plugin_visibility import is_plugin_public

        if not is_plugin_public(plugin_type):
            accept_language = request.headers.get("accept-language")
            query_lang = request.query_params.get("lang")
            lang = detect_language(accept_language, query_lang)
            return templates.TemplateResponse(
                request,
                "dashboard/404.html",
                {
                    "lang": lang,
                    "t": get_translations(lang),
                    "session": session,
                    "is_admin": admin,
                    "display_info": display_info,
                    "current_page": "services",
                },
                status_code=404,
            )

    data = await get_service_page_data(plugin_type)
    if data is None:
        accept_language = request.headers.get("accept-language")
        query_lang = request.query_params.get("lang")
        lang = detect_language(accept_language, query_lang)
        return templates.TemplateResponse(
            request,
            "dashboard/404.html",
            {
                "lang": lang,
                "t": get_translations(lang),
                "session": session,
                "is_admin": admin,
                "display_info": display_info,
                "current_page": "services",
            },
            status_code=404,
        )

    accept_language = request.headers.get("accept-language")
    query_lang = request.query_params.get("lang")
    lang = detect_language(accept_language, query_lang)
    t = get_translations(lang)

    # F.20 prep: dashboard UX hint — surface the companion-plugin download
    # link on the WP / WC service pages. The link switches from the GitHub
    # raw-download URL to wp.org once the plugin ships (see F.20 scope).
    companion_download_url = None
    if plugin_type in {"wordpress", "woocommerce"}:
        companion_download_url = (
            "https://github.com/airano-ir/mcphub/raw/main/" "wordpress-plugin/airano-mcp-bridge.zip"
        )

    return templates.TemplateResponse(
        request,
        "dashboard/service.html",
        {
            "lang": lang,
            "t": t,
            "session": session,
            "is_admin": admin,
            "display_info": display_info,
            "current_page": "services",
            "service": data,
            "companion_download_url": companion_download_url,
        },
    )


# ======================================================================
# F.18.8 — Provider Keys Dashboard UI (REMOVED in F.5a.9.x)
# ======================================================================
#
# Per-user AI provider keys and the /dashboard/provider-keys page have
# been replaced by per-site keys defined in each WordPress / WooCommerce
# site's Connection Settings. The site-scoped API is the F.5a.9.x block
# below. The user_provider_keys table is dropped in schema migration v12.
#
# Deleted helpers / handlers:
#   _PROVIDER_LABELS, _build_provider_rows,
#   dashboard_provider_keys_page,
#   api_user_provider_keys_set, api_user_provider_keys_delete.


# ======================================================================
# F.5a.9.x — Per-site AI provider key endpoints
# ======================================================================


async def api_site_provider_keys_list(request: Request) -> Response:
    """GET /api/sites/{id}/provider-keys — list providers with a key stored.

    Returns ``{"providers": ["openai", ...], "default_models": {...}}``.
    Does not leak ciphertext or plaintext.
    """
    user_session, redirect = _require_user_session(request)
    if redirect or user_session is None:
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)

    site_id = (request.path_params.get("id") or "").strip()
    from core.site_api import get_user_site, list_site_providers_set, site_supports_provider_keys

    site = await get_user_site(site_id, user_session["user_id"])
    if site is None:
        return JSONResponse({"ok": False, "error": "site_not_found"}, status_code=404)
    if not site_supports_provider_keys(site["plugin_type"]):
        return JSONResponse({"ok": False, "error": "plugin_unsupported"}, status_code=400)

    providers = sorted(await list_site_providers_set(site_id))
    default_models: dict[str, str | None] = {}
    try:
        from core.database import get_database

        db = get_database()
        for row in await db.list_site_provider_keys(site_id):
            default_models[str(row.get("provider"))] = row.get("default_model")
    except Exception as exc:  # noqa: BLE001
        logger.debug("site provider default-model list skipped site=%s: %s", site_id, exc)
    return JSONResponse({"ok": True, "providers": providers, "default_models": default_models})


async def api_site_provider_keys_set(request: Request) -> Response:
    """POST /api/sites/{id}/provider-keys/{provider} — upsert a per-site key.

    Body: ``{"api_key": "..."}``. Enforces site ownership, plugin-type gate,
    and provider allow-list (site_api.set_site_provider_key).
    """
    user_session, redirect = _require_user_session(request)
    if redirect or user_session is None:
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)

    site_id = (request.path_params.get("id") or "").strip()
    provider = (request.path_params.get("provider") or "").strip().lower()

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "invalid_json"}, status_code=400)
    if not isinstance(body, dict):
        return JSONResponse({"ok": False, "error": "invalid_body"}, status_code=400)

    api_key = str(body.get("api_key") or "").strip()
    if len(api_key) < 8:
        return JSONResponse(
            {
                "ok": False,
                "error": "key_too_short",
                "message": "api_key must be at least 8 characters",
            },
            status_code=400,
        )

    from core.site_api import set_site_provider_key

    try:
        await set_site_provider_key(site_id, user_session["user_id"], provider, api_key)
    except ValueError as exc:
        return JSONResponse(
            {"ok": False, "error": "invalid_request", "message": str(exc)},
            status_code=400,
        )
    except Exception as exc:
        logger.error(
            "site_provider_keys set failed user=%s site=%s provider=%s: %s",
            user_session["user_id"],
            site_id,
            provider,
            exc,
        )
        return JSONResponse(
            {"ok": False, "error": "storage_failed", "message": str(exc)},
            status_code=500,
        )

    return JSONResponse(
        {
            "ok": True,
            "site_id": site_id,
            "provider": provider,
            "secret_last4": api_key[-4:],
        }
    )


async def api_site_provider_keys_delete(request: Request) -> Response:
    """DELETE /api/sites/{id}/provider-keys/{provider} — remove a per-site key."""
    user_session, redirect = _require_user_session(request)
    if redirect or user_session is None:
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)

    site_id = (request.path_params.get("id") or "").strip()
    provider = (request.path_params.get("provider") or "").strip().lower()

    from core.site_api import delete_site_provider_key

    try:
        deleted = await delete_site_provider_key(site_id, user_session["user_id"], provider)
    except Exception as exc:
        logger.error(
            "site_provider_keys delete failed user=%s site=%s provider=%s: %s",
            user_session["user_id"],
            site_id,
            provider,
            exc,
        )
        return JSONResponse(
            {"ok": False, "error": "storage_failed", "message": str(exc)},
            status_code=500,
        )
    return JSONResponse({"ok": True, "site_id": site_id, "provider": provider, "deleted": deleted})


async def api_site_provider_default_model(request: Request) -> Response:
    """PATCH /api/sites/{id}/provider-keys/{provider}/default-model.

    Body: ``{"model": "<id>"}`` to set, ``{"model": null}`` (or empty
    string) to clear. F.X.fix-pass3 — lets the user pin a discovered
    OpenRouter image-model id as the implicit default for a site, so
    MCP callers don't have to pass ``model=`` every time.
    """
    user_session, redirect = _require_user_session(request)
    if redirect or user_session is None:
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)

    site_id = (request.path_params.get("id") or "").strip()
    provider = (request.path_params.get("provider") or "").strip().lower()

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "invalid_json"}, status_code=400)
    if not isinstance(body, dict):
        return JSONResponse({"ok": False, "error": "invalid_body"}, status_code=400)

    raw = body.get("model")
    model: str | None
    if raw is None:
        model = None
    elif isinstance(raw, str):
        stripped = raw.strip()
        model = stripped or None
    else:
        return JSONResponse({"ok": False, "error": "invalid_model"}, status_code=400)

    from core.site_api import get_user_site

    site = await get_user_site(site_id, user_session["user_id"])
    if site is None:
        return JSONResponse({"ok": False, "error": "site_not_found"}, status_code=404)

    from core.database import get_database

    db = get_database()
    updated = await db.set_site_provider_default_model(site_id, provider, model)
    if not updated:
        return JSONResponse(
            {
                "ok": False,
                "error": "provider_key_not_found",
                "message": "Save the provider key first, then set the default model.",
            },
            status_code=404,
        )
    return JSONResponse(
        {
            "ok": True,
            "site_id": site_id,
            "provider": provider,
            "default_model": model,
        }
    )


def register_dashboard_routes(mcp):
    """
    Register dashboard routes with the MCP server.

    Args:
        mcp: FastMCP instance to register routes with.
    """
    logger.info("Registering dashboard routes...")

    # Set template globals (available in all templates without passing explicitly)
    templates.env.globals["project_version"] = _get_project_version()

    # Auth routes (E.2: OAuth Social Login)
    mcp.custom_route("/auth/login", methods=["GET"])(auth_login_page)
    mcp.custom_route("/auth/callback/{provider}", methods=["GET"])(auth_callback)
    mcp.custom_route("/auth/logout", methods=["GET", "POST"])(auth_logout)
    mcp.custom_route("/auth/{provider}", methods=["GET"])(auth_provider_redirect)

    # Legacy Jinja UI routes. The SPA owns /dashboard/* after G.12; the
    # remaining server-rendered pages now live under /dashboard-legacy/*.
    mcp.custom_route("/dashboard-legacy/profile", methods=["GET"])(dashboard_profile_page)
    mcp.custom_route("/dashboard-legacy/login", methods=["GET"])(dashboard_login_page)
    mcp.custom_route("/dashboard-legacy/login", methods=["POST"])(dashboard_login_submit)
    mcp.custom_route("/api/dashboard/login", methods=["POST"])(dashboard_api_login)
    mcp.custom_route("/dashboard/logout", methods=["GET", "POST"])(dashboard_logout)
    mcp.custom_route("/dashboard-legacy/logout", methods=["GET", "POST"])(dashboard_logout)
    mcp.custom_route("/dashboard-legacy", methods=["GET"])(dashboard_home)
    mcp.custom_route("/dashboard-legacy/", methods=["GET"])(dashboard_home)

    # Projects routes
    mcp.custom_route("/dashboard-legacy/projects", methods=["GET"])(dashboard_projects_list)
    mcp.custom_route("/dashboard-legacy/projects/{project_id:path}", methods=["GET"])(
        dashboard_project_detail
    )

    # API Keys routes (unified — /dashboard/keys replaces /dashboard/api-keys and /dashboard/connect)
    mcp.custom_route("/dashboard-legacy/keys", methods=["GET"])(dashboard_keys_unified)
    mcp.custom_route("/dashboard-legacy/api-keys", methods=["GET"])(
        lambda r: RedirectResponse("/dashboard-legacy/keys", status_code=301)
    )

    # OAuth Clients routes
    mcp.custom_route("/dashboard-legacy/oauth-clients", methods=["GET"])(
        dashboard_oauth_clients_list
    )

    # Audit Logs routes
    mcp.custom_route("/dashboard-legacy/audit-logs", methods=["GET"])(dashboard_audit_logs_list)

    # Health Monitoring routes
    mcp.custom_route("/dashboard-legacy/health", methods=["GET"])(dashboard_health_page)

    # Settings routes
    mcp.custom_route("/dashboard-legacy/settings", methods=["GET"])(dashboard_settings_page)

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
    mcp.custom_route("/api/dashboard/api-keys", methods=["GET"])(dashboard_api_keys_list_json)
    mcp.custom_route("/api/dashboard/api-keys/create", methods=["POST"])(dashboard_api_keys_create)
    mcp.custom_route("/api/dashboard/api-keys/{key_id}/revoke", methods=["POST"])(
        dashboard_api_keys_revoke
    )
    mcp.custom_route("/api/dashboard/api-keys/{key_id}", methods=["DELETE"])(
        dashboard_api_keys_delete
    )
    mcp.custom_route("/api/dashboard/oauth-clients", methods=["GET"])(
        dashboard_oauth_clients_list_json
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
    mcp.custom_route("/api/dashboard/settings", methods=["GET"])(api_get_settings)
    mcp.custom_route("/api/dashboard/settings", methods=["POST"])(api_save_setting)
    mcp.custom_route("/api/dashboard/settings/reset", methods=["POST"])(api_reset_settings)

    # Site Management routes (E.3)
    mcp.custom_route("/dashboard-legacy/sites", methods=["GET"])(dashboard_sites_list)
    mcp.custom_route("/dashboard-legacy/sites/add", methods=["GET"])(dashboard_sites_add)
    mcp.custom_route("/dashboard-legacy/sites/{id}/edit", methods=["GET"])(dashboard_sites_edit)
    mcp.custom_route("/dashboard-legacy/sites/{id}", methods=["GET"])(dashboard_sites_view)
    mcp.custom_route("/dashboard-legacy/connect", methods=["GET"])(
        lambda r: RedirectResponse("/dashboard-legacy/keys", status_code=301)
    )

    # Service pages (F.3)
    mcp.custom_route("/dashboard-legacy/services", methods=["GET"])(dashboard_services_list)
    mcp.custom_route("/dashboard-legacy/services/{plugin_type}", methods=["GET"])(
        dashboard_service_page
    )

    # Site Management API (E.3)
    mcp.custom_route("/api/sites", methods=["GET"])(api_list_sites)
    mcp.custom_route("/api/sites", methods=["POST"])(api_create_site)
    mcp.custom_route("/api/sites/{id}/test", methods=["POST"])(api_test_site)
    mcp.custom_route("/api/sites/{id}", methods=["DELETE"])(api_delete_site)
    mcp.custom_route("/api/sites/{id}", methods=["PATCH"])(api_update_site)

    # Per-site AI provider keys (F.5a.9.x)
    mcp.custom_route("/api/sites/{id}/provider-keys", methods=["GET"])(api_site_provider_keys_list)
    mcp.custom_route("/api/sites/{id}/provider-keys/{provider}", methods=["POST"])(
        api_site_provider_keys_set
    )
    mcp.custom_route("/api/sites/{id}/provider-keys/{provider}", methods=["DELETE"])(
        api_site_provider_keys_delete
    )
    mcp.custom_route("/api/sites/{id}/provider-keys/{provider}/default-model", methods=["PATCH"])(
        api_site_provider_default_model
    )
    from plugins.ai_image.providers.openrouter import api_openrouter_models

    mcp.custom_route("/api/providers/openrouter/models", methods=["GET"])(api_openrouter_models)

    # User API Key routes (E.3)
    mcp.custom_route("/api/keys", methods=["GET"])(api_list_keys)
    mcp.custom_route("/api/keys", methods=["POST"])(api_create_key)
    mcp.custom_route("/api/keys/{id}", methods=["DELETE"])(api_delete_key)

    # Config snippet API (E.3)
    mcp.custom_route("/api/config/{alias}", methods=["GET"])(api_get_config)

    # User OAuth Client routes (Bug C fix)
    mcp.custom_route("/dashboard-legacy/connect/oauth-clients", methods=["GET"])(
        dashboard_user_oauth_clients_list
    )
    mcp.custom_route("/api/dashboard/user-oauth-clients/create", methods=["POST"])(
        dashboard_user_oauth_clients_create
    )
    mcp.custom_route("/api/dashboard/user-oauth-clients/{client_id}", methods=["DELETE"])(
        dashboard_user_oauth_clients_delete
    )

    # F.18.8 /dashboard/provider-keys routes removed in F.5a.9.x —
    # per-site AI provider keys replace the per-user page. See the
    # per-site endpoints registered above:
    #   GET    /api/sites/{id}/provider-keys
    #   POST   /api/sites/{id}/provider-keys/{provider}
    #   DELETE /api/sites/{id}/provider-keys/{provider}

    # Track G — SPA / dashboard-v2 support (additive, leaves /dashboard/* untouched)
    from .spa_routes import register_spa_routes

    register_spa_routes(mcp)

    logger.info("Dashboard routes registered successfully")
