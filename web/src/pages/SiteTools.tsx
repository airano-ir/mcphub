import { useMemo, useState, type CSSProperties } from "react";
import { Link, useParams } from "react-router-dom";
import { Topbar } from "../components/Topbar";
import { Card, CardHead, Badge } from "../components/primitives";
import { Icons } from "../components/icons";
import {
  useDeleteSiteProviderKey,
  useOpenRouterImageModels,
  useSetSiteProviderKey,
  useSetSiteProviderDefaultModel,
  useSite,
  useSiteCapabilities,
  useSiteProviderKeys,
  useSiteTools,
  useToggleSiteTool,
  useUpdateSiteToolScope,
  type SiteCapabilityProbe,
  type ScopePreset,
} from "../lib/queries";
import { useT } from "../lib/i18n";
import { useUiStore } from "../lib/store";

function scopeKey(scope: string): string {
  return scope.replace(":", "_");
}

function scopeFallback(scope: string): string {
  const labels: Record<string, string> = {
    read: "Read",
    "read:sensitive": "Read sensitive",
    deploy: "Deploy",
    editor: "Editor",
    settings: "Settings",
    install: "Installer",
    write: "Write",
    admin: "Admin",
    custom: "Custom",
  };
  return labels[scope] ?? scope;
}

function credentialGuide(
  pluginType: string | undefined,
  scope: string,
  t: ReturnType<typeof useT>,
): { title: string; body: string } | null {
  if (!pluginType || scope === "custom") return null;
  const key = `${pluginType}.${scopeKey(scope)}`;
  const fallbacks: Record<string, string> = {
    "wordpress.read":
      "The Application Password saved in service credentials should belong to a WordPress user with at least Editor role. Basic read tools do not require CRUD capabilities.",
    "wordpress.admin":
      "The Application Password saved in service credentials must belong to a WordPress Administrator for full CRUD. SEO and companion-backed tools may also require their corresponding plugins to be active.",
    "wordpress_specialist.read":
      "The Application Password must belong to a WordPress user with manage_options (Administrator). Airano MCP Bridge v2.11.0+ must be installed and active for companion-backed tools.",
    "wordpress_specialist.editor":
      "Same prerequisites as Read, plus Airano MCP Bridge v2.13.0+ for page editing and v2.14.0+ for theme file CRUD. Tool calls still check edit_posts/edit_themes.",
    "wordpress_specialist.settings":
      "Same prerequisites as Editor. Settings, identity, permalink, and cron tools require an Administrator Application Password with manage_options.",
    "wordpress_specialist.install":
      "Same prerequisites as Settings, plus Airano MCP Bridge v2.14.0+ for theme install/activate/delete and v2.15.0+ for plugin install/activate/update.",
    "wordpress_specialist.admin":
      "Same prerequisites as Installer, plus destructive routes such as delete and URL/zip installs. PHP file edits require DISALLOW_FILE_EDIT to be unset or false.",
    "woocommerce.read":
      "The WooCommerce REST API Consumer Key and Secret saved in service credentials must have Read permission. The creating WordPress user should be at least Shop Manager to see orders and customers.",
    "woocommerce.admin":
      "The WooCommerce REST API key must have Read/Write permission and belong to an Administrator or Shop Manager. Media and AI image upload tools additionally need WordPress username and Application Password credentials.",
  };
  const title = t("tools.credential_requirement_title", "Credential requirement for {scope}")
    .replace("{scope}", t(`tier.${scopeKey(scope)}`, scopeFallback(scope)));
  const fallback = fallbacks[key];
  if (!fallback) return null;
  const body = t(`tools.credential_guide.${key}`, fallback);
  return body ? { title, body } : null;
}

function tierWarning(
  scope: string,
  t: ReturnType<typeof useT>,
): { severity: "warning" | "danger"; title: string; body: string } | null {
  if (scope === "install") {
    return {
      severity: "warning",
      title: t("tools.tier_warning_title", "Warning"),
      body: t(
        "tools.tier_warning.install",
        "Installer grants the AI agent permission to install and activate plugins or themes from curated repositories. Test on staging first and review installed extensions regularly.",
      ),
    };
  }
  if (scope === "admin") {
    return {
      severity: "danger",
      title: t("tools.tier_warning_title", "Warning"),
      body: t(
        "tools.tier_warning.admin",
        "Admin grants the full destructive surface: arbitrary installs, deletes, user CRUD, and other operations that may not have undo. Use only where mistakes are recoverable from backups.",
      ),
    };
  }
  return null;
}

function unavailableReasonMeta(reason: string | null | undefined, t: ReturnType<typeof useT>) {
  switch (reason) {
    case "provider_key":
      return {
        label: t("tools.reason.provider_key", "needs AI provider key"),
        detail: t("tools.reason.provider_key_detail", "Configure a provider key in AI Image Generation."),
        variant: "warning" as const,
      };
    case "companion_route":
      return {
        label: t("tools.reason.companion_route", "needs companion plugin"),
        detail: t("tools.reason.companion_route_detail", "Install or update Airano MCP Bridge and run a connection test."),
        variant: "info" as const,
      };
    case "feature":
      return {
        label: t("tools.reason.feature", "needs SEO plugin"),
        detail: t("tools.reason.feature_detail", "Install Rank Math or Yoast support before enabling this tool."),
        variant: "warning" as const,
      };
    case "wp_credentials":
      return {
        label: t("tools.reason.wp_credentials", "needs WP App Password"),
        detail: t("tools.reason.wp_credentials_detail", "Add WordPress username and Application Password in service credentials for media uploads."),
        variant: "warning" as const,
      };
    case "probe_unknown":
      return {
        label: t("tools.reason.probe_unknown", "needs health probe"),
        detail: t("tools.reason.probe_unknown_detail", "Run a connection test so MCP Hub can verify service capabilities."),
        variant: "default" as const,
      };
    default:
      return null;
  }
}

export function SiteToolsPage() {
  const t = useT();
  const { id: siteId = "" } = useParams<{ id: string }>();
  const site = useSite(siteId);
  const data = useSiteTools(siteId);
  const supportsProviderKeys =
    data.data?.plugin_type === "wordpress" || data.data?.plugin_type === "woocommerce";
  const providerKeys = useSiteProviderKeys(siteId, supportsProviderKeys);
  const setProviderKey = useSetSiteProviderKey(siteId);
  const deleteProviderKey = useDeleteSiteProviderKey(siteId);
  const setProviderDefaultModel = useSetSiteProviderDefaultModel(siteId);
  const toggle = useToggleSiteTool(siteId);
  const updateScope = useUpdateSiteToolScope();
  const setToast = useUiStore((s) => s.setToast);
  const lang = useUiStore((s) => s.lang);

  const [pendingTool, setPendingTool] = useState<string | null>(null);
  const [providerInputs, setProviderInputs] = useState<Record<string, string>>({});
  const [pendingProvider, setPendingProvider] = useState<string | null>(null);
  const [pendingModel, setPendingModel] = useState<string | null>(null);
  const [filterScope, setFilterScope] = useState<string>("all");
  const [search, setSearch] = useState("");

  const tools = useMemo(() => data.data?.tools ?? [], [data.data?.tools]);
  const currentScope = data.data?.tool_scope ?? site.data?.tool_scope ?? "admin";
  const capabilities = useSiteCapabilities(siteId, currentScope);
  const scopePresets = data.data?.scope_presets ?? [];
  const configuredProviders = new Set(
    providerKeys.data?.providers ?? data.data?.configured_providers ?? [],
  );
  const defaultModels = providerKeys.data?.default_models ?? {};
  const scopeCounts = useMemo(() => {
    const m = new Map<string, number>();
    tools.forEach((tool) => m.set(tool.required_scope, (m.get(tool.required_scope) ?? 0) + 1));
    return m;
  }, [tools]);
  const allScopes = useMemo(
    () => Array.from(scopeCounts.keys()).sort(),
    [scopeCounts],
  );
  const guide = credentialGuide(data.data?.plugin_type, currentScope, t);
  const warning = tierWarning(currentScope, t);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return tools.filter((tool) => {
      if (filterScope !== "all" && tool.required_scope !== filterScope) return false;
      if (q && !tool.name.toLowerCase().includes(q) && !(tool.description ?? "").toLowerCase().includes(q))
        return false;
      return true;
    });
  }, [tools, filterScope, search]);

  // Group by required_scope so the page reads as a per-tier audit. Within a
  // group, sort by name so reorder doesn't shift as toggles flip enabled.
  const grouped = useMemo(() => {
    const groups = new Map<string, typeof filtered>();
    filtered.forEach((tool) => {
      const k = tool.required_scope || "other";
      if (!groups.has(k)) groups.set(k, []);
      groups.get(k)!.push(tool);
    });
    return Array.from(groups.entries())
      .map(([scope, arr]) => ({
        scope,
        tools: [...arr].sort((a, b) => a.name.localeCompare(b.name)),
      }))
      .sort((a, b) => a.scope.localeCompare(b.scope));
  }, [filtered]);

  const onToggle = async (name: string, next: boolean) => {
    setPendingTool(name);
    try {
      await toggle.mutateAsync({ name, enabled: next });
    } catch (e: any) {
      setToast(t("tools.toast_failed", "Failed to update tool: {error}").replace("{error}", e.message));
    } finally {
      setPendingTool(null);
    }
  };

  const onScopePick = async (scope: string) => {
    if (!siteId || scope === currentScope) return;
    try {
      await updateScope.mutateAsync({ siteId, scope });
      setToast(t("connect.toast.scope_updated", "Tool access updated to {scope}").replace("{scope}", scope));
    } catch (e: any) {
      setToast(t("connect.toast.scope_failed", "Update failed: {error}").replace("{error}", e.message));
    }
  };

  const onSaveProvider = async (provider: string) => {
    const apiKey = (providerInputs[provider] ?? "").trim();
    if (!apiKey) return;
    setPendingProvider(provider);
    try {
      await setProviderKey.mutateAsync({ provider, apiKey });
      setProviderInputs((prev) => ({ ...prev, [provider]: "" }));
      setToast(t("providers.toast_saved", "Provider key saved"));
    } catch (e: any) {
      setToast(t("providers.toast_save_failed", "Save failed: {error}").replace("{error}", e.message));
    } finally {
      setPendingProvider(null);
    }
  };

  const onRemoveProvider = async (provider: string) => {
    if (!window.confirm(t("providers.confirm_remove", "Remove this provider key?"))) return;
    setPendingProvider(provider);
    try {
      await deleteProviderKey.mutateAsync(provider);
      setToast(t("providers.toast_removed", "Provider key removed"));
    } catch (e: any) {
      setToast(t("providers.toast_remove_failed", "Remove failed: {error}").replace("{error}", e.message));
    } finally {
      setPendingProvider(null);
    }
  };

  const onSetDefaultModel = async (provider: string, model: string | null) => {
    setPendingModel(model ?? `${provider}:clear`);
    try {
      await setProviderDefaultModel.mutateAsync({ provider, model });
      setToast(
        model
          ? t("providers.model.toast_saved", "Default image model saved")
          : t("providers.model.toast_cleared", "Default image model cleared"),
      );
    } catch (e: any) {
      setToast(t("providers.model.toast_failed", "Model update failed: {error}").replace("{error}", e.message));
    } finally {
      setPendingModel(null);
    }
  };

  return (
    <>
      <Topbar
        crumbs={[t("workspace", "Workspace"), t("nav.sites", "Sites"), site.data?.alias ?? "—"]}
        actions={
          <Link to="/sites" className="btn btn-secondary btn-sm">
            <Icons.arrow style={{ width: 12, height: 12, transform: "scaleX(-1)" }} />{" "}
            {t("tools.back_to_sites", "Back to sites")}
          </Link>
        }
      />
      <div className="page-pad">
        <div className="page-head page-head-split">
          <div className="page-head-text">
            <div className="eyebrow" style={{ marginBottom: 8 }}>
              {t("tools.eyebrow", "Tool access")}
            </div>
            <h1 className="h-1" style={{ margin: 0 }}>
              {site.data?.alias ?? siteId}
            </h1>
            <div className="body" style={{ color: "var(--text-muted)", marginTop: 6, maxWidth: 640 }}>
              {t(
                "tools.intro",
                "Toggle individual MCP tools this site exposes. Scope-tier presets in Connect are easier for the common case — use this page to fine-tune.",
              )}
            </div>
          </div>
          <div className="page-head-actions">
            <div style={searchBoxStyle}>
              <Icons.search style={{ width: 14, height: 14, color: "var(--text-subtle)" }} />
              <input
                placeholder={t("tools.search_placeholder", "Filter tools…")}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                style={inputResetStyle}
              />
            </div>
            <select
              className="input"
              style={{ width: 200 }}
              value={filterScope}
              onChange={(e) => setFilterScope(e.target.value)}
            >
              <option value="all">
                {t("tools.scope_filter_all", "All scopes")} ({tools.length})
              </option>
              {allScopes.map((s) => (
                <option key={s} value={s}>
                  {t(`tier.${s.replace(":", "_")}`, s)} ({scopeCounts.get(s)})
                </option>
              ))}
            </select>
          </div>
        </div>

        {data.isLoading ? (
          <Card>
            <div className="card-body">
              <div className="shimmer" style={{ height: 28, borderRadius: 4, marginBottom: 8 }} />
              <div className="shimmer" style={{ height: 28, borderRadius: 4, marginBottom: 8 }} />
              <div className="shimmer" style={{ height: 28, borderRadius: 4 }} />
            </div>
          </Card>
        ) : tools.length === 0 ? (
          <Card>
            <div className="card-body" style={{ textAlign: "center", padding: 32 }}>
              <div className="caption">
                {t("tools.empty", "This plugin doesn't expose any tools yet.")}
              </div>
            </div>
          </Card>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {supportsProviderKeys ? (
              <ProviderKeysCard
                siteId={siteId}
                configuredProviders={configuredProviders}
                defaultModels={defaultModels}
                inputs={providerInputs}
                pendingProvider={pendingProvider}
                pendingModel={pendingModel}
                setInput={(provider, value) =>
                  setProviderInputs((prev) => ({ ...prev, [provider]: value }))
                }
                onSave={onSaveProvider}
                onRemove={onRemoveProvider}
                onSetDefaultModel={onSetDefaultModel}
                t={t}
              />
            ) : null}
            {scopePresets.length > 0 ? (
              <Card>
                <CardHead
                  icon="shield"
                  title={t("connect.tool_access", "Tool Access")}
                  subtitle={t(
                    "tools.preset_subtitle",
                    "Choose a service preset or Custom, then fine-tune individual tools below.",
                  )}
                />
                <div style={presetGridStyle}>
                  {scopePresets.map((preset) => {
                    const active = preset.value === currentScope;
                    const pending = updateScope.isPending && updateScope.variables?.scope === preset.value;
                    return (
                      <button
                        type="button"
                        key={preset.value}
                        disabled={updateScope.isPending}
                        onClick={() => onScopePick(preset.value)}
                        style={presetTileStyle(active, preset)}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                          <span style={{ fontWeight: 500 }}>
                            {lang === "fa" && preset.label_fa ? preset.label_fa : preset.label}
                          </span>
                          {active ? (
                            <Icons.check style={{ width: 14, height: 14, color: "var(--brand-400)" }} />
                          ) : pending ? (
                            <span className="caption">...</span>
                          ) : null}
                        </div>
                        <div className="caption" style={{ marginTop: 4 }}>
                          {lang === "fa" && preset.hint_fa ? preset.hint_fa : preset.hint}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </Card>
            ) : null}
            <ToolReadinessCard
              warning={warning}
              guide={guide}
              capability={capabilities.data}
              isCapabilityLoading={capabilities.isLoading}
              t={t}
            />
            {grouped.map((group) => (
              <Card key={group.scope}>
                <CardHead
                  icon="shield"
                  title={t(`tier.${group.scope.replace(":", "_")}`, group.scope)}
                  subtitle={
                    t("tools.group_subtitle", "{n} tool(s) in this tier").replace(
                      "{n}",
                      String(group.tools.length),
                    )
                  }
                />
                <div>
                  {group.tools.map((tool) => {
                    const isPending = pendingTool === tool.name;
                    const disabled = !tool.available || isPending;
                    return (
                      <div key={tool.name} style={rowStyle}>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div
                            className="mono"
                            style={{
                              fontSize: 13,
                              color: tool.enabled ? "var(--text)" : "var(--text-muted)",
                              wordBreak: "break-all",
                            }}
                          >
                            {tool.name}
                          </div>
                          {tool.description ? (
                            <div
                              className="caption"
                              style={{ marginTop: 4, opacity: tool.enabled ? 1 : 0.6 }}
                            >
                              {tool.description}
                            </div>
                          ) : null}
                          {!tool.available && tool.unavailable_reason ? (
                            <div
                              className="caption"
                              style={{ marginTop: 4, color: "var(--warning)" }}
                            >
                              {t("tools.unavailable", "Unavailable")}:{" "}
                              {unavailableReasonMeta(tool.unavailable_reason, t)?.detail ?? tool.unavailable_reason}
                            </div>
                          ) : null}
                          {tool.provider_key_required && !tool.provider_key_configured ? (
                            <div
                              className="caption"
                              style={{ marginTop: 4, color: "var(--warning)" }}
                            >
                              {t(
                                "tools.needs_provider_key",
                                "Needs an AI provider key — configure one above.",
                              )}
                            </div>
                          ) : null}
                          {!tool.available && tool.unavailable_reason ? (
                            <div style={reasonRowStyle}>
                              <ReasonBadge reason={tool.unavailable_reason} t={t} />
                              {tool.unavailable_reason === "provider_key" && supportsProviderKeys ? (
                                <button
                                  type="button"
                                  className="btn btn-ghost btn-sm"
                                  onClick={() =>
                                    document
                                      .getElementById("site-provider-keys")
                                      ?.scrollIntoView({ behavior: "smooth", block: "start" })
                                  }
                                >
                                  {t("tools.configure_provider_key", "Configure key")}
                                </button>
                              ) : null}
                            </div>
                          ) : null}
                        </div>
                        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                          {tool.sensitivity ? (
                            <Badge
                              variant={tool.sensitivity === "destructive" ? "danger" : "warning"}
                              className="badge-fixed"
                              title={tool.sensitivity}
                            >
                              {t(`tools.sensitivity.${tool.sensitivity}`, tool.sensitivity)}
                            </Badge>
                          ) : null}
                          <button
                            type="button"
                            className={`switch ${tool.enabled ? "on" : ""}`}
                            disabled={disabled}
                            aria-label={tool.name}
                            aria-pressed={tool.enabled}
                            style={{ opacity: disabled ? 0.5 : 1 }}
                            onClick={() => onToggle(tool.name, !tool.enabled)}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>
    </>
  );
}

function ToolReadinessCard({
  warning,
  guide,
  capability,
  isCapabilityLoading,
  t,
}: {
  warning: ReturnType<typeof tierWarning>;
  guide: ReturnType<typeof credentialGuide>;
  capability?: SiteCapabilityProbe;
  isCapabilityLoading: boolean;
  t: ReturnType<typeof useT>;
}) {
  const fit = capability?.fit;
  const fitStatus = fit?.status;
  const aiProviders = capability?.ai_providers_configured ?? [];
  return (
    <Card>
      <CardHead
        icon="shield"
        title={t("tools.readiness_title", "Service readiness")}
        subtitle={t(
          "tools.readiness_subtitle",
          "Credential and health checks determine which tools are exposed to MCP clients.",
        )}
      />
      <div style={readinessBodyStyle}>
        {warning ? (
          <div className={`alert ${warning.severity === "danger" ? "alert-danger" : "alert-warning"}`} style={readinessAlertStyle}>
            <Icons.warning style={{ width: 16, height: 16, flexShrink: 0, marginTop: 2 }} />
            <div>
              <div style={{ fontWeight: 600 }}>{warning.title}</div>
              <div className="caption" style={{ color: "inherit", marginTop: 4 }}>{warning.body}</div>
            </div>
          </div>
        ) : null}
        {guide ? (
          <div className="alert alert-info" style={readinessAlertStyle}>
            <Icons.key style={{ width: 16, height: 16, flexShrink: 0, marginTop: 2 }} />
            <div>
              <div style={{ fontWeight: 600 }}>{guide.title}</div>
              <div className="caption" style={{ color: "inherit", marginTop: 4 }}>{guide.body}</div>
            </div>
          </div>
        ) : null}
        <div style={capabilitySummaryStyle}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <span style={{ fontWeight: 600 }}>{t("tools.capability_status", "Capability check")}</span>
            {isCapabilityLoading ? (
              <Badge className="badge-fixed">{t("loading", "Loading...")}</Badge>
            ) : fitStatus === "ok" ? (
              <Badge variant="success" dot className="badge-fixed">
                {t("tools.capability_ok", "credential fits selected tier")}
              </Badge>
            ) : fitStatus === "warning" ? (
              <Badge variant="warning" dot className="badge-fixed">
                {t("tools.capability_warning", "credential below selected tier")}
              </Badge>
            ) : fitStatus === "probe_unavailable" ? (
              <Badge variant="default" className="badge-fixed">
                {t("tools.capability_unavailable", "probe unavailable")}
              </Badge>
            ) : fitStatus === "unknown_tier" ? (
              <Badge variant="info" className="badge-fixed">
                {t("tools.capability_unknown_tier", "tier not probed")}
              </Badge>
            ) : (
              <Badge className="badge-fixed">{t("status_unknown", "unknown")}</Badge>
            )}
          </div>
          {!isCapabilityLoading && fitStatus === "warning" && (fit?.missing ?? []).length > 0 ? (
            <div className="caption" style={{ marginTop: 6 }}>
              {t("tools.capability_missing", "Missing")}:{" "}
              <span className="mono">{(fit?.missing ?? []).join(", ")}</span>
            </div>
          ) : null}
          {!isCapabilityLoading && fitStatus === "probe_unavailable" ? (
            <div className="caption" style={{ marginTop: 6 }}>
              {t("tools.capability_probe_reason", "Reason")}:{" "}
              <span className="mono">{fit?.reason ?? capability?.reason ?? "probe_unavailable"}</span>
            </div>
          ) : null}
          {!isCapabilityLoading ? (
            <div className="caption" style={{ marginTop: 6 }}>
              {t("tools.capability_ai_providers", "Configured AI providers")}:{" "}
              <span className="mono">
                {aiProviders.length > 0 ? aiProviders.join(", ") : t("providers.status_unset", "Unset")}
              </span>
            </div>
          ) : null}
        </div>
      </div>
    </Card>
  );
}

function ReasonBadge({
  reason,
  t,
}: {
  reason: string | null;
  t: ReturnType<typeof useT>;
}) {
  const meta = unavailableReasonMeta(reason, t);
  if (!meta) return null;
  return (
    <Badge variant={meta.variant} className="badge-fixed" title={meta.detail}>
      {meta.label}
    </Badge>
  );
}

const PROVIDERS = [
  { id: "openai", label: "OpenAI" },
  { id: "stability", label: "Stability AI" },
  { id: "replicate", label: "Replicate" },
  { id: "openrouter", label: "OpenRouter" },
];

function ProviderKeysCard({
  siteId,
  configuredProviders,
  defaultModels,
  inputs,
  pendingProvider,
  pendingModel,
  setInput,
  onSave,
  onRemove,
  onSetDefaultModel,
  t,
}: {
  siteId: string;
  configuredProviders: Set<string>;
  defaultModels: Record<string, string | null>;
  inputs: Record<string, string>;
  pendingProvider: string | null;
  pendingModel: string | null;
  setInput: (provider: string, value: string) => void;
  onSave: (provider: string) => void;
  onRemove: (provider: string) => void;
  onSetDefaultModel: (provider: string, model: string | null) => void;
  t: ReturnType<typeof useT>;
}) {
  const openRouterIsSet = configuredProviders.has("openrouter");
  const openRouterModels = useOpenRouterImageModels(siteId, openRouterIsSet);
  const currentDefault = defaultModels.openrouter ?? null;

  return (
    <Card id="site-provider-keys">
      <CardHead
        icon="spark"
        title={t("providers.title", "AI Image Generation")}
        subtitle={t(
          "providers.subtitle",
          "Store provider API keys for this service. Image generation tools stay unavailable until a provider key is set and the service connection is healthy.",
        )}
      />
      <div style={providerGridStyle}>
        {PROVIDERS.map((provider) => {
          const isSet = configuredProviders.has(provider.id);
          const pending = pendingProvider === provider.id;
          return (
            <div key={provider.id} style={providerRowStyle} data-provider-row={provider.id}>
              <div style={{ minWidth: 0 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontWeight: 500 }}>{provider.label}</span>
                  <Badge variant={isSet ? "success" : "default"} className="badge-fixed">
                    {isSet ? t("providers.status_set", "Set") : t("providers.status_unset", "Unset")}
                  </Badge>
                </div>
                <div className="caption" style={{ marginTop: 4 }}>
                  {t(
                    `providers.hint.${provider.id}`,
                    provider.id === "openrouter"
                      ? "Supports image-capable OpenRouter models. Save a key, then choose a default model for this service."
                      : "Save a new key to replace the stored value.",
                  )}
                </div>
                {provider.id === "openrouter" && isSet ? (
                  <OpenRouterModelPicker
                    models={openRouterModels.data ?? []}
                    isLoading={openRouterModels.isLoading}
                    isError={openRouterModels.isError}
                    currentDefault={currentDefault}
                    pendingModel={pendingModel}
                    onSetDefault={(model) => onSetDefaultModel("openrouter", model)}
                    t={t}
                  />
                ) : null}
              </div>
              <div style={providerActionsStyle}>
                <input
                  className="input"
                  type="password"
                  value={inputs[provider.id] ?? ""}
                  onChange={(e) => setInput(provider.id, e.target.value)}
                  placeholder={t("providers.new_key_placeholder", "New API key")}
                  aria-label={`${provider.label} ${t("providers.new_key_placeholder", "New API key")}`}
                  style={{ minWidth: 180 }}
                />
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  disabled={pending || !(inputs[provider.id] ?? "").trim()}
                  onClick={() => onSave(provider.id)}
                >
                  {pending ? "..." : t("action.save", "Save")}
                </button>
                {isSet ? (
                  <button
                    type="button"
                    className="btn btn-ghost btn-sm"
                    disabled={pending}
                    onClick={() => onRemove(provider.id)}
                    style={{ color: "var(--danger)" }}
                  >
                    {t("providers.remove", "Remove")}
                  </button>
                ) : null}
              </div>
            </div>
          );
        })}
      </div>
      <div className="caption" style={{ padding: "0 20px 20px", color: "var(--text-subtle)" }}>
        {t(
          "providers.encrypted_note",
          "Keys are encrypted at rest and scoped to this service only.",
        )}
      </div>
    </Card>
  );
}

function OpenRouterModelPicker({
  models,
  isLoading,
  isError,
  currentDefault,
  pendingModel,
  onSetDefault,
  t,
}: {
  models: import("../lib/queries").OpenRouterImageModel[];
  isLoading: boolean;
  isError: boolean;
  currentDefault: string | null;
  pendingModel: string | null;
  onSetDefault: (model: string | null) => void;
  t: ReturnType<typeof useT>;
}) {
  const [selected, setSelected] = useState(currentDefault ?? "");
  const active = selected || currentDefault || "";

  if (isLoading) {
    return <div className="caption" style={{ marginTop: 8 }}>{t("providers.model.loading", "Loading image models…")}</div>;
  }
  if (isError) {
    return (
      <div className="caption" style={{ marginTop: 8, color: "var(--warning)" }}>
        {t("providers.model.failed", "Could not load OpenRouter image models. The tool remains disabled if the provider connection is not healthy.")}
      </div>
    );
  }
  if (models.length === 0) {
    return (
      <div className="caption" style={{ marginTop: 8, color: "var(--warning)" }}>
        {t("providers.model.empty", "No image-capable OpenRouter models were found for this key.")}
      </div>
    );
  }

  const selectedModel = models.find((m) => m.id === active);
  const price =
    typeof selectedModel?.price_per_image_usd === "number"
      ? `$${selectedModel.price_per_image_usd.toFixed(3)}`
      : null;

  return (
    <div style={modelPickerStyle}>
      <label className="field" style={{ margin: 0, flex: "1 1 260px" }}>
        <span>{t("providers.model.default_label", "Default image model")}</span>
        <select className="input" value={active} onChange={(e) => setSelected(e.target.value)}>
          <option value="">{t("providers.model.select", "Select a model")}</option>
          {models.map((model) => (
            <option key={model.id} value={model.id}>
              {model.name || model.id}
            </option>
          ))}
        </select>
      </label>
      <button
        type="button"
        className="btn btn-secondary btn-sm"
        disabled={!selected || selected === currentDefault || pendingModel === selected}
        onClick={() => onSetDefault(selected)}
      >
        {pendingModel === selected ? "..." : t("providers.model.set_default", "Set default")}
      </button>
      {currentDefault ? (
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          disabled={pendingModel === "openrouter:clear"}
          onClick={() => onSetDefault(null)}
        >
          {pendingModel === "openrouter:clear" ? "..." : t("providers.model.clear", "Clear")}
        </button>
      ) : null}
      {currentDefault ? (
        <div className="caption" style={{ flexBasis: "100%" }}>
          {t("providers.model.current", "Current default: {model}").replace("{model}", currentDefault)}
          {price ? ` · ${price}` : ""}
        </div>
      ) : null}
    </div>
  );
}

const searchBoxStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 8,
  padding: "7px 10px",
  flex: 1,
  minWidth: 220,
  background: "var(--bg-sunken)",
  border: "1px solid var(--border)",
  borderRadius: 8,
  fontSize: 13,
};

const providerGridStyle: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  padding: "4px 20px 12px",
};

const providerRowStyle: CSSProperties = {
  display: "flex",
  gap: 14,
  justifyContent: "space-between",
  alignItems: "center",
  padding: "14px 0",
  borderBottom: "1px solid var(--border)",
};

const providerActionsStyle: CSSProperties = {
  display: "flex",
  gap: 8,
  alignItems: "center",
  flexWrap: "wrap",
  justifyContent: "flex-end",
};

const modelPickerStyle: CSSProperties = {
  marginTop: 10,
  display: "flex",
  gap: 8,
  alignItems: "flex-end",
  flexWrap: "wrap",
};

const inputResetStyle: CSSProperties = {
  flex: 1,
  background: "none",
  border: "none",
  color: "var(--text)",
  outline: "none",
};

const rowStyle: CSSProperties = {
  display: "flex",
  gap: 14,
  alignItems: "center",
  padding: "14px 20px",
  borderBottom: "1px solid var(--border)",
};

const reasonRowStyle: CSSProperties = {
  display: "flex",
  gap: 8,
  alignItems: "center",
  flexWrap: "wrap",
  marginTop: 8,
};

const readinessBodyStyle: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 10,
  padding: 20,
};

const readinessAlertStyle: CSSProperties = {
  alignItems: "flex-start",
  fontSize: 13,
  lineHeight: 1.5,
};

const capabilitySummaryStyle: CSSProperties = {
  border: "1px solid var(--border)",
  borderRadius: 8,
  padding: "12px 14px",
  background: "var(--bg-sunken)",
  fontSize: 13,
};

const presetGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fill, minmax(190px, 1fr))",
  gap: 8,
  padding: 20,
};

function presetTileStyle(active: boolean, preset: ScopePreset): CSSProperties {
  const accent = preset.value === "admin" ? "var(--danger)" : "var(--brand-400)";
  return {
    textAlign: "left",
    padding: "10px 12px",
    background: active ? "var(--surface)" : "var(--bg-sunken)",
    border: `1px solid ${active ? accent : "var(--border)"}`,
    borderRadius: 8,
    cursor: "pointer",
    color: "var(--text)",
    fontSize: 13,
  };
}
