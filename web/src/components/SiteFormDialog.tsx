import { useEffect, useMemo, useState, type CSSProperties } from "react";
import { Card, Btn } from "./primitives";
import { Icons } from "./icons";
import {
  usePluginCatalog,
  useCreateSite,
  useUpdateSite,
  useInitSiteOAuth,
  type PluginFieldDef,
} from "../lib/queries";
import { OAUTH_PLUGIN_TYPES } from "../lib/queries";
import { useT } from "../lib/i18n";
import { useUiStore } from "../lib/store";
import type { Site } from "../lib/types";

type Mode = "create" | "edit";

function advancedFieldsLabel(
  showAdvanced: boolean,
  pluginName: string | undefined,
  fields: PluginFieldDef[],
  t: (key: string, fallback?: string) => string,
): string {
  const advanced = fields.filter((field) => field.advanced);
  const service = pluginName ?? t("sites.selected_service", "selected service");
  const fieldNames = advanced
    .slice(0, 3)
    .map((field) => field.label)
    .join(", ");
  const extra = advanced.length > 3 ? ` +${advanced.length - 3}` : "";
  const suffix = fieldNames ? `: ${fieldNames}${extra}` : "";
  return showAdvanced
    ? t("sites.hide_advanced_for_service", "Hide advanced {service} fields").replace("{service}", service)
    : t("sites.show_advanced_for_service", "Show advanced {service} fields").replace("{service}", service) + suffix;
}

function setupGuidance(
  pluginType: string,
  t: (key: string, fallback?: string) => string,
): { title: string; items: string[] } | null {
  if (pluginType === "wordpress" || pluginType === "wordpress_specialist") {
    return {
      title:
        pluginType === "wordpress_specialist"
          ? t("sites.guidance.wordpress_specialist_title", "WordPress Specialist requirements")
          : t("sites.guidance.wordpress_title", "WordPress requirements"),
      items: [
        t(
          "sites.guidance.wp_username",
          "Username: WordPress admin username that owns the Application Password. Required.",
        ),
        t(
          "sites.guidance.wp_app_password",
          "Application Password: WP Admin -> Users -> Profile -> Application Passwords. User must have manage_options. Required.",
        ),
        t(
          "sites.guidance.bridge_version",
          "Airano MCP Bridge v2.11.0+ is recommended for companion-backed tools.",
        ),
        t(
          "sites.guidance.bridge_lag",
          "The WordPress.org plugin page can lag behind repository builds while publishing/review completes; do not assume the newest repo feature is already available there.",
        ),
        t(
          "sites.guidance.companion_copy",
          "Airano MCP Bridge — companion plugin (optional but recommended). Installing it unlocks larger uploads, unified site-health snapshot, cache purge, transient flush, bulk meta writes, structured export, capability probe, and audit-hook webhooks. Without it, basic tools still work but these features remain unavailable.",
        ),
      ],
    };
  }
  if (pluginType === "woocommerce") {
    return {
      title: t("sites.guidance.woocommerce_title", "WooCommerce requirements"),
      items: [
        t(
          "sites.guidance.wc_consumer_key",
          "Consumer Key: WooCommerce -> Settings -> Advanced -> REST API -> Add Key. Read/Write permission. Required.",
        ),
        t(
          "sites.guidance.wc_consumer_secret",
          "Consumer Secret: shown once, starts with cs_, save immediately. Required.",
        ),
        t(
          "sites.guidance.wc_no_extra_key",
          "No extra API key field exists for WooCommerce REST auth.",
        ),
        t(
          "sites.guidance.wc_media_username",
          "WordPress Username for media tools: only required for AI/media tools like upload_and_attach_to_product, attach_media_to_product, set_featured_image, generate_and_upload_image with attach_to_post. Optional.",
        ),
        t(
          "sites.guidance.wc_media_password",
          "WordPress Application Password for media tools: required only for WC media uploads to /wp/v2/media; Consumer Key/Secret do not work for that. Optional.",
        ),
        t(
          "sites.guidance.bridge_version",
          "Airano MCP Bridge v2.11.0+ is recommended for companion-backed tools.",
        ),
        t(
          "sites.guidance.bridge_lag",
          "The WordPress.org plugin page can lag behind repository builds while publishing/review completes; do not assume the newest repo feature is already available there.",
        ),
        t(
          "sites.guidance.companion_copy",
          "Airano MCP Bridge — companion plugin (optional but recommended). Installing it unlocks larger uploads, unified site-health snapshot, cache purge, transient flush, bulk meta writes, structured export, capability probe, and audit-hook webhooks. Without it, basic tools still work but these features remain unavailable.",
        ),
      ],
    };
  }
  if (pluginType === "gmail") {
    return {
      title: t("sites.guidance.gmail_setup_title", "Gmail setup (manual OAuth)"),
      items: [
        t(
          "sites.guidance.gmail_gcp",
          "In Google Cloud Console: create a project, enable the Gmail API, set up OAuth consent screen (External, Testing mode), add your Google email as a test user.",
        ),
        t(
          "sites.guidance.gmail_desktop_client",
          "Create an OAuth client ID of type Desktop app (NOT Web app). Note the Client ID (ends in .apps.googleusercontent.com) and Client Secret (GOCSPX-…).",
        ),
        t(
          "sites.guidance.gmail_bootstrap",
          "Run: python plugins/gmail/bootstrap/get_refresh_token.py --client-id <ID> --client-secret <SECRET> on a machine with a browser. It opens Google's consent screen and prints a long-lived refresh token.",
        ),
        t(
          "sites.guidance.gmail_paste",
          "Paste the Client ID, Client Secret, and Refresh Token into the fields below. Use https://gmail.googleapis.com as the Site URL (the plugin ignores it; the dashboard requires a URL).",
        ),
        t(
          "sites.guidance.gmail_scope",
          "Scope requested: gmail.modify (read + manage: list/get/search/labels/attachments, mark read/unread, trash). gmail.send is not requested yet.",
        ),
      ],
    };
  }
  if (pluginType === "google_search_console") {
    return {
      title: t("sites.guidance.google_oauth_title", "Google Search Console setup"),
      items: [
        t(
          "sites.guidance.google_oauth_gcp",
          "Enable the Google Search Console API in your Google Cloud Console → APIs & Services → Enable APIs & Services.",
        ),
        t(
          "sites.guidance.google_oauth_redirect",
          "Add your MCPHub instance's callback URL to the OAuth client's Authorized redirect URIs in Google Cloud Console. The URL is: {PUBLIC_URL}/oauth/site/callback",
        ),
        t(
          "sites.guidance.google_oauth_consent",
          "Keep the OAuth consent screen in Testing mode and add your Google account as a test user. Sensitive scopes work without Google verification in Testing mode.",
        ),
        t(
          "sites.guidance.google_oauth_unverified",
          "When authorizing, Google shows a 'Google hasn't verified this app' warning. Click Advanced → Go to app (unsafe) to continue. This is expected for apps in Testing mode and is safe — only accounts you add as test users can authorize.",
        ),
        t(
          "sites.guidance.google_oauth_env",
          "Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables on the MCPHub server to match your GCP OAuth client.",
        ),
      ],
    };
  }
  return null;
}

function supportsAiImageGeneration(pluginType: string): boolean {
  return pluginType === "wordpress" || pluginType === "woocommerce";
}

// Replaces the legacy `/dashboard-legacy/sites/add` and
// `/dashboard-legacy/sites/:id/edit` Jinja round-trips with a
// native SPA dialog. On edit, credentials are NOT prefilled (the API never
// returns them); leave the field blank to keep the existing secret, or
// type a new value to replace it. We pass credentials as a partial object
// so unset fields are preserved server-side (PATCH semantics).
export function SiteFormDialog({
  mode,
  site,
  onCancel,
  onDone,
}: {
  mode: Mode;
  site?: Site;
  onCancel: () => void;
  onDone: () => void;
}) {
  const t = useT();
  const lang = useUiStore((s) => s.lang);
  const setToast = useUiStore((s) => s.setToast);

  const plugins = usePluginCatalog();
  const create = useCreateSite();
  const update = useUpdateSite(site?.id ?? "");

  const [pluginType, setPluginType] = useState<string>(site?.plugin_type ?? "");
  const [alias, setAlias] = useState<string>(site?.alias ?? "");
  const [url, setUrl] = useState<string>(site?.url ?? "");
  const [creds, setCreds] = useState<Record<string, string>>({});
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Default the plugin type to the first public one once the catalog loads
  // (creating mode only — edit mode locks the type).
  useEffect(() => {
    if (mode !== "create") return;
    if (pluginType) return;
    if (!plugins.data || plugins.data.length === 0) return;
    setPluginType(plugins.data[0].type);
  }, [mode, pluginType, plugins.data]);

  const currentPlugin = useMemo(
    () => (plugins.data ?? []).find((p) => p.type === pluginType),
    [plugins.data, pluginType],
  );
  const guidance = useMemo(() => setupGuidance(pluginType, t), [pluginType, t]);
  const showAiImageSetup = supportsAiImageGeneration(pluginType);
  // Plugins with a fixed third-party API base (Cloudflare, …) don't need a
  // user-entered URL — the backend catalog sends the fixed value.
  const fixedUrl = currentPlugin?.fixedUrl;
  // OAuth plugins: no static credential fields — show "Connect with Google" instead.
  const isOAuthPlugin = OAUTH_PLUGIN_TYPES.has(pluginType);
  const initOAuth = useInitSiteOAuth();
  const [oauthPending, setOauthPending] = useState(false);
  // Visible credential fields exclude ``internal`` fields (auto-managed).
  const fields: PluginFieldDef[] = (currentPlugin?.fields ?? []).filter(
    (f) => !f.internal,
  );
  const advancedFields = fields.filter((f) => f.advanced);
  const requiredFieldsMissing =
    !isOAuthPlugin &&
    mode === "create" &&
    fields.filter((f) => f.required).some((f) => !creds[f.name]?.trim());
  const baseFieldsMissing =
    mode === "create" && (!alias.trim() || (!fixedUrl && !url.trim()) || !pluginType);

  const onSubmit = async () => {
    if (submitting) return;
    setError(null);
    setSubmitting(true);
    try {
      // Drop blank credential fields — on edit, the backend keeps the
      // stored value when the field is omitted from the PATCH payload.
      const cleanedCreds: Record<string, string> = {};
      if (!isOAuthPlugin) {
        Object.entries(creds).forEach(([k, v]) => {
          if (v && v.trim()) cleanedCreds[k] = v.trim();
        });
      }

      if (mode === "create") {
        const result = await create.mutateAsync({
          plugin_type: pluginType,
          alias: alias.trim(),
          url: (fixedUrl ?? url.trim()).replace(/\/+$/, ""),
          credentials: cleanedCreds,
        });
        // For OAuth plugins: after creating the site, initiate the OAuth flow.
        if (isOAuthPlugin && result?.id) {
          setToast(t("sites.oauth.pending", "Awaiting authorization"));
          try {
            const oauthResult = await initOAuth.mutateAsync(result.id);
            // Redirect to Google OAuth consent screen
            window.location.href = oauthResult.auth_url;
            return; // Don't close dialog — browser is redirecting
          } catch (oauthErr: any) {
            const msg = oauthErr?.body?.error ?? oauthErr?.message ?? String(oauthErr);
            setError(msg);
            setSubmitting(false);
            return;
          }
        }
        setToast(t("sites.toast_created", "Site created"));
      } else {
        // Edit: PATCH /api/sites/{id}. URL + alias may change; credentials
        // only update when the user types something into a field.
        await update.mutateAsync({
          alias: alias.trim() || undefined,
          url: url.trim() || undefined,
          credentials: Object.keys(cleanedCreds).length > 0 ? cleanedCreds : undefined,
        });
        setToast(t("sites.toast_updated", "Site updated"));
      }
      onDone();
    } catch (e: any) {
      const msg = e?.body?.error ?? e?.message ?? String(e);
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="dialog-backdrop" style={backdropStyle} onClick={onCancel}>
      <div
        className="dialog"
        style={dialogStyle}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
      >
        <Card style={{ width: "100%" }}>
          <div style={headerStyle}>
            <div className="h-2" style={{ margin: 0 }}>
              {mode === "create"
                ? t("sites.dialog_add_title", "Add a site")
                : t("sites.dialog_edit_title", "Edit site")}
            </div>
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={onCancel}
              aria-label={t("cancel", "Cancel")}
              style={{ padding: 6 }}
            >
              <Icons.x style={{ width: 16, height: 16 }} />
            </button>
          </div>

          <div style={bodyStyle}>
            {/* Plugin picker — locked on edit since changing plugin_type
                would invalidate stored credentials. */}
            <div className="field">
              <label>{t("sites.field_plugin_type", "Plugin")}</label>
              {plugins.isLoading ? (
                <div className="shimmer" style={{ height: 36, borderRadius: 8 }} />
              ) : mode === "edit" ? (
                <input
                  className="input"
                  value={currentPlugin?.name ?? pluginType}
                  disabled
                />
              ) : (
                <select
                  className="input"
                  value={pluginType}
                  onChange={(e) => {
                    setPluginType(e.target.value);
                    setCreds({});
                  }}
                  disabled={submitting}
                >
                  {(plugins.data ?? []).map((p) => (
                    <option key={p.type} value={p.type}>
                      {p.name}
                    </option>
                  ))}
                </select>
              )}
            </div>

            {guidance ? (
              <div className="alert alert-info" style={guidanceStyle}>
                <Icons.info style={{ width: 16, height: 16, flexShrink: 0, marginTop: 2 }} />
                <div>
                  <div style={{ fontWeight: 600, marginBottom: 6 }}>{guidance.title}</div>
                  <ul style={guidanceListStyle}>
                    {guidance.items.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
              </div>
            ) : null}

            {showAiImageSetup ? (
              <div className="alert alert-info" style={aiSetupStyle}>
                <Icons.spark style={{ width: 16, height: 16, flexShrink: 0, marginTop: 2 }} />
                <div>
                  <div style={{ fontWeight: 600, marginBottom: 6 }}>
                    {t("sites.ai_image.title", "AI Image Generation")}
                  </div>
                  <div className="caption" style={{ color: "var(--text-muted)" }}>
                    {mode === "edit" && site?.id
                      ? t(
                          "sites.ai_image.edit_body",
                          "Image generation is configured per service in Tool access. Add an OpenAI, Stability AI, Replicate, or OpenRouter key there; OpenRouter can also use a default image model.",
                        )
                      : t(
                          "sites.ai_image.create_body",
                          "After creating this service, open Tool access to add an OpenAI, Stability AI, Replicate, or OpenRouter key. The image generation tool stays unavailable until a provider key is saved and the service connection is healthy.",
                        )}
                  </div>
                  {mode === "edit" && site?.id ? (
                    <a
                      className="btn btn-secondary btn-sm"
                      href={`/dashboard/sites/${site.id}/tools`}
                      style={{ marginTop: 10, alignSelf: "flex-start" }}
                    >
                      {t("sites.ai_image.open_tools", "Open AI Image Generation settings")}
                    </a>
                  ) : null}
                </div>
              </div>
            ) : null}

            <div className="field">
              <label>{t("sites.field_alias", "Alias")}</label>
              <input
                className="input"
                value={alias}
                onChange={(e) => setAlias(e.target.value)}
                placeholder={t("sites.alias_placeholder", "short-id-for-this-site")}
                disabled={submitting}
              />
              <div className="caption" style={{ marginTop: 4 }}>
                {t(
                  "sites.alias_hint",
                  "Short identifier the AI sees as `site=…`. Stick to lowercase letters, digits, and dashes.",
                )}
              </div>
            </div>

            <div className="field">
              <label>{t("sites.field_url", "URL")}</label>
              {fixedUrl ? (
                <>
                  <input className="input" value={fixedUrl} disabled />
                  <div className="caption" style={{ marginTop: 4 }}>
                    {t(
                      "sites.url_fixed_hint",
                      "Fixed API base for this plugin — set automatically.",
                    )}
                  </div>
                </>
              ) : (
                <input
                  className="input"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://example.com"
                  disabled={submitting}
                />
              )}
            </div>

            {/* Credential fields per plugin — hidden for OAuth plugins */}
            {isOAuthPlugin ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                <div className="alert alert-info" style={guidanceStyle}>
                  <Icons.info style={{ width: 16, height: 16, flexShrink: 0, marginTop: 2 }} />
                  <div>
                    <div style={{ fontWeight: 600, marginBottom: 6 }}>
                      {t("sites.oauth.connect_google", "Connect with Google")}
                    </div>
                    <div className="caption" style={{ color: "var(--text-muted)" }}>
                      {mode === "edit" && site?.status === "reauth_required"
                        ? t(
                            "sites.oauth.status_reauth_required_desc",
                            "The OAuth refresh token is no longer valid. Re-authorize to reconnect.",
                          )
                        : t(
                            "sites.oauth.pending_desc",
                            'Click "Connect with Google" to authorize this site.',
                          )}
                    </div>
                    <div className="caption" style={{ color: "var(--text-subtle)", marginTop: 8 }}>
                      {t(
                        "sites.oauth.unverified_app_note",
                        "Google will show a 'Google hasn't verified this app' warning because this app uses sensitive scopes (Gmail/Search Console) and is in Testing mode. Click Advanced → Go to app (unsafe) to continue. This is safe — only your Google account is authorized.",
                      )}
                    </div>
                    {mode === "edit" && site?.id ? (
                      <button
                        type="button"
                        className="btn btn-primary btn-sm"
                        style={{ marginTop: 10, alignSelf: "flex-start" }}
                        onClick={async () => {
                          setOauthPending(true);
                          try {
                            const r = await initOAuth.mutateAsync(site.id);
                            window.location.href = r.auth_url;
                          } catch (oauthErr: any) {
                            const msg = oauthErr?.body?.error ?? oauthErr?.message ?? String(oauthErr);
                            setError(msg);
                            setOauthPending(false);
                          }
                        }}
                        disabled={oauthPending}
                      >
                        {oauthPending
                          ? t("sites.oauth.authorizing", "Authorizing…")
                          : t("sites.oauth.reauthorize", "Re-authorize")}
                      </button>
                    ) : null}
                  </div>
                </div>
              </div>
            ) : fields.length > 0 ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                <div className="eyebrow">{t("sites.credentials", "Credentials")}</div>
                {fields
                  .filter((f) => !f.advanced || showAdvanced)
                  .map((field) => (
                    <div key={field.name} className="field">
                      <label>
                        {field.label}
                        {field.required ? " *" : ""}
                      </label>
                      <input
                        className="input"
                        type={field.type === "password" ? "password" : "text"}
                        value={creds[field.name] ?? ""}
                        onChange={(e) =>
                          setCreds((prev) => ({ ...prev, [field.name]: e.target.value }))
                        }
                        placeholder={
                          mode === "edit" && !field.required
                            ? t("sites.cred_unchanged", "Leave blank to keep current")
                            : ""
                        }
                        disabled={submitting}
                      />
                      {field.hint ? (
                        <div className="caption" style={{ marginTop: 4 }}>
                          {field.hint}
                        </div>
                      ) : null}
                    </div>
                  ))}
                {advancedFields.length > 0 ? (
                  <Btn
                    variant="ghost"
                    size="sm"
                    onClick={() => setShowAdvanced((v) => !v)}
                    type="button"
                    style={{ alignSelf: lang === "fa" ? "flex-end" : "flex-start" }}
                  >
                    {advancedFieldsLabel(showAdvanced, currentPlugin?.name, fields, t)}
                  </Btn>
                ) : null}
              </div>
            ) : null}

            {error ? (
              <div className="alert alert-danger">
                <Icons.warning style={{ width: 16, height: 16, flexShrink: 0 }} />
                <div style={{ flex: 1, fontSize: 13 }}>{error}</div>
              </div>
            ) : null}
          </div>

          <div style={footerStyle}>
            <Btn variant="ghost" onClick={onCancel} disabled={submitting}>
              {t("cancel", "Cancel")}
            </Btn>
            <Btn
              variant="primary"
              onClick={onSubmit}
              disabled={
                submitting ||
                plugins.isLoading ||
                baseFieldsMissing ||
                requiredFieldsMissing
              }
            >
              {submitting
                ? "…"
                : mode === "create"
                  ? isOAuthPlugin
                    ? t("sites.oauth.connect_google", "Connect with Google")
                    : t("sites.dialog_add_submit", "Add site")
                  : t("sites.dialog_edit_submit", "Save changes")}
            </Btn>
          </div>
        </Card>
      </div>
    </div>
  );
}

const backdropStyle: CSSProperties = {
  position: "fixed",
  inset: 0,
  background: "oklch(0.10 0.012 250 / 0.55)",
  backdropFilter: "blur(4px)",
  WebkitBackdropFilter: "blur(4px)",
  zIndex: 60,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  padding: 20,
  overflowY: "auto",
};

const dialogStyle: CSSProperties = {
  width: "min(720px, 100%)",
  maxHeight: "calc(100dvh - 40px)",
  display: "flex",
  flexDirection: "column",
};

const headerStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  padding: "18px 22px",
  borderBottom: "1px solid var(--border)",
};

const bodyStyle: CSSProperties = {
  padding: "20px 22px",
  display: "flex",
  flexDirection: "column",
  gap: 16,
  overflowY: "auto",
};

const guidanceStyle: CSSProperties = {
  alignItems: "flex-start",
  fontSize: 12,
  lineHeight: 1.5,
};

const guidanceListStyle: CSSProperties = {
  margin: 0,
  paddingInlineStart: 18,
  display: "flex",
  flexDirection: "column",
  gap: 4,
};

const aiSetupStyle: CSSProperties = {
  alignItems: "flex-start",
  fontSize: 12,
  lineHeight: 1.5,
};

const footerStyle: CSSProperties = {
  display: "flex",
  gap: 10,
  justifyContent: "flex-end",
  padding: "16px 22px",
  borderTop: "1px solid var(--border)",
};
