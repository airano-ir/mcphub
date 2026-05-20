import { useEffect, useState, type CSSProperties } from "react";
import { Topbar } from "../components/Topbar";
import { Card, CardHead, Avatar, Btn, Seg, Badge } from "../components/primitives";
import { Icons, type IconName } from "../components/icons";
import {
  useManagedSettings,
  useResetSettings,
  useSaveSetting,
  useSession,
  type ManagedSetting,
} from "../lib/queries";
import { useUiStore } from "../lib/store";
import { useT } from "../lib/i18n";

type Tab = "profile" | "appearance" | "limits" | "plugins" | "danger";

const PLUGIN_LIBRARY: { key: string; label: string; descriptionKey: string; description: string }[] = [
  {
    key: "wordpress",
    label: "WordPress",
    descriptionKey: "settings.plugin.wordpress",
    description: "Posts, pages, media, comments.",
  },
  {
    key: "woocommerce",
    label: "WooCommerce",
    descriptionKey: "settings.plugin.woocommerce",
    description: "Products, orders, customers, reports.",
  },
  {
    key: "wordpress_specialist",
    label: "WordPress Specialist",
    descriptionKey: "settings.plugin.wordpress_specialist",
    description: "Companion-backed: blocks, theme files, plugins, DB.",
  },
  { key: "supabase", label: "Supabase", descriptionKey: "settings.plugin.supabase", description: "DB, auth, storage, functions." },
  { key: "openpanel", label: "OpenPanel", descriptionKey: "settings.plugin.openpanel", description: "Product analytics and event exports." },
  { key: "gitea", label: "Gitea", descriptionKey: "settings.plugin.gitea", description: "Repos, issues, PRs, releases." },
  { key: "n8n", label: "n8n", descriptionKey: "settings.plugin.n8n", description: "Workflows and executions." },
  { key: "coolify", label: "Coolify", descriptionKey: "settings.plugin.coolify", description: "Apps, deployments, servers, services." },
];

export function SettingsPage() {
  const t = useT();
  const session = useSession();
  const isAdmin = session.data?.is_admin ?? false;
  const [tab, setTab] = useState<Tab>("profile");

  const tabs: { id: Tab; label: string; icon: IconName; admin?: boolean }[] = [
    { id: "profile", label: t("settings.tab_profile", "Profile"), icon: "user" },
    { id: "appearance", label: t("settings.tab_appearance", "Appearance"), icon: "sparkles" },
    { id: "limits", label: t("settings.tab_limits", "Limits"), icon: "shield", admin: true },
    { id: "plugins", label: t("settings.tab_plugins", "Public plugin visibility"), icon: "plug", admin: true },
    { id: "danger", label: t("settings.tab_danger", "Danger zone"), icon: "warning", admin: true },
  ];
  const visible = tabs.filter((t) => !t.admin || isAdmin);

  return (
    <>
      <Topbar crumbs={[t("nav.account", "Account"), t("settings", "Settings")]} />
      <div className="page-pad">
        <div className="page-head">
          <h1 className="h-1" style={{ margin: 0 }}>
            {t("settings", "Settings")}
          </h1>
          <div className="body" style={{ color: "var(--text-muted)", marginTop: 6 }}>
            {t(
              "settings.intro",
              "Your profile, hub preferences, and integrations.",
            )}
            {isAdmin
              ? ` ${t("settings.intro_admin_suffix", "Admin-only sections are flagged in the sidebar.")}`
              : null}
          </div>
        </div>

        <div className="settings-grid">
          <div className="stack settings-tabs" style={{ gap: 2 }}>
            {visible.map((row) => {
              const Ic = Icons[row.icon];
              return (
                <button
                  key={row.id}
                  type="button"
                  className={`nav-item ${tab === row.id ? "is-active" : ""}`}
                  onClick={() => setTab(row.id)}
                >
                  <Ic />
                  <span>{row.label}</span>
                  {row.admin ? (
                    <Badge variant="warning" className="badge-fixed" style={{ marginLeft: "auto" }}>
                      {t("badge.admin_lc", "admin")}
                    </Badge>
                  ) : null}
                </button>
              );
            })}
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 16, minWidth: 0 }}>
            {tab === "profile" && <ProfileTab />}
            {tab === "appearance" && <AppearanceTab />}
            {tab === "limits" && isAdmin && <LimitsTab />}
            {tab === "plugins" && isAdmin && <PluginsTab />}
            {tab === "danger" && isAdmin && <DangerTab />}
          </div>
        </div>
      </div>
    </>
  );
}

// ---------- Profile ----------

function ProfileTab() {
  const t = useT();
  const { data: session } = useSession();
  return (
    <Card>
      <CardHead
        icon="user"
        title={t("settings.profile_title", "Profile")}
        subtitle={t("settings.profile_subtitle", "Used across the hub and for audit attribution")}
      />
      <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 16 }}>
        <div style={{ display: "flex", gap: 20, alignItems: "center" }}>
          <Avatar name={session?.name || session?.email || "User"} size={64} />
          <div style={{ flex: 1 }}>
            <div className="h-3">{session?.name ?? "—"}</div>
            <div className="caption">
              {session?.email ?? "—"}
              {session?.role ? ` · ${session.role}` : ""}
              {session?.type ? ` · ${session.type}` : ""}
            </div>
          </div>
          {session?.is_admin ? (
            <Badge variant="warning">{t("badge.admin", "Admin")}</Badge>
          ) : null}
        </div>
        <div className="settings-profile-grid">
          <ReadOnlyField label={t("settings.field_full_name", "Full name")} value={session?.name} />
          <ReadOnlyField label={t("settings.field_email", "Email")} value={session?.email} />
          <ReadOnlyField label={t("settings.field_session_type", "Session type")} value={session?.type} />
          <ReadOnlyField label={t("settings.field_role", "Role")} value={session?.role} />
        </div>
        <div className="caption">
          {t(
            "settings.profile_footnote",
            "Profile details come from your OAuth provider and aren't editable here. Sign out and reconnect to update them.",
          )}
        </div>
      </div>
    </Card>
  );
}

function ReadOnlyField({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="field">
      <label>{label}</label>
      <input className="input" value={value ?? ""} disabled />
    </div>
  );
}

// ---------- Appearance ----------

function AppearanceTab() {
  const t = useT();
  const { theme, setTheme, lang, setLang, brandHue, setBrandHue, density, setDensity } =
    useUiStore();
  const HUES: { value: number; label: string }[] = [
    { value: 205, label: "Cyan" },
    { value: 165, label: "Green" },
    { value: 290, label: "Purple" },
    { value: 30, label: "Amber" },
    { value: 0, label: "Red" },
  ];
  return (
    <Card>
      <CardHead
        icon="sparkles"
        title={t("settings.tab_appearance", "Appearance")}
        subtitle={t(
          "settings.appearance_subtitle",
          "Theme, language, brand hue, density. Changes apply immediately and persist locally.",
        )}
      />
      <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 18 }}>
        <SettingRow label={t("theme" as string, "Theme")}>
          <Seg
            value={theme}
            onChange={setTheme}
            options={[
              { value: "light", label: t("theme.light", "Light") },
              { value: "dark", label: t("theme.dark", "Dark") },
              { value: "system", label: t("theme.system", "System") },
            ]}
          />
        </SettingRow>
        <SettingRow label={t("language" as string, "Language")}>
          <Seg
            value={lang}
            onChange={setLang}
            options={[
              { value: "en", label: "English" },
              { value: "fa", label: "فارسی" },
            ]}
          />
        </SettingRow>
        <SettingRow label={t("settings.brand_color", "Brand color")}>
          <div style={{ display: "flex", gap: 8 }}>
            {HUES.map((h) => (
              <button
                key={h.value}
                type="button"
                onClick={() => setBrandHue(h.value)}
                title={h.label}
                aria-label={`Brand color ${h.label}`}
                style={{
                  width: 28,
                  height: 28,
                  borderRadius: "50%",
                  background: `oklch(0.74 0.14 ${h.value})`,
                  border: brandHue === h.value ? "2px solid var(--text)" : "2px solid transparent",
                  boxShadow: brandHue === h.value ? "0 0 0 2px var(--bg)" : "none",
                  cursor: "pointer",
                }}
              />
            ))}
          </div>
        </SettingRow>
        <SettingRow label={t("settings.density", "Density")}>
          <Seg
            value={String(density) as "0.85" | "1" | "1.1"}
            onChange={(v) => setDensity(parseFloat(v))}
            options={[
              { value: "0.85", label: "Compact" },
              { value: "1", label: "Default" },
              { value: "1.1", label: "Comfortable" },
            ]}
          />
        </SettingRow>
      </div>
    </Card>
  );
}

// ---------- Limits (admin) ----------

function LimitsTab() {
  const t = useT();
  const settings = useManagedSettings();
  const limits = (settings.data ?? []).filter((s) =>
    ["MAX_SITES_PER_USER", "USER_RATE_LIMIT_PER_MIN", "USER_RATE_LIMIT_PER_HR"].includes(s.key),
  );
  return (
    <Card>
      <CardHead
        icon="shield"
        title={t("settings.limits_title", "User limits")}
        subtitle={t(
          "settings.limits_subtitle",
          "Maximum sites and rate limits per registered user. Persists in the SQLite settings table.",
        )}
      />
      <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 14 }}>
        {settings.isLoading ? (
          <>
            <div className="shimmer" style={{ height: 56, borderRadius: 8 }} />
            <div className="shimmer" style={{ height: 56, borderRadius: 8 }} />
            <div className="shimmer" style={{ height: 56, borderRadius: 8 }} />
          </>
        ) : limits.length === 0 ? (
          <div className="caption">{t("settings.no_managed_limits", "No managed limits found.")}</div>
        ) : (
          limits.map((s) => <ManagedSettingRow key={s.key} setting={s} type="number" />)
        )}
      </div>
    </Card>
  );
}

// ---------- Plugins (admin) ----------

function PluginsTab() {
  const t = useT();
  const settings = useManagedSettings();
  const save = useSaveSetting();
  const setting = (settings.data ?? []).find((s) => s.key === "ENABLED_PLUGINS");
  const enabled = new Set(
    (setting?.value ?? "")
      .split(",")
      .map((p) => p.trim())
      .filter(Boolean),
  );

  const toggle = async (key: string) => {
    if (!setting) return;
    const next = new Set(enabled);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    await save.mutateAsync({ key: "ENABLED_PLUGINS", value: Array.from(next).join(",") });
  };

  return (
    <Card>
      <CardHead
        icon="plug"
        title={t("settings.plugins_title", "Public plugin visibility")}
        subtitle={t(
          "settings.plugins_subtitle",
          "Toggle which plugin types non-admin users can see. Admins always see everything.",
        )}
      />
      <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 8 }}>
        {settings.isLoading ? (
          <div className="shimmer" style={{ height: 200, borderRadius: 8 }} />
        ) : !setting ? (
          <div className="caption">
            {t("settings.plugins_unavailable", "ENABLED_PLUGINS setting not available.")}
          </div>
        ) : (
          <>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
              <div className="caption">
                {t("settings.source_label", "Source")}:{" "}
                <strong style={{ color: "var(--text)" }}>{setting.source}</strong>
                {" · "}
                {t("settings.default_label", "default")}:{" "}
                <span className="mono">{setting.default}</span>
              </div>
              <Btn
                variant="ghost"
                size="sm"
                onClick={() => save.mutate({ key: "ENABLED_PLUGINS", value: setting.default, action: "reset" })}
                disabled={save.isPending}
              >
                {t("settings.reset_default", "Reset to default")}
              </Btn>
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 8 }}>
              {PLUGIN_LIBRARY.map((p) => {
                const on = enabled.has(p.key);
                const pending = save.isPending && save.variables?.value?.includes(p.key) !== on;
                return (
                  <button
                    type="button"
                    key={p.key}
                    onClick={() => toggle(p.key)}
                    disabled={save.isPending}
                    style={pluginTileStyle(on)}
                  >
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span style={{ fontWeight: 500 }}>{p.label}</span>
                      <Badge variant={on ? "success" : "default"} dot={on}>
                        {on ? t("toggle.on", "on") : t("toggle.off", "off")}
                      </Badge>
                    </div>
                    <div className="caption" style={{ marginTop: 4 }}>
                      {t(p.descriptionKey, p.description)}
                    </div>
                    {pending ? (
                      <div className="caption" style={{ marginTop: 4 }}>
                        {t("status.saving", "saving…")}
                      </div>
                    ) : null}
                  </button>
                );
              })}
            </div>
          </>
        )}
      </div>
    </Card>
  );
}

// ---------- Danger ----------

function DangerTab() {
  const t = useT();
  const reset = useResetSettings();
  const setToast = useUiStore((s) => s.setToast);

  const onReset = async () => {
    const ok = window.confirm(t("settings.reset_all_confirm", "Reset all managed settings to environment/default values? This affects every user."));
    if (!ok) return;
    try {
      await reset.mutateAsync();
      setToast(t("settings.reset_all_done", "Managed settings reset"));
    } catch (e: any) {
      setToast(t("settings.reset_all_failed", "Reset failed: {error}").replace("{error}", e.message || "unknown"));
    }
  };

  return (
    <Card style={{ borderColor: "oklch(from var(--danger) l c h / 0.4)" }}>
      <CardHead
        icon="warning"
        title={t("settings.danger_title", "Danger zone")}
        subtitle={t(
          "settings.danger_subtitle",
          "Actions in this section affect every user of the hub. Confirm twice before acting.",
        )}
      />
      <div style={{ padding: 20, display: "flex", flexDirection: "column", gap: 14 }}>
        <div className="alert alert-warning" style={{ alignItems: "center" }}>
          <Icons.warning style={{ width: 16, height: 16, flexShrink: 0 }} />
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 500, color: "var(--text)" }}>
              {t("settings.reset_all_title", "Reset managed settings")}
            </div>
            <div className="caption" style={{ marginTop: 2 }}>
              {t(
                "settings.reset_all_body",
                "Delete database overrides for user limits and public plugin visibility. Environment values still win over defaults.",
              )}
            </div>
          </div>
          <Btn variant="danger" size="sm" onClick={onReset} disabled={reset.isPending}>
            {reset.isPending ? "…" : t("settings.reset_all_action", "Reset all managed settings")}
          </Btn>
        </div>
      </div>
    </Card>
  );
}

// ---------- Shared bits ----------

function SettingRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div
      className="setting-row"
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        gap: 16,
        padding: 12,
        border: "1px solid var(--border)",
        borderRadius: 8,
      }}
    >
      <div style={{ fontSize: 13, fontWeight: 500 }}>{label}</div>
      {children}
    </div>
  );
}

function ManagedSettingRow({ setting, type = "text" }: { setting: ManagedSetting; type?: "text" | "number" }) {
  const save = useSaveSetting();
  const t = useT();
  const lang = useUiStore((s) => s.lang);
  const [draft, setDraft] = useState(setting.value);
  const [hint, setHint] = useState<string | null>(null);

  // Reset local draft when the saved value changes (e.g. another tab edits).
  useEffect(() => {
    setDraft(setting.value);
  }, [setting.value]);

  const dirty = draft !== setting.value;

  const onSave = async () => {
    try {
      await save.mutateAsync({ key: setting.key, value: draft });
      setHint("Saved");
      setTimeout(() => setHint(null), 1500);
    } catch (e: any) {
      setHint(e.message || "Failed");
    }
  };

  const onReset = async () => {
    try {
      await save.mutateAsync({ key: setting.key, value: setting.default, action: "reset" });
      setHint("Reset to default");
      setTimeout(() => setHint(null), 1500);
    } catch (e: any) {
      setHint(e.message || "Failed");
    }
  };

  return (
    <div
      style={{
        padding: 12,
        border: "1px solid var(--border)",
        borderRadius: 8,
        display: "flex",
        flexDirection: "column",
        gap: 8,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
        <div>
          <div style={{ fontWeight: 500, fontSize: 13 }}>
            {lang === "fa" && setting.label_fa ? setting.label_fa : setting.label}
          </div>
          <div className="caption" style={{ marginTop: 2 }}>
            {lang === "fa" && setting.hint_fa ? setting.hint_fa : setting.hint}
          </div>
        </div>
        <Badge className="badge-fixed">{setting.source}</Badge>
      </div>
      <div style={{ display: "flex", gap: 8 }}>
        <input
          className="input"
          type={type}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          style={{ flex: 1, fontFamily: "var(--font-mono)" }}
        />
        <Btn variant="primary" size="sm" disabled={!dirty || save.isPending} onClick={onSave}>
          {save.isPending ? "…" : t("action.save", "Save")}
        </Btn>
        <Btn
          variant="ghost"
          size="sm"
          onClick={onReset}
          disabled={save.isPending || setting.value === setting.default}
        >
          {t("action.reset", "Reset")}
        </Btn>
      </div>
      {hint ? (
        <div className="caption" style={{ color: "var(--brand-400)" }}>
          {hint}
        </div>
      ) : null}
      <div className="caption">
        {t("settings.default_label", "default")}: <span className="mono">{setting.default}</span>
      </div>
    </div>
  );
}

function pluginTileStyle(active: boolean): CSSProperties {
  return {
    textAlign: "left",
    padding: "10px 12px",
    background: active ? "var(--surface)" : "var(--bg-sunken)",
    border: `1px solid ${active ? "var(--brand-400)" : "var(--border)"}`,
    borderRadius: 8,
    cursor: "pointer",
    color: "var(--text)",
    fontSize: 13,
    transition: "background 120ms, border-color 120ms",
  };
}
