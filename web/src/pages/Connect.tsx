import { useEffect, useState, type CSSProperties } from "react";
import { Link, useLocation } from "react-router-dom";
import { Topbar } from "../components/Topbar";
import { Card, CardHead, Badge, CopyField, Step } from "../components/primitives";
import { Icons, type IconName } from "../components/icons";
import { useSession, useSiteTools, useSites, useUpdateSiteToolScope } from "../lib/queries";
import { useUiStore } from "../lib/store";
import { useT } from "../lib/i18n";
import type { Site } from "../lib/types";

type Client = {
  id: string;
  name: string;
  desc: string;
  icon: IconName;
  guide: "claude-ai" | "claude-desktop" | "cli" | "json" | "codex" | "oauth";
};

const CLIENTS: Client[] = [
  {
    id: "claude-ai",
    name: "Claude.ai Connectors",
    desc: "Browser · URL only",
    icon: "sparkles",
    guide: "claude-ai",
  },
  { id: "claude-desktop", name: "Claude Desktop", desc: "Desktop app · JSON config", icon: "command", guide: "claude-desktop" },
  { id: "claude-code", name: "Claude Code", desc: "CLI · Developer", icon: "terminal", guide: "cli" },
  { id: "github-codex", name: "Codex", desc: "config.toml · Remote HTTP", icon: "github", guide: "codex" },
  { id: "cursor", name: "Cursor", desc: "JSON config", icon: "command", guide: "json" },
  { id: "chatgpt", name: "ChatGPT", desc: "OAuth · Apps SDK", icon: "spark", guide: "oauth" },
  { id: "gemini", name: "Gemini CLI", desc: "CLI · Token", icon: "terminal", guide: "cli" },
  { id: "vscode", name: "VS Code", desc: "Extension · Preview", icon: "edit", guide: "json" },
  { id: "custom", name: "Custom client", desc: "Any MCP client", icon: "wrench", guide: "json" },
];

// Tile descriptions go through i18n; brand names stay verbatim.
function clientDesc(t: ReturnType<typeof useT>, id: string, fallback: string): string {
  return t(`connect.client.${id}.desc`, fallback);
}
function clientName(t: ReturnType<typeof useT>, id: string, fallback: string): string {
  // Only the "Custom client" entry has a translatable name; the rest are brands.
  if (id === "custom") return t("connect.client.custom.name", fallback);
  return fallback;
}

export function ConnectPage() {
  const t = useT();
  const [selected, setSelected] = useState<string>("claude-ai");
  const [siteAlias, setSiteAlias] = useState<string | undefined>();
  const location = useLocation();
  const sites = useSites();
  const session = useSession();
  // Real per-user URL needs the actual user_id; falls back to "me" so the
  // snippet still reads sensibly while the session is loading.
  const userId = session.data?.user_id ?? "me";

  const current = CLIENTS.find((c) => c.id === selected)!;

  // Pick the first site as default once loaded.
  useEffect(() => {
    if (!sites.data || sites.data.length === 0) return;
    const requested = new URLSearchParams(location.search).get("site") ?? undefined;
    if (requested && sites.data.some((s) => s.alias === requested)) {
      setSiteAlias(requested);
      return;
    }
    if (!siteAlias) {
      setSiteAlias(sites.data[0].alias);
    }
  }, [sites.data, siteAlias, location.search]);

  const selectedSite = sites.data?.find((s) => s.alias === siteAlias);

  return (
    <>
      <Topbar crumbs={[t("workspace", "Workspace"), t("nav.connect", "Connect")]} />
      <div className="page-pad">
        <div className="page-head">
          <h1 className="h-1" style={{ margin: 0 }}>
            {t("connect_client", "Connect an AI client")}
          </h1>
          <div className="body" style={{ color: "var(--text-muted)", marginTop: 6, maxWidth: 640 }}>
            {t(
              "connect.intro",
              "Choose a client below. You'll get a one-time link or config snippet. No tokens to paste by hand.",
            )}
          </div>
        </div>

        {!sites.isLoading && (sites.data ?? []).length === 0 ? (
          <Card style={{ marginBottom: 16 }}>
            <div style={{ padding: 20, display: "flex", gap: 12, alignItems: "flex-start" }}>
              <Icons.sites style={{ width: 18, height: 18, color: "var(--brand-400)", flexShrink: 0 }} />
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, marginBottom: 4 }}>
                  {t("connect.no_services_title", "Add a service before connecting clients")}
                </div>
                <div className="caption" style={{ marginBottom: 12 }}>
                  {t(
                    "connect.no_services_body",
                    "MCP clients need at least one WordPress, WooCommerce, Coolify, or other service to route tools to. Add your first service from Sites, then return here for the client URL and setup steps.",
                  )}
                </div>
                <Link to="/sites?create=1" className="btn btn-primary btn-sm">
                  <Icons.plus style={{ width: 12, height: 12 }} />
                  {t("add_site_short", "Add site")}
                </Link>
              </div>
            </div>
          </Card>
        ) : null}

        <div className="connect-grid">
          <div className="stack connect-list" style={{ gap: 8 }}>
            {CLIENTS.map((c) => {
              const Ic = Icons[c.icon];
              const active = selected === c.id;
              return (
                <button
                  key={c.id}
                  type="button"
                  className={`tile ${active ? "is-active" : ""}`}
                  onClick={() => setSelected(c.id)}
                >
                  <div
                    style={{
                      width: 34,
                      height: 34,
                      borderRadius: 8,
                      background: "var(--surface)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      border: "1px solid var(--border)",
                    }}
                  >
                    <Ic
                      style={{
                        width: 16,
                        height: 16,
                        color: active ? "var(--brand-400)" : "var(--text-muted)",
                      }}
                    />
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13.5, fontWeight: 500 }}>
                      {clientName(t, c.id, c.name)}
                    </div>
                    <div className="caption">{clientDesc(t, c.id, c.desc)}</div>
                  </div>
                  {active ? (
                    <Icons.check style={{ width: 14, height: 14, color: "var(--brand-400)" }} />
                  ) : null}
                </button>
              );
            })}
          </div>

          <div>
            <Card>
              <div
                style={{
                  padding: 24,
                  borderBottom: "1px solid var(--border)",
                  display: "flex",
                  gap: 14,
                  alignItems: "center",
                }}
              >
                <div
                  style={{
                    width: 48,
                    height: 48,
                    borderRadius: 10,
                    background: "oklch(from var(--brand-500) l c h / 0.1)",
                    border: "1px solid oklch(from var(--brand-500) l c h / 0.25)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  {(() => {
                    const Ic = Icons[current.icon];
                    return <Ic style={{ width: 22, height: 22, color: "var(--brand-400)" }} />;
                  })()}
                </div>
                <div style={{ flex: 1 }}>
                  <div className="h-2" style={{ margin: 0 }}>
                    {t("connect.connect_x", "Connect {name}").replace(
                      "{name}",
                      clientName(t, current.id, current.name),
                    )}
                  </div>
                  <div className="caption" style={{ marginTop: 2 }}>
                    {clientDesc(t, current.id, current.desc)}
                  </div>
                </div>
                {sites.data && sites.data.length > 0 && (
                  <label className="field connect-site-select">
                    <span>{t("connect.service_select_label", "Service")}</span>
                    <select
                      className="input"
                      value={siteAlias ?? ""}
                      onChange={(e) => setSiteAlias(e.target.value || undefined)}
                    >
                      {sites.data.map((s) => (
                        <option key={s.id} value={s.alias}>
                          {s.alias} · {s.plugin_type}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
              </div>

              {current.guide === "claude-ai" ? <ClaudeAiFlow alias={siteAlias} userId={userId} /> : null}
              {current.guide === "claude-desktop" ? <ClaudeDesktopFlow alias={siteAlias} userId={userId} /> : null}
              {current.guide === "cli" ? <CLIFlow alias={siteAlias} userId={userId} /> : null}
              {current.guide === "json" ? (
                <JsonFlow alias={siteAlias} userId={userId} name={current.name} />
              ) : null}
              {current.guide === "codex" ? <CodexFlow alias={siteAlias} userId={userId} /> : null}
              {current.guide === "oauth" ? <ChatGptFlow alias={siteAlias} userId={userId} /> : null}
            </Card>

            <SiteScopeCard site={selectedSite} />
          </div>
        </div>
      </div>
    </>
  );
}

// ---------- Per-site Tool Access tier picker (replaces dummy ScopeGroup) ----------
// Tiers mirror _VALID_TOOL_SCOPES in core/dashboard/routes.py. Destructive
// treatment per F.19.2.3: install + read:sensitive = amber, admin = red.

type TierInfo = { value: string; label: string; hint: string; danger?: boolean; warning?: boolean };

const SITE_TOOL_TIERS: TierInfo[] = [
  { value: "read", label: "Read", hint: "Listing and inspection only." },
  {
    value: "read:sensitive",
    label: "Read sensitive",
    hint: "Adds backups, env vars, and other privacy-bearing reads.",
    warning: true,
  },
  { value: "deploy", label: "Deploy", hint: "Trigger deployments and lifecycle, no edits." },
  { value: "editor", label: "Editor", hint: "Pages, posts, content edits (wordpress_specialist F.19.5)." },
  {
    value: "settings",
    label: "Settings",
    hint: "Options, permalinks, identity, cron (wordpress_specialist F.19.6).",
  },
  {
    value: "install",
    label: "Installer",
    hint: "Install plugins / themes from the directory. Treat as elevated.",
    warning: true,
  },
  { value: "write", label: "Write", hint: "Create / update / delete resources and configuration." },
  {
    value: "admin",
    label: "Admin",
    hint: "Full system control including destructive operations.",
    danger: true,
  },
  { value: "custom", label: "Custom", hint: "Toggle individual tools manually after picking this." },
];

function SiteScopeCard({ site }: { site: Site | undefined }) {
  const t = useT();
  const update = useUpdateSiteToolScope();
  const setToast = useUiStore((s) => s.setToast);
  const lang = useUiStore((s) => s.lang);
  const siteTools = useSiteTools(site?.id);
  const current = site?.tool_scope ?? "admin";
  const hasPluginPresets = !!siteTools.data?.scope_presets?.length;
  const tiers: TierInfo[] =
    siteTools.data?.scope_presets?.map((preset) => ({
      value: preset.value,
      label: lang === "fa" && preset.label_fa ? preset.label_fa : preset.label,
      hint: lang === "fa" && preset.hint_fa ? preset.hint_fa : preset.hint,
      danger: preset.value === "admin",
      warning: preset.value === "install" || preset.value === "read:sensitive",
    })) ?? SITE_TOOL_TIERS;

  const onPick = async (scope: string) => {
    if (!site || scope === current) return;
    const ok = window.confirm(
      t(
        "connect.confirm_scope_change",
        'Change tool access for "{site}" from "{from}" to "{to}"?',
      )
        .replace("{site}", site.alias)
        .replace("{from}", current)
        .replace("{to}", scope),
    );
    if (!ok) return;
    try {
      await update.mutateAsync({ siteId: site.id, scope });
      setToast(
        t("connect.toast.scope_updated", "Tool access updated to {scope}").replace(
          "{scope}",
          scope,
        ),
      );
    } catch (e: any) {
      setToast(t("connect.toast.scope_failed", "Update failed: {error}").replace("{error}", e.message));
    }
  };

  const selectedTier = tiers.find((s) => s.value === current);

  return (
    <Card style={{ marginTop: 16 }}>
      <CardHead
        icon="shield"
        title={t("connect.tool_access", "Tool Access")}
        subtitle={
          site
            ? t(
                "connect.tool_access_service_subtitle",
                "Pick the access options this service actually supports.",
              ) + ` (${site.alias} · ${site.plugin_type})`
            : t("connect.tool_access_pick_site", "Select a site above to manage tool access.")
        }
      />
      <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 12 }}>
        <div style={tierGridStyle}>
          {tiers.map((tier) => {
            const active = tier.value === current;
            const pending = update.isPending && update.variables?.scope === tier.value;
            return (
              <button
                type="button"
                key={tier.value}
                disabled={!site || update.isPending}
                onClick={() => onPick(tier.value)}
                style={tierTileStyle(active, tier)}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <span style={{ fontWeight: 500 }}>
                    {hasPluginPresets ? tier.label : t(`tier.${tier.value.replace(":", "_")}`, tier.label)}
                  </span>
                  <span style={{ display: "inline-flex", gap: 6, alignItems: "center" }}>
                    {tier.danger ? (
                      <Badge variant="danger" className="badge-fixed">
                        {t("badge.admin", "admin")}
                      </Badge>
                    ) : tier.warning ? (
                      <Badge variant="warning" className="badge-fixed">
                        {t("badge.elevated", "elevated")}
                      </Badge>
                    ) : null}
                    {active ? (
                      <Icons.check style={{ width: 14, height: 14, color: "var(--brand-400)" }} />
                    ) : null}
                    {pending ? <span className="caption">…</span> : null}
                  </span>
                </div>
                <div className="caption" style={{ marginTop: 4 }}>
                  {hasPluginPresets
                    ? tier.hint
                    : t(`tier.${tier.value.replace(":", "_")}.hint`, tier.hint)}
                </div>
              </button>
            );
          })}
        </div>
        {selectedTier?.danger ? (
          <div className="alert alert-danger">
            <Icons.warning style={{ width: 16, height: 16, flexShrink: 0 }} />
            <div style={{ flex: 1, fontSize: 13 }}>
              {t(
                "connect.tier.admin_warning",
                "This service's highest tier exposes destructive or administrative operations. Anyone holding a token for this service can act with full privilege. Prefer a narrower option unless the agent needs every tool.",
              )}
            </div>
          </div>
        ) : selectedTier?.warning ? (
          <div className="alert alert-warning">
            <Icons.warning style={{ width: 16, height: 16, flexShrink: 0 }} />
            <div style={{ flex: 1, fontSize: 13 }}>
              {selectedTier.value === "install"
                ? t(
                    "connect.tier.install_warning",
                    "Installer is an elevated tier — installs run code from the WordPress / theme repository on your site. Use it only when the client needs that access.",
                  )
                : t(
                    "connect.tier.sensitive_warning",
                    "Sensitive reads is an elevated tier — sensitive reads include backups and env vars. Use it only when the client needs that access.",
                  )}
            </div>
          </div>
        ) : null}
      </div>
    </Card>
  );
}

const tierGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
  gap: 8,
};

function tierTileStyle(active: boolean, tier: TierInfo): CSSProperties {
  const accent = tier.danger
    ? "var(--danger)"
    : tier.warning
      ? "var(--warning, #d97706)"
      : "var(--brand-400)";
  return {
    textAlign: "left",
    padding: "10px 12px",
    background: active ? "var(--surface)" : "var(--bg-sunken)",
    border: `1px solid ${active ? accent : "var(--border)"}`,
    borderRadius: 8,
    cursor: "pointer",
    color: "var(--text)",
    fontSize: 13,
    transition: "background 120ms, border-color 120ms",
    opacity: active ? 1 : 0.92,
  };
}

function ClaudeAiFlow({ alias, userId }: { alias?: string; userId: string }) {
  const t = useT();
  const url = `${typeof window !== "undefined" ? window.location.origin : "https://your-hub"}${alias ? `/u/${userId}/${alias}/mcp` : "/mcp"}`;
  return (
    <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 24 }}>
      <Step n={1} title={t("connect.claude_ai.step1", "Use this Claude.ai connector URL")}>
        <div style={{ display: "flex", gap: 16, alignItems: "stretch" }}>
          <div style={{ flex: 1 }}>
            <p className="body-sm" style={{ color: "var(--text-muted)", margin: 0 }}>
              {t(
                "connect.claude.step1_body",
                "Paste this service URL into Claude.ai Connectors in your browser when it asks for your MCP endpoint.",
              )}
            </p>
            <div style={{ marginTop: 14 }}>
              <CopyField value={url} />
            </div>
            <div className="alert alert-info" style={{ marginTop: 12 }}>
              <Icons.info style={{ width: 16, height: 16, flexShrink: 0 }} />
              <div style={{ flex: 1, fontSize: 13 }}>
                {t(
                  "connect.claude.connector_tip",
                  "Tip: You only need the URL above. When connecting, authenticate with an API Key or GitHub/Google.",
                )}
              </div>
            </div>
          </div>
        </div>
      </Step>
      <Step n={2} title={t("connect.claude.step2", "Approve in Claude.ai")} ghost>
        <p className="body-sm" style={{ color: "var(--text-muted)", margin: 0 }}>
          {t("connect.claude.step2_body_prefix", "Claude will show:")}{" "}
          <span
            className="mono"
            style={{ background: "var(--surface)", padding: "2px 6px", borderRadius: 4 }}
          >
            {t("connect.claude.prompt_text", "MCP Hub wants to access N tools")}
          </span>
          . {t("connect.claude.step2_body_suffix", "Approve to continue.")}
        </p>
      </Step>
      <Step n={3} title={t("connect.claude.step3", "You're connected")} ghost done>
        <p className="body-sm" style={{ color: "var(--text-muted)", margin: 0 }}>
          {t(
            "connect.claude.step3_body",
            "You'll see the new client appear on your Overview. Try asking Claude to list your sites.",
          )}
        </p>
      </Step>
    </div>
  );
}

function ClaudeDesktopFlow({ alias, userId }: { alias?: string; userId: string }) {
  const t = useT();
  const origin = typeof window !== "undefined" ? window.location.origin : "https://your-hub";
  const url = `${origin}${alias ? `/u/${userId}/${alias}/mcp` : "/mcp"}`;
  const desktopUrl = "claude://";
  const envName = alias
    ? `MCPHUB_${alias.replace(/[^a-zA-Z0-9]+/g, "_").toUpperCase()}_TOKEN`
    : "MCPHUB_TOKEN";
  const cfg = JSON.stringify(
    {
      mcpServers: {
        mcphub: {
          type: "streamableHttp",
          url,
          headers: {
            Authorization: `Bearer \${${envName}}`,
          },
        },
      },
    },
    null,
    2,
  );

  return (
    <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 20 }}>
      <Step n={1} title={t("connect.desktop.open_step", "Open Claude Desktop")}>
        <p className="body-sm" style={{ color: "var(--text-muted)", margin: 0 }}>
          {t(
            "connect.desktop.open_body",
            "Use this shortcut to switch into Claude Desktop, then return here if your app still needs the local MCP server config.",
          )}
        </p>
        <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 8, alignItems: "flex-start" }}>
          <a href={desktopUrl} className="btn btn-primary btn-sm">
            {t("connect.desktop.open_button", "Open Claude Desktop")}
            <Icons.arrow style={{ width: 12, height: 12 }} />
          </a>
          <div className="caption">
            {t(
              "connect.desktop.open_fallback",
              "If your browser does not open the desktop app, continue with the config steps below.",
            )}
          </div>
        </div>
      </Step>
      <Step n={2} title={t("connect.desktop.step1", "Create or select an MCP Hub API key")} ghost>
        <p className="body-sm" style={{ color: "var(--text-muted)", margin: 0 }}>
          {t(
            "connect.desktop.step1_body",
            "Claude Desktop uses a local config file. Store the mhu_ key in an environment variable instead of pasting it directly into JSON.",
          )}
        </p>
        <div style={{ marginTop: 12 }}>
          <CopyField value={`export ${envName}=mhu_your_key_here`} />
        </div>
      </Step>
      <Step n={3} title={t("connect.desktop.step2", "Add this server to claude_desktop_config.json")} ghost>
        <CopyField value={cfg} />
        <div className="caption" style={{ marginTop: 8 }}>
          {t(
            "connect.desktop.config_paths",
            "macOS: ~/Library/Application Support/Claude/claude_desktop_config.json · Windows: %APPDATA%\\Claude\\claude_desktop_config.json",
          )}
        </div>
      </Step>
      <Step n={4} title={t("connect.desktop.step3", "Restart Claude Desktop and verify tools")} ghost done>
        <p className="body-sm" style={{ color: "var(--text-muted)", margin: 0 }}>
          {t(
            "connect.desktop.step3_body",
            "Quit Claude Desktop completely, reopen it, then ask Claude to list the available MCP Hub tools for the selected service.",
          )}
        </p>
      </Step>
      <div className="alert alert-info">
        <Icons.info style={{ width: 16, height: 16, flexShrink: 0 }} />
        <div style={{ flex: 1, fontSize: 13 }}>
          {t(
            "connect.desktop.oauth_note",
            "Claude.ai Connectors are browser-based and only need the URL. Claude Desktop needs this local JSON config plus a bearer token.",
          )}
        </div>
      </div>
    </div>
  );
}

function CLIFlow({ alias, userId }: { alias?: string; userId: string }) {
  const t = useT();
  const url = `${typeof window !== "undefined" ? window.location.origin : "https://your-hub"}${alias ? `/u/${userId}/${alias}/mcp` : "/mcp"}`;
  return (
    <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 20 }}>
      <Step n={1} title={t("connect.cli.step1", "Run this in your terminal")}>
        <div className="term">
          <div className="term-head">
            <span className="dot" style={{ background: "#ff5f57" }} />
            <span className="dot" style={{ background: "#febc2e" }} />
            <span className="dot" style={{ background: "#28c840" }} />
          </div>
          <div className="term-body" dir="ltr">
            <span className="com"># install + connect</span>
            {"\n"}
            <span className="kw">$</span> claude mcp add mcphub \{"\n"}
            {"    "}--transport sse \{"\n"}
            {"    "}<span className="str">{url}</span>
          </div>
        </div>
      </Step>
      <Step n={2} title={t("connect.cli.step2", "Verify")} ghost done>
        <div className="term">
          <div className="term-head">
            <span className="dot" style={{ background: "#28c840" }} />
          </div>
          <div className="term-body" dir="ltr">
            <span className="kw">$</span> claude mcp list{"\n"}
            <span className="com">mcphub  connected  N tools  healthy</span>
          </div>
        </div>
      </Step>
    </div>
  );
}

function JsonFlow({ alias, userId, name }: { alias?: string; userId: string; name: string }) {
  const t = useT();
  const url = `${typeof window !== "undefined" ? window.location.origin : "https://your-hub"}${alias ? `/u/${userId}/${alias}/mcp` : "/mcp"}`;
  const cfg = JSON.stringify(
    {
      mcpServers: {
        mcphub: {
          url,
          auth: "bearer",
          token: "mhu_•••••••",
        },
      },
    },
    null,
    2,
  );
  return (
    <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 20 }}>
      <div className="alert alert-info">
        <Icons.info style={{ width: 16, height: 16, flexShrink: 0 }} />
        <div>
          <div style={{ fontWeight: 500, color: "var(--text)" }}>
            {t("connect.json.paste_into", "Paste this into {name}'s MCP config").replace(
              "{name}",
              name,
            )}
          </div>
          <div className="caption" style={{ marginTop: 2 }}>
            {t(
              "connect.json.location_hint",
              "Settings → MCP Servers · file path differs per client",
            )}
          </div>
        </div>
      </div>
      <CopyField value={cfg} />
      <div className="alert alert-warning">
        <Icons.warning style={{ width: 16, height: 16, flexShrink: 0 }} />
        <div>
          <div style={{ fontWeight: 500, color: "var(--text)" }}>
            {t("connect.json.create_key_title", "Create an API key first")}
          </div>
          <div className="caption" style={{ marginTop: 2 }}>
            {t(
              "connect.json.create_key_body",
              "Generate an API key from API Keys, copy it when it is shown once, then replace mhu_••••••• in this config. You can delete and recreate keys from API Keys.",
            )}
          </div>
          <Link to="/api-keys" className="btn btn-secondary btn-sm" style={{ marginTop: 10 }}>
            <Icons.key style={{ width: 12, height: 12 }} />
            {t("nav.api_keys", "API Keys")}
          </Link>
        </div>
      </div>
      <div style={{ display: "flex", gap: 10 }}>
        <Badge>{t("connect.json.compatible", "Compatible:")}</Badge>
        <Badge>Cursor</Badge>
        <Badge>VS Code</Badge>
        <Badge>{t("connect.json.custom_mcp", "Custom MCP")}</Badge>
      </div>
    </div>
  );
}

function CodexFlow({ alias, userId }: { alias?: string; userId: string }) {
  const t = useT();
  const origin = typeof window !== "undefined" ? window.location.origin : "https://your-hub";
  const url = `${origin}${alias ? `/u/${userId}/${alias}/mcp` : "/mcp"}`;
  const envName = alias
    ? `MCPHUB_${alias.replace(/[^a-zA-Z0-9]+/g, "_").toUpperCase()}_TOKEN`
    : "MCPHUB_TOKEN";
  const codexToml = `[mcp_servers.mcphub]\nurl = "${url}"\nbearer_token_env_var = "${envName}"`;
  const claudeJson = JSON.stringify(
    {
      mcpServers: {
        mcphub: {
          type: "streamableHttp",
          url,
          headers: {
            Authorization: `Bearer \${${envName}}`,
          },
        },
      },
    },
    null,
    2,
  );
  const exportSnippet = `export ${envName}=mhu_your_key_here\ncodex mcp list`;

  return (
    <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 20 }}>
      <div className="alert alert-info">
        <Icons.info style={{ width: 16, height: 16, flexShrink: 0 }} />
        <div>
          <div style={{ fontWeight: 500, color: "var(--text)" }}>
            {t("connect.codex.env_var_title", "Codex reads the token from an environment variable")}
          </div>
          <div className="caption" style={{ marginTop: 2 }}>
            {t(
              "connect.codex.env_var_body",
              "Set bearer_token_env_var to the variable name, not the mhu_ token value. Restart Codex after adding new environment variables.",
            )}
          </div>
        </div>
      </div>

      <Step n={1} title={t("connect.codex.step1", "Export the token for this service")}>
        <CopyField value={exportSnippet} />
      </Step>

      <Step n={2} title={t("connect.codex.step2", "Add this to ~/.codex/config.toml")} ghost>
        <CopyField value={codexToml} />
      </Step>

      <Step n={3} title={t("connect.codex.step3", "Claude-style JSON is different")} ghost>
        <CopyField value={claudeJson} />
        <div className="caption" style={{ marginTop: 8 }}>
          {t(
            "connect.codex.claude_difference",
            "Use the TOML block for Codex. The JSON block is shown only to clarify how Claude-style headers differ.",
          )}
        </div>
      </Step>

      <div className="alert alert-warning">
        <Icons.warning style={{ width: 16, height: 16, flexShrink: 0 }} />
        <div>
          <div style={{ fontWeight: 500, color: "var(--text)" }}>
            {t("connect.codex.troubleshooting_title", "Troubleshooting online code environments")}
          </div>
          <div className="caption" style={{ marginTop: 2 }}>
            {t(
              "connect.codex.troubleshooting_body",
              "Run codex mcp list, verify bubblewrap/bwrap is available, and restart the Codex session after changing env vars. Missing sandbox dependencies can look like MCP auth failures.",
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function ChatGptFlow({ alias, userId }: { alias?: string; userId: string }) {
  const t = useT();
  const url = `${typeof window !== "undefined" ? window.location.origin : "https://your-hub"}${alias ? `/u/${userId}/${alias}/mcp` : "/mcp"}`;
  return (
    <div style={{ padding: 24, display: "flex", flexDirection: "column", gap: 20 }}>
      <Step n={1} title={t("connect.chatgpt.step1", "Use this ChatGPT connector URL")}>
        <p className="body-sm" style={{ color: "var(--text-muted)", margin: 0 }}>
          {t(
            "connect.chatgpt.step1_body",
            "Copy this service URL. ChatGPT only needs the MCP endpoint URL; MCP Hub handles authentication when ChatGPT connects.",
          )}
        </p>
        <div style={{ marginTop: 14 }}>
          <CopyField value={url} />
        </div>
        <div className="alert alert-info" style={{ marginTop: 12 }}>
          <Icons.info style={{ width: 16, height: 16, flexShrink: 0 }} />
          <div style={{ flex: 1, fontSize: 13 }}>
            {t(
              "connect.chatgpt.connector_tip",
              "Tip: You only need the URL above. When connecting, authenticate with an API Key or GitHub/Google.",
            )}
          </div>
        </div>
      </Step>
      <Step n={2} title={t("connect.chatgpt.step2", "Enable Developer mode in ChatGPT")} ghost>
        <p className="body-sm" style={{ color: "var(--text-muted)", margin: 0 }}>
          {t(
            "connect.chatgpt.step2_body",
            "In chatgpt.com settings, enable Developer mode first. Then open Apps and choose Create app.",
          )}
        </p>
      </Step>
      <Step n={3} title={t("connect.chatgpt.step3", "Create the ChatGPT app")} ghost done>
        <p className="body-sm" style={{ color: "var(--text-muted)", margin: 0 }}>
          {t(
            "connect.chatgpt.step3_body",
            "Set Authorization to OAuth mode, which is the default, then paste the URL above as the MCP server URL and finish the app setup.",
          )}
        </p>
      </Step>
    </div>
  );
}
