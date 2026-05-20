// Shared types for API responses. Kept loose where the backend already varies.

export type Session = {
  authenticated: boolean;
  user_id?: string;
  email?: string | null;
  name?: string | null;
  role?: "admin" | "user";
  type?: "master" | "api_key" | "oauth_user";
  is_admin: boolean;
  lang: "en" | "fa";
  // Provided by /api/me. The dashboard_csrf cookie is HttpOnly, so JS reads
  // the matching token from this field instead.
  csrf_token?: string | null;
  // Mirrors the server-side DISABLE_MASTER_KEY_LOGIN env var (inverted).
  // When false, the SPA hides the master-key form on /login.
  master_key_login_enabled?: boolean;
  max_sites_per_user?: number;
};

export type DashboardStats = {
  projects_count: number;
  api_keys_count: number;
  tools_count: number;
  uptime_days: number;
  users_count?: number;
  user_sites_count?: number;
  recent_users_count?: number;
};

export type Project = {
  full_id: string;
  alias: string;
  plugin_type: string;
  site_id?: string;
  status?: "healthy" | "warning" | "error" | "unknown";
  url?: string;
  tools_count?: number;
};

export type ApiKey = {
  id: string;
  description?: string;
  scope?: string;
  project_id?: string | null;
  created_at?: string;
  last_used?: string | null;
  status?: "active" | "revoked" | "expired" | "idle";
  prefix?: string;
};

export type Site = {
  id: string;
  alias: string;
  plugin_type: string;
  url?: string;
  // Backend persists `"active"` for sites passing the connection test (see
  // core/site_api.py). Keep both vocabularies so the type matches reality;
  // use `normalizeSiteStatus` from `lib/format.ts` before rendering.
  status?: "healthy" | "active" | "warning" | "error" | "unknown" | "untested";
  status_msg?: string;
  last_tested_at?: string | null;
  created_at?: string;
  // F.19.2.0 — per-site tool tier; values from _VALID_TOOL_SCOPES in
  // core/dashboard/routes.py (read, read:sensitive, deploy, editor,
  // settings, install, write, admin, custom). Returned by /api/sites
  // since the field is on the sites table; defaults to "admin".
  tool_scope?: string;
};

export type UserKey = {
  id: string;
  name: string;
  key_prefix?: string;
  prefix?: string;
  scopes?: string;
  scope?: string;
  site_id?: string | null;
  expires_at?: string | null;
  created_at?: string;
  last_used?: string | null;
  status?: "active" | "revoked" | "expired";
};

export type OAuthClient = {
  id: string;
  name: string;
  redirect_uris: string[];
  created_at?: string;
};

export type AuditEntry = {
  id?: string;
  timestamp: string;
  event_type: string;
  message?: string;
  level?: "info" | "warn" | "error";
  actor?: string;
  target?: string;
  ip?: string;
  duration_ms?: number;
  result?: "ok" | "denied" | "error";
};

// Mirrors get_health_data() in core/dashboard/routes.py — that endpoint
// is the source of truth, so the SPA reads its real fields directly.
export type HealthAlert = {
  level?: "info" | "warning" | "warn" | "error" | "critical";
  message?: string;
  source?: string;
  timestamp?: string;
  status_code?: number;
  path?: string;
};

export type HealthData = {
  system_status?: "healthy" | "degraded" | "down" | "unknown";
  metrics?: {
    total_requests?: number;
    successful_requests?: number;
    failed_requests?: number;
    average_response_time_ms?: number;
    error_rate_percent?: number;
    requests_per_minute?: number;
  };
  uptime?: {
    start_time?: string;
    current_time?: string;
    formatted?: string;
    days?: number;
    hours?: number;
  };
  alerts?: HealthAlert[];
  projects_health?: Record<
    string,
    {
      status?: string;
      latency_ms?: number;
      uptime_percent?: number;
      tool_count?: number;
      last_check?: string;
      message?: string;
    }
  >;
  projects_summary?: {
    total?: number;
    healthy?: number;
    unhealthy?: number;
  };
};

export type Translations = Record<string, string>;
