// react-query hooks per resource. Keys mirror REST paths for simplicity.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import type {
  ApiKey,
  AuditEntry,
  DashboardStats,
  HealthData,
  OAuthClient,
  Project,
  Session,
  Site,
  Translations,
  UserKey,
} from "./types";

// ---------- Session ----------
export function useSession() {
  return useQuery({
    queryKey: ["me"],
    queryFn: () => api.get<Session>("/api/me"),
    staleTime: 60_000,
    retry: 0,
  });
}

// ---------- i18n ----------
export function useTranslations(lang: "en" | "fa") {
  return useQuery({
    queryKey: ["i18n", lang],
    queryFn: () => api.get<Translations>(`/api/i18n/${lang}`),
    staleTime: 60 * 60_000,
  });
}

// ---------- Dashboard stats ----------
// Server returns { stats: {...}, projects_by_type, health }; flatten to the
// stats object the SPA pages consume directly. User-session vs admin-session
// shapes differ, but both nest the headline numbers under `stats`.
export function useDashboardStats() {
  return useQuery({
    queryKey: ["dashboard-stats"],
    queryFn: () =>
      api.get<{ stats: DashboardStats; projects_by_type?: unknown; health?: unknown }>(
        "/api/dashboard/stats",
      ),
    select: (data) => data?.stats ?? ({} as DashboardStats),
    staleTime: 30_000,
  });
}

// ---------- Projects (admin) ----------
// Server returns paginated { projects: [...], total_count, ... }; pages
// consume the array directly.
export function useProjects() {
  return useQuery({
    queryKey: ["projects"],
    queryFn: () =>
      api.get<{ projects: Project[]; total_count?: number }>("/api/dashboard/projects"),
    select: (data) => data?.projects ?? [],
  });
}

// ---------- Admin API keys ----------
// /api/dashboard/api-keys (Track G GET endpoint) returns
// { keys: [...], total_count, total_pages, current_page, per_page }.
export function useAdminApiKeys() {
  return useQuery({
    queryKey: ["admin-api-keys"],
    queryFn: () => api.get<{ keys: ApiKey[] }>("/api/dashboard/api-keys"),
    select: (data) => data?.keys ?? [],
  });
}

export function useCreateAdminApiKey() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { description: string; scope?: string; project_id?: string | null }) =>
      api.post<{ id: string; key: string }>("/api/dashboard/api-keys/create", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-api-keys"] }),
  });
}

export function useRevokeAdminApiKey() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.post(`/api/dashboard/api-keys/${id}/revoke`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-api-keys"] }),
  });
}

export function useDeleteAdminApiKey() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.del(`/api/dashboard/api-keys/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-api-keys"] }),
  });
}

// ---------- OAuth clients (admin) ----------
// /api/dashboard/oauth-clients (Track G GET endpoint) returns
// { clients: [...], total_count }. Admin sees all; OAuth user sees own.
export function useOAuthClients() {
  return useQuery({
    queryKey: ["oauth-clients"],
    queryFn: () =>
      api.get<{ clients: OAuthClient[]; total_count?: number }>("/api/dashboard/oauth-clients"),
    select: (data) =>
      (data?.clients ?? []).map((client: any) => ({
        id: client.id ?? client.client_id,
        name: client.name ?? client.client_name,
        redirect_uris: client.redirect_uris ?? [],
        created_at: client.created_at,
      })),
  });
}

export function useCreateOAuthClient() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; redirect_uris: string[] }) =>
      api.post<{
        success: boolean;
        client_id: string;
        client_secret: string;
        client?: {
          client_id?: string;
          id?: string;
          client_name?: string;
          name?: string;
          redirect_uris?: string[];
          created_at?: string;
        };
      }>("/api/dashboard/oauth-clients/create", body),
    onSuccess: (data, variables) => {
      const created = data.client;
      if (created) {
        qc.setQueryData<{ clients: any[]; total_count?: number }>(["oauth-clients"], (prev) => {
          const clients = prev?.clients ?? [];
          const client_id = created.client_id ?? created.id ?? data.client_id;
          return {
            clients: [
              {
                client_id,
                client_name: created.client_name ?? created.name ?? variables.name,
                redirect_uris: created.redirect_uris ?? variables.redirect_uris,
                created_at: created.created_at,
              },
              ...clients.filter((client: any) => (client.client_id ?? client.id) !== client_id),
            ],
            total_count: (prev?.total_count ?? clients.length) + 1,
          };
        });
      }
      qc.invalidateQueries({ queryKey: ["oauth-clients"] });
    },
  });
}

export function useDeleteOAuthClient() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.del(`/api/dashboard/oauth-clients/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["oauth-clients"] }),
  });
}

// ---------- Audit logs ----------
// Server returns { logs, stats, total_count, total_pages, current_page, per_page }.
// SPA expects { total, entries } — translate at the edge so the page does not need to know.
// AuditLogs hook: filters are server-side so we can paginate over millions
// of rows. Backend params: event_type, level, date (YYYY-MM-DD), search, page.
export function useAuditLogs(opts: {
  page?: number;
  limit?: number;
  level?: string;
  search?: string;
  date?: string;
  eventType?: string;
} = {}) {
  const { page = 1, limit = 50, level, search, date, eventType } = opts;
  const params = new URLSearchParams({
    page: String(page),
    limit: String(limit),
  });
  if (level && level !== "all") params.set("level", level);
  if (search) params.set("search", search);
  if (date) params.set("date", date);
  if (eventType) params.set("event_type", eventType);

  return useQuery({
    queryKey: ["audit-logs", page, limit, level, search, date, eventType],
    queryFn: () =>
      api.get<{
        logs: AuditEntry[];
        total_count: number;
        total_pages?: number;
        current_page?: number;
        per_page?: number;
      }>(`/api/dashboard/audit-logs?${params}`),
    select: (data) => ({
      total: data?.total_count ?? 0,
      pages: data?.total_pages ?? 1,
      entries: data?.logs ?? [],
    }),
  });
}

// ---------- Health ----------
export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: () => api.get<HealthData>("/api/dashboard/health"),
    refetchInterval: 30_000,
  });
}

// ---------- User sites ----------
// Server returns { sites: [...] }; pages consume the array directly.
export function useSites() {
  return useQuery({
    queryKey: ["sites"],
    queryFn: () => api.get<{ sites: Site[]; limit?: number; remaining?: number }>("/api/sites"),
    select: (data) => data?.sites ?? [],
  });
}

export function useSiteLimit() {
  return useQuery({
    queryKey: ["sites"],
    queryFn: () => api.get<{ sites: Site[]; limit?: number; remaining?: number }>("/api/sites"),
    select: (data) => ({
      limit: data?.limit,
      remaining: data?.remaining,
      count: data?.sites?.length ?? 0,
    }),
  });
}

// Single-site GET is not exposed by the backend; surface the matching site
// from the cached list instead of issuing a doomed /api/sites/{id} request.
export function useSite(id: string | undefined) {
  return useQuery({
    queryKey: ["sites", id],
    queryFn: async () => {
      const res = await api.get<{ sites: Site[] }>("/api/sites");
      return (res?.sites ?? []).find((s) => s.id === id);
    },
    enabled: !!id,
  });
}

export function useCreateSite() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<Site> & { credentials?: Record<string, unknown> }) =>
      api.post<Site>("/api/sites", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sites"] }),
  });
}

export function useUpdateSite(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<Site> & { credentials?: Record<string, unknown> }) =>
      api.patch<Site>(`/api/sites/${id}`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sites"] });
      qc.invalidateQueries({ queryKey: ["sites", id] });
    },
  });
}

export function useDeleteSite() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.del(`/api/sites/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["sites"] }),
  });
}

export function useTestSite() {
  return useMutation({
    // Backend response shape (core/dashboard/routes.py:api_test_site):
    // { ok: bool, message: str, status: "active"|"error", last_tested_at: ISO }
    mutationFn: (id: string) =>
      api.post<{
        ok?: boolean;
        status: string;
        message?: string;
        response_time?: number;
        last_tested_at?: string;
      }>(`/api/sites/${id}/test`),
  });
}

export function useSiteConfig(alias: string | undefined) {
  return useQuery({
    queryKey: ["config", alias],
    queryFn: () => api.get<{ client_configs: Record<string, any> }>(`/api/config/${alias}`),
    enabled: !!alias,
  });
}

// ---------- Admin managed settings ----------
// GET returns { settings: [{ key, value, source, default, label, hint, ... }] }
// POST { key, value } persists to the database; admin-only on both.
export type ManagedSetting = {
  key: string;
  value: string;
  source: "database" | "environment" | "default";
  default: string;
  label: string;
  label_fa: string;
  hint: string;
  hint_fa: string;
};

export function useManagedSettings() {
  return useQuery({
    queryKey: ["managed-settings"],
    queryFn: () =>
      api.get<{ settings: ManagedSetting[] }>("/api/dashboard/settings"),
    select: (data) => data?.settings ?? [],
  });
}

export function useSaveSetting() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { key: string; value: string; action?: "save" | "reset" }) =>
      api.post("/api/dashboard/settings", body),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: ["managed-settings"] });
      if (variables.key === "ENABLED_PLUGINS") {
        qc.invalidateQueries({ queryKey: ["plugins"] });
        qc.invalidateQueries({ queryKey: ["sites"] });
      }
    },
  });
}

export function useResetSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<{ ok: boolean; deleted: number }>("/api/dashboard/settings/reset"),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["managed-settings"] });
      qc.invalidateQueries({ queryKey: ["plugins"] });
      qc.invalidateQueries({ queryKey: ["sites"] });
    },
  });
}

// PATCH /api/sites/{site_id}/tool-scope — update the site's tier preset.
// Body: { scope: "read" | "read:sensitive" | "deploy" | "editor" | "settings"
// | "install" | "write" | "admin" | "custom" }.
export function useUpdateSiteToolScope() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ siteId, scope }: { siteId: string; scope: string }) =>
      api.patch<{ ok: boolean; site_id: string; tool_scope: string }>(
        `/api/sites/${siteId}/tool-scope`,
        { scope },
      ),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: ["sites"] });
      qc.invalidateQueries({ queryKey: ["site-tools", variables.siteId] });
    },
  });
}

// ---------- Plugins catalog (G.12 prep) ----------
// /api/plugins returns the per-plugin credential field schema. Used by the
// SPA's native Site Add/Edit dialog to avoid round-tripping to the legacy
// Jinja form. Admins see every plugin; user sessions are filtered to the
// public set via ENABLED_PLUGINS.
export type PluginFieldDef = {
  name: string;
  label: string;
  type: "text" | "password" | "url" | string;
  required: boolean;
  hint?: string;
  advanced?: boolean;
};
export type PluginCatalogEntry = {
  type: string;
  name: string;
  fields: PluginFieldDef[];
};

export function usePluginCatalog() {
  return useQuery({
    queryKey: ["plugins"],
    queryFn: () => api.get<{ plugins: PluginCatalogEntry[] }>("/api/plugins"),
    select: (data) => data?.plugins ?? [],
    staleTime: 60_000,
  });
}

// ---------- Per-site tools (G.5c) ----------
// GET /api/sites/{site_id}/tools returns every tool the plugin defines with
// its current toggle state and prerequisite metadata. PATCH /tools/{name}
// flips a single tool; the bulk-toggle endpoint isn't exposed here yet —
// scope-tier preset (above) covers the bulk case.
export type SiteTool = {
  name: string;
  description: string;
  plugin_type: string;
  category: string | null;
  sensitivity: string | null;
  required_scope: string;
  enabled: boolean;
  provider_key_required: boolean;
  provider_key_configured: boolean;
  available: boolean;
  unavailable_reason: string | null;
};

export type ScopePreset = {
  value: string;
  label: string;
  label_fa?: string;
  hint: string;
  hint_fa?: string;
};

export type SiteCapabilityProbe = {
  ok: boolean;
  plugin_type?: string;
  probe_available?: boolean;
  reason?: string | null;
  granted?: string[];
  ai_providers_configured?: string[];
  tier?: string;
  fit?: {
    status?: "ok" | "warning" | "probe_unavailable" | "unknown_tier" | string;
    required?: string[];
    missing?: string[];
    reason?: string | null;
  };
};

export function useSiteCapabilities(siteId: string | undefined, tier: string | undefined) {
  return useQuery({
    queryKey: ["site-capabilities", siteId, tier],
    queryFn: () => {
      const params = new URLSearchParams();
      if (tier) params.set("tier", tier);
      const qs = params.toString();
      return api.get<SiteCapabilityProbe>(`/api/sites/${siteId}/capabilities${qs ? `?${qs}` : ""}`);
    },
    enabled: !!siteId,
    staleTime: 60_000,
  });
}

export function useSiteTools(siteId: string | undefined) {
  return useQuery({
    queryKey: ["site-tools", siteId],
    queryFn: () =>
      api.get<{
        site_id: string;
        plugin_type: string;
        tool_scope: string;
        scope_presets?: ScopePreset[];
        configured_providers: string[];
        tools: SiteTool[];
      }>(`/api/sites/${siteId}/tools`),
    enabled: !!siteId,
  });
}

export type SiteProviderKeyState = {
  ok: boolean;
  providers: string[];
  default_models?: Record<string, string | null>;
};

export function useSiteProviderKeys(siteId: string | undefined, enabled = true) {
  return useQuery({
    queryKey: ["site-provider-keys", siteId],
    queryFn: () => api.get<SiteProviderKeyState>(`/api/sites/${siteId}/provider-keys`),
    enabled: !!siteId && enabled,
  });
}

export function useSetSiteProviderKey(siteId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ provider, apiKey }: { provider: string; apiKey: string }) =>
      api.post<{ ok: boolean; provider: string; secret_last4?: string }>(
        `/api/sites/${siteId}/provider-keys/${provider}`,
        { api_key: apiKey },
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["site-provider-keys", siteId] });
      qc.invalidateQueries({ queryKey: ["site-tools", siteId] });
      qc.invalidateQueries({ queryKey: ["site-capabilities", siteId] });
    },
  });
}

export function useDeleteSiteProviderKey(siteId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (provider: string) =>
      api.del<{ ok: boolean; provider: string; deleted: boolean }>(
        `/api/sites/${siteId}/provider-keys/${provider}`,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["site-provider-keys", siteId] });
      qc.invalidateQueries({ queryKey: ["site-tools", siteId] });
      qc.invalidateQueries({ queryKey: ["site-capabilities", siteId] });
    },
  });
}

export type OpenRouterImageModel = {
  id: string;
  name: string;
  description?: string;
  context_length?: number | null;
  input_modalities?: string[];
  output_modalities?: string[];
  price_per_image_usd?: number | null;
};

export function useOpenRouterImageModels(siteId: string | undefined, enabled = true) {
  return useQuery({
    queryKey: ["openrouter-image-models", siteId],
    queryFn: () =>
      api.get<{ ok: boolean; provider: "openrouter"; models: OpenRouterImageModel[] }>(
        `/api/providers/openrouter/models?site_id=${encodeURIComponent(siteId ?? "")}`,
      ),
    select: (data) => data?.models ?? [],
    enabled: !!siteId && enabled,
    staleTime: 60 * 60_000,
  });
}

export function useSetSiteProviderDefaultModel(siteId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ provider, model }: { provider: string; model: string | null }) =>
      api.patch<{ ok: boolean; provider: string; default_model: string | null }>(
        `/api/sites/${siteId}/provider-keys/${provider}/default-model`,
        { model },
      ),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: ["site-provider-keys", siteId] });
      if (variables.provider === "openrouter") {
        qc.invalidateQueries({ queryKey: ["openrouter-image-models", siteId] });
      }
    },
  });
}

export function useToggleSiteTool(siteId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ name, enabled, reason }: { name: string; enabled: boolean; reason?: string }) =>
      api.patch<{ ok: boolean; tool_name: string; enabled: boolean }>(
        `/api/sites/${siteId}/tools/${name}`,
        { enabled, reason },
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["site-tools", siteId] }),
  });
}

// ---------- User API keys ----------
// Server returns { keys: [...] }; pages consume the array directly.
export function useUserKeys() {
  return useQuery({
    queryKey: ["user-keys"],
    queryFn: () => api.get<{ keys: UserKey[] }>("/api/keys"),
    select: (data) =>
      (data?.keys ?? []).map((key) => {
        const expiresAt = key.expires_at ? Date.parse(key.expires_at) : Number.NaN;
        return {
          ...key,
          prefix: key.prefix ?? key.key_prefix,
          scope: key.scope ?? key.scopes,
          status:
            key.status ??
            (Number.isFinite(expiresAt) && expiresAt < Date.now() ? "expired" : "active"),
        };
      }),
  });
}

export function useCreateUserKey() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { name: string; site_id?: string; expires_in_days?: number }) =>
      api.post<{ id: string; key: string; name: string }>("/api/keys", body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["user-keys"] }),
  });
}

export function useDeleteUserKey() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.del(`/api/keys/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["user-keys"] }),
  });
}
