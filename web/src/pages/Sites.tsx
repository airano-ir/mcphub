import { useEffect, useState, type CSSProperties } from "react";
import { Link } from "react-router-dom";
import { Topbar } from "../components/Topbar";
import { Card, Badge, Btn, Seg, EmptyState } from "../components/primitives";
import { Icons } from "../components/icons";
import { SiteFormDialog } from "../components/SiteFormDialog";
import { useDeleteSite, useSiteLimit, useSites, useTestSite } from "../lib/queries";
import { useUiStore } from "../lib/store";
import { useT } from "../lib/i18n";
import { fmtDateTime, fmtInt, normalizeSiteStatus } from "../lib/format";
import type { Lang } from "../lib/store";
import type { Site } from "../lib/types";

// Map tool_scope tier → Badge variant. Mirrors the F.19.2.3 destructive-tier
// treatment (install = amber, admin = red, everything else = default).
function tierBadgeVariant(scope: string | undefined): "default" | "warning" | "danger" {
  if (scope === "admin") return "danger";
  if (scope === "install" || scope === "read:sensitive") return "warning";
  return "default";
}

// Friendly display name for each plugin type. Mirrors the lookup the
// legacy Jinja list.html does via `plugin_names.get(...)`.
const PLUGIN_DISPLAY: Record<string, string> = {
  wordpress: "WordPress",
  woocommerce: "WooCommerce",
  wordpress_specialist: "WordPress (specialist)",
  gitea: "Gitea",
  n8n: "n8n",
  supabase: "Supabase",
  openpanel: "OpenPanel",
  appwrite: "Appwrite",
  directus: "Directus",
  coolify: "Coolify",
};

function formatTested(
  iso: string | null | undefined,
  lang: Lang,
  t: (k: string, fb?: string) => string,
): string {
  if (!iso) return t("never_tested", "Never tested");
  return `${t("last_tested", "Last tested")}: ${fmtDateTime(iso, lang)}`;
}

function emptyCopy(
  filter: "all" | "healthy" | "untested",
  search: string,
  t: (k: string, fb?: string) => string,
): { title: string; body: string; showAction: boolean } {
  if (search.trim()) {
    return {
      title: t("sites.empty_search_title", "No sites match this search"),
      body: t("sites.empty_search_body", "Try a different alias or clear the search field."),
      showAction: false,
    };
  }
  if (filter === "healthy") {
    return {
      title: t("sites.empty_healthy_title", "No healthy sites"),
      body: t("sites.empty_healthy_body", "Run a connection test or clear the filter to see every site."),
      showAction: false,
    };
  }
  if (filter === "untested") {
    return {
      title: t("sites.empty_untested_title", "No untested sites"),
      body: t("sites.empty_untested_body", "Every site has been tested. Clear the filter to see all sites."),
      showAction: false,
    };
  }
  return {
    title: t("no_sites", "No sites yet"),
    body: t(
      "sites.empty_body",
      "Register a Coolify project, WordPress site, or other supported plugin so your AI clients can use it.",
    ),
    showAction: true,
  };
}

export function SitesPage() {
  const t = useT();
  const [view, setView] = useState<"grid" | "list">("grid");
  const [search, setSearch] = useState("");
  // Track in-flight test + delete per site so each row can render its own
  // pending state without a global spinner.
  const [pendingTestId, setPendingTestId] = useState<string | null>(null);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);
  const [dialog, setDialog] = useState<
    | { mode: "create" }
    | { mode: "edit"; site: Site }
    | null
  >(null);
  const sites = useSites();
  const siteLimit = useSiteLimit();
  const testSite = useTestSite();
  const deleteSite = useDeleteSite();
  const setToast = useUiStore((s) => s.setToast);
  const lang = useUiStore((s) => s.lang);
  const limit = siteLimit.data?.limit;
  const remaining = siteLimit.data?.remaining;
  const atSiteLimit = typeof remaining === "number" && remaining <= 0;
  const siteLimitMessage =
    typeof limit === "number"
      ? t(
          "sites.limit_reached_body",
          "You have reached the maximum of {limit} services for this account. Delete an existing service or ask an administrator to raise the limit.",
        ).replace("{limit}", fmtInt(limit, lang))
      : t(
          "sites.limit_reached_body_unknown",
          "You have reached the maximum number of services for this account. Delete an existing service or ask an administrator to raise the limit.",
        );

  // Surface legacy flash params and support `?create=1` deep links from the
  // onboarding flow, then strip them from the URL so a refresh doesn't replay
  // the same action.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const msg = params.get("msg");
    const err = params.get("error");
    const openCreate = params.get("create") === "1";
    if (msg || err) {
      setToast(
        err === "site_not_found"
          ? t("site_not_found", "Site not found")
          : err
            ? `${t("error", "Error")}: ${err}`
            : msg!,
      );
    }
    if (openCreate && !atSiteLimit) {
      setDialog((current) => current ?? { mode: "create" });
    }
    if (msg || err || openCreate) {
      params.delete("msg");
      params.delete("error");
      params.delete("create");
      const qs = params.toString();
      const next = window.location.pathname + (qs ? `?${qs}` : "");
      window.history.replaceState({}, "", next);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [atSiteLimit]);

  const filtered = (sites.data ?? []).filter((s) => {
    if (search && !s.alias.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });
  const empty = emptyCopy("all", search, t);

  const onTest = async (id: string) => {
    setPendingTestId(id);
    try {
      const r = await testSite.mutateAsync(id);
      // Backend signals success via either `ok: true` or `status: "active"`
      // (sometimes `"healthy"` from older code paths). Trust `ok` first; fall
      // back to the status string so we stay tolerant if the contract drifts.
      const ok = r.ok === true || r.status === "active" || r.status === "healthy" || r.status === "ok";
      setToast(
        ok
          ? `${t("connection_ok", "Connection OK")}${r.response_time != null ? ` (${r.response_time}ms)` : ""}`
          : `${t("connection_failed", "Connection failed")}${r.message ? `: ${r.message}` : ""}`,
      );
      sites.refetch();
    } catch (e: any) {
      setToast(`${t("connection_failed", "Connection failed")}: ${e.message}`);
    } finally {
      setPendingTestId(null);
    }
  };
  const onDelete = async (s: Site) => {
    const confirmMsg = `${t("delete", "Delete")} "${s.alias}"?\n\n${
      s.url ?? ""
    }\n\nThis cannot be undone.`;
    if (!window.confirm(confirmMsg)) return;
    setPendingDeleteId(s.id);
    try {
      await deleteSite.mutateAsync(s.id);
      setToast(t("site_deleted", "Site deleted"));
    } catch (e: any) {
      setToast(`${t("delete", "Delete")} ${t("error", "error")}: ${e.message}`);
    } finally {
      setPendingDeleteId(null);
    }
  };

  return (
    <>
      <Topbar
        crumbs={[t("workspace", "Workspace"), t("my_sites", "Sites")]}
        actions={
          <>
            <Seg
              value={view}
              onChange={setView}
              options={[
                { value: "grid", label: t("view.grid", "Grid") },
                { value: "list", label: t("view.list", "List") },
              ]}
            />
            <button
              type="button"
              className="btn btn-primary btn-sm"
              disabled={atSiteLimit}
              title={atSiteLimit ? t("max_sites_reached", "Maximum sites reached") : undefined}
              onClick={() => {
                if (!atSiteLimit) setDialog({ mode: "create" });
              }}
            >
              <Icons.plus style={{ width: 12, height: 12 }} /> {t("add_site_short", "Add site")}
            </button>
          </>
        }
      />
      <div className="page-pad">
        <div className="page-head page-head-split">
          <div className="page-head-text">
            <h1 className="h-1" style={{ margin: 0 }}>
              {t("my_sites", "Sites")}
            </h1>
            <div className="body" style={{ color: "var(--text-muted)", marginTop: 6 }}>
              {t(
                "sites.intro",
                "Every site your AI agents can see. Capabilities are scoped per site and per key.",
              )}
            </div>
          </div>
          <div className="page-head-actions">
            <div style={searchBoxStyle}>
              <Icons.search style={{ width: 14, height: 14, color: "var(--text-subtle)" }} />
              <input
                placeholder={`${t("search", "Search")}…`}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                style={{ flex: 1, background: "none", border: "none", color: "var(--text)", outline: "none" }}
              />
            </div>
          </div>
        </div>

        {atSiteLimit ? (
          <div className="alert alert-warning" style={{ marginBottom: 16 }}>
            <Icons.warning style={{ width: 16, height: 16, flexShrink: 0 }} />
            <div style={{ flex: 1, fontSize: 13 }}>
              <div style={{ fontWeight: 500, color: "var(--text)", marginBottom: 2 }}>
                {t("max_sites_reached", "Maximum sites reached")}
              </div>
              <div className="caption">{siteLimitMessage}</div>
            </div>
          </div>
        ) : null}

        {sites.isLoading ? (
          <SitesSkeleton view={view} />
        ) : filtered.length === 0 ? (
          <Card className="sites-list-card">
            <EmptyState
              icon="sites"
              title={empty.title}
              action={
                empty.showAction ? (
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={atSiteLimit}
                    onClick={() => {
                      if (!atSiteLimit) setDialog({ mode: "create" });
                    }}
                  >
                    <Icons.plus style={{ width: 14, height: 14 }} />{" "}
                    {t("add_first_site", "Add your first site")}
                  </button>
                ) : undefined
              }
            >
              {empty.body}
            </EmptyState>
          </Card>
        ) : view === "grid" ? (
          <div style={gridStyle}>
            {filtered.map((s) => (
              <SiteCard
                key={s.id}
                site={s}
                t={t}
                lang={lang}
                pendingTest={pendingTestId === s.id}
                pendingDelete={pendingDeleteId === s.id}
                onTest={() => onTest(s.id)}
                onDelete={() => onDelete(s)}
                onEdit={() => setDialog({ mode: "edit", site: s })}
              />
            ))}
            <button
              type="button"
              className="tile"
              style={addTileStyle}
              disabled={atSiteLimit}
              onClick={() => {
                if (!atSiteLimit) setDialog({ mode: "create" });
              }}
            >
              <div style={addTileIconStyle}>
                <Icons.plus style={{ width: 18, height: 18 }} />
              </div>
              <div style={{ fontSize: 14, fontWeight: 500, color: "var(--text)" }}>
                {t("sites.add_tile_title", "Add a site")}
              </div>
              <div className="caption" style={{ textAlign: "center", maxWidth: 180 }}>
                {t(
                  "sites.add_tile_desc",
                  "Register a Coolify project, WordPress site, or other plugin",
                )}
              </div>
            </button>
          </div>
        ) : (
          <Card>
            <table className="table mobile-stack">
              <thead>
                <tr>
                  <th>{t("site_alias", "Alias")}</th>
                  <th>{t("plugin_type", "Plugin Type")}</th>
                  <th>{t("site_url", "Site URL")}</th>
                  <th>{t("status", "Status")}</th>
                  <th>{t("table.tier", "Tier")}</th>
                  <th>{t("last_tested", "Last tested")}</th>
                  <th style={{ textAlign: "right" }}>{t("actions", "Actions")}</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((s) => (
                  <SiteRow
                    key={s.id}
                    site={s}
                    t={t}
                    lang={lang}
                    pendingTest={pendingTestId === s.id}
                    pendingDelete={pendingDeleteId === s.id}
                    onTest={() => onTest(s.id)}
                    onDelete={() => onDelete(s)}
                    onEdit={() => setDialog({ mode: "edit", site: s })}
                  />
                ))}
              </tbody>
            </table>
          </Card>
        )}
      </div>

      {dialog ? (
        <SiteFormDialog
          mode={dialog.mode}
          site={dialog.mode === "edit" ? dialog.site : undefined}
          onCancel={() => setDialog(null)}
          onDone={() => setDialog(null)}
        />
      ) : null}
    </>
  );
}

// ---------- Cards & rows ----------

type CardProps = {
  site: Site;
  t: ReturnType<typeof useT>;
  lang: Lang;
  onEdit?: () => void;
  pendingTest: boolean;
  pendingDelete: boolean;
  onTest: () => void;
  onDelete: () => void;
};

function StatusBadge({ site, t }: { site: Site; t: ReturnType<typeof useT> }) {
  const status = normalizeSiteStatus(site.status, site.last_tested_at);
  if (status === "healthy")
    return (
      <Badge variant="success" dot className="badge-fixed">
        {t("status_healthy", "healthy")}
      </Badge>
    );
  if (status === "warning")
    return (
      <Badge variant="warning" dot className="badge-fixed">
        {t("status_warning", "warning")}
      </Badge>
    );
  if (status === "error")
    return (
      <Badge variant="danger" dot className="badge-fixed">
        {t("status_error", "error")}
      </Badge>
    );
  if (status === "unknown")
    return (
      <Badge variant="warning" className="badge-fixed">
        {t("status_unknown", "unknown")}
      </Badge>
    );
  return <Badge className="badge-fixed">{t("status_untested", "untested")}</Badge>;
}

function TierBadge({ scope }: { scope: string | undefined }) {
  if (!scope) return null;
  return (
    <Badge variant={tierBadgeVariant(scope)} className="badge-fixed" title={`tool_scope: ${scope}`}>
      {scope}
    </Badge>
  );
}

function SiteCard({ site: s, t, lang, pendingTest, pendingDelete, onTest, onDelete, onEdit }: CardProps) {
  const pluginLabel = PLUGIN_DISPLAY[s.plugin_type] ?? s.plugin_type;
  return (
    <div className="tile" style={{ display: "flex", flexDirection: "column" }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 14, gap: 8 }}>
        <div style={{ display: "flex", gap: 10, alignItems: "center", minWidth: 0 }}>
          <div style={iconBoxStyle}>
            <Icons.server style={{ width: 16, height: 16, color: "var(--brand-400)" }} />
          </div>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {s.alias}
            </div>
            <div className="caption">{pluginLabel}</div>
          </div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4 }}>
          <StatusBadge site={s} t={t} />
          <TierBadge scope={s.tool_scope} />
        </div>
      </div>
      <div className="caption" style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis" }}>
        {s.url || "—"}
      </div>
      {s.status_msg ? (
        <div
          className="caption"
          style={{ marginTop: 6, color: s.status === "error" ? "var(--danger)" : "var(--text-muted)" }}
        >
          {s.status_msg.slice(0, 80)}
        </div>
      ) : null}
      <div className="caption" style={{ marginTop: 6, color: "var(--text-subtle)" }}>
        {formatTested(s.last_tested_at, lang, t)}
      </div>
      <div style={{ display: "flex", gap: 6, marginTop: 14 }}>
        <Link
          to={`/connect?site=${encodeURIComponent(s.alias)}`}
          className="btn btn-secondary btn-sm"
          style={{ flex: 1, textAlign: "center" }}
        >
          {t("connect", "Connect")}
        </Link>
        <Link
          to={`/sites/${s.id}/tools`}
          className="btn btn-ghost btn-sm"
          style={{ padding: 6 }}
          title={t("sites.manage_tools", "Manage tools")}
        >
          <Icons.shield style={{ width: 14, height: 14 }} />
        </Link>
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          style={{ padding: 6 }}
          onClick={onEdit}
          title={t("edit", "Edit")}
        >
          <Icons.edit style={{ width: 14, height: 14 }} />
        </button>
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          style={{ padding: 6 }}
          onClick={onTest}
          disabled={pendingTest}
          title={t("test_connection", "Test connection")}
        >
          {pendingTest ? <Spinner /> : <Icons.refresh style={{ width: 14, height: 14 }} />}
        </button>
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          style={{ padding: 6, color: "var(--danger)" }}
          onClick={onDelete}
          disabled={pendingDelete}
          title={t("delete", "Delete")}
        >
          {pendingDelete ? <Spinner /> : <Icons.trash style={{ width: 14, height: 14 }} />}
        </button>
      </div>
    </div>
  );
}

function SiteRow({ site: s, t, lang, pendingTest, pendingDelete, onTest, onDelete, onEdit }: CardProps) {
  const pluginLabel = PLUGIN_DISPLAY[s.plugin_type] ?? s.plugin_type;
  return (
    <tr>
      <td className="row-head" data-label={t("site_alias", "Alias")} style={{ fontWeight: 500 }}>
        {s.alias}
      </td>
      <td data-label={t("plugin_type", "Plugin Type")}>
        <Badge>{pluginLabel}</Badge>
      </td>
      <td className="mono caption sites-url-cell" data-label={t("site_url", "Site URL")}>
        {s.url}
      </td>
      <td data-label={t("status", "Status")}>
        <StatusBadge site={s} t={t} />
      </td>
      <td data-label={t("table.tier", "Tier")}>
        <TierBadge scope={s.tool_scope} />
      </td>
      <td className="caption" data-label={t("last_tested", "Last tested")}>
        {fmtDateTime(s.last_tested_at, lang)}
      </td>
      <td className="cell-actions" style={{ textAlign: "right" }}>
        <div style={{ display: "inline-flex", gap: 4 }}>
          <Btn
            variant="ghost"
            size="sm"
            onClick={onTest}
            disabled={pendingTest}
            title={t("test_connection", "Test")}
            style={{ padding: 6 }}
          >
            {pendingTest ? <Spinner /> : <Icons.refresh style={{ width: 14, height: 14 }} />}
          </Btn>
          <Link
            to={`/connect?site=${encodeURIComponent(s.alias)}`}
            className="btn btn-ghost btn-sm"
            style={{ padding: "6px 10px" }}
            title={t("connect", "Connect")}
          >
            {t("connect", "Connect")}
          </Link>
          <Link
            to={`/sites/${s.id}/tools`}
            className="btn btn-ghost btn-sm"
            style={{ padding: 6 }}
            title={t("sites.manage_tools", "Manage tools")}
          >
            <Icons.shield style={{ width: 14, height: 14 }} />
          </Link>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            style={{ padding: 6 }}
            onClick={onEdit}
            title={t("edit", "Edit")}
          >
            <Icons.edit style={{ width: 14, height: 14 }} />
          </button>
          <Btn
            variant="ghost"
            size="sm"
            onClick={onDelete}
            disabled={pendingDelete}
            title={t("delete", "Delete")}
            style={{ padding: 6, color: "var(--danger)" }}
          >
            {pendingDelete ? <Spinner /> : <Icons.trash style={{ width: 14, height: 14 }} />}
          </Btn>
        </div>
      </td>
    </tr>
  );
}

function SitesSkeleton({ view }: { view: "grid" | "list" }) {
  // Minimal animated placeholder so the empty space carries system status while
  // the request is in flight (replaces the bare "Loading sites…" caption).
  if (view === "list") {
    return (
      <Card>
        <div role="status" aria-live="polite" style={{ padding: 16 }}>
          <div className="caption" style={{ marginBottom: 12 }}>
            {/* visually hidden text for screen readers; keep visible text minimal */}
            Loading…
          </div>
          {[0, 1, 2].map((i) => (
            <div key={i} className="shimmer" style={skeletonRowStyle} />
          ))}
        </div>
      </Card>
    );
  }
  return (
    <div style={gridStyle} role="status" aria-live="polite">
      {[0, 1, 2].map((i) => (
        <div key={i} className="tile shimmer" style={skeletonTileStyle} />
      ))}
    </div>
  );
}

function Spinner() {
  return (
    <span
      aria-label="loading"
      style={{
        display: "inline-block",
        width: 14,
        height: 14,
        border: "2px solid var(--border)",
        borderTopColor: "var(--brand-400)",
        borderRadius: "50%",
        animation: "spin 0.8s linear infinite",
      }}
    />
  );
}

// ---------- Style constants (lifted out of JSX so the markup is scannable) ----------

const searchBoxStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 8,
  padding: "7px 10px",
  minWidth: 260,
  background: "var(--bg-sunken)",
  border: "1px solid var(--border)",
  borderRadius: 8,
  fontSize: 13,
};

const gridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
  gap: 16,
  alignItems: "stretch",
};

const iconBoxStyle: CSSProperties = {
  width: 36,
  height: 36,
  borderRadius: 8,
  background: "var(--surface)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  border: "1px solid var(--border)",
  flexShrink: 0,
};

const addTileStyle: CSSProperties = {
  borderStyle: "dashed",
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "center",
  gap: 10,
  color: "var(--text-muted)",
};

const addTileIconStyle: CSSProperties = {
  width: 44,
  height: 44,
  borderRadius: "50%",
  background: "oklch(from var(--brand-500) l c h / 0.1)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  color: "var(--brand-400)",
};

const skeletonTileStyle: CSSProperties = {
  height: 160,
};

const skeletonRowStyle: CSSProperties = {
  height: 32,
  marginBottom: 8,
  borderRadius: 6,
};
