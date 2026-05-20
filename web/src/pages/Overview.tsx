import { Link } from "react-router-dom";
import { Topbar } from "../components/Topbar";
import { Card, CardHead, Badge, Btn, EmptyState } from "../components/primitives";
import { Icons } from "../components/icons";
import { useDashboardStats, useSession, useSites, useUserKeys } from "../lib/queries";
import type { DashboardStats } from "../lib/types";
import { useT } from "../lib/i18n";
import { useUiStore } from "../lib/store";
import type { Lang } from "../lib/store";
import { fmtNumber, fmtInt, fmtDateTime, normalizeSiteStatus } from "../lib/format";

export function OverviewPage() {
  const t = useT();
  const lang = useUiStore((s) => s.lang);
  const session = useSession();
  const isAdmin = session.data?.is_admin ?? false;
  const stats = useDashboardStats();
  const sites = useSites();
  const keys = useUserKeys();

  const userSitesCount = sites.data?.length ?? 0;
  const userKeysCount = keys.data?.length ?? 0;
  const healthyCount = (sites.data ?? []).filter((s) => normalizeSiteStatus(s.status, s.last_tested_at) === "healthy").length;

  // Persian has no plural inflection; English does. Keep both natural.
  const summary =
    lang === "fa"
      ? `${fmtNumber(userSitesCount, lang)} سایت ثبت‌شده · ${fmtNumber(userKeysCount, lang)} کلید فعال`
      : `${userSitesCount} site${userSitesCount === 1 ? "" : "s"} registered · ${userKeysCount} key${userKeysCount === 1 ? "" : "s"} active`;

  // /api/dashboard/stats has different shapes for admin vs OAuth user; the
  // user payload doesn't carry tools_count or uptime_days. Use the live
  // /api/sites and /api/keys queries as the source of truth for counts so
  // the cards never disagree with the underlying lists.
  const cards = [
    {
      label: t("card.active_sites_label", "Active sites"),
      value: fmtNumber(userSitesCount, lang, "0"),
      delta: t("card.active_sites_caption", "Sites you manage"),
      icon: "sites" as const,
    },
    {
      label: t("card.api_keys_label", "API keys"),
      value: fmtNumber(userKeysCount, lang, "0"),
      delta: t("card.api_keys_caption", "Personal & client keys"),
      icon: "key" as const,
    },
    {
      label: t("card.healthy_sites_label", "Healthy sites"),
      value:
        userSitesCount === 0
          ? "—"
          : `${fmtNumber(healthyCount, lang)} / ${fmtNumber(userSitesCount, lang)}`,
      delta: t("card.healthy_sites_caption", "Sites passing connection tests"),
      icon: "activity" as const,
    },
    {
      label: t("card.uptime_label", "Uptime (days)"),
      value: fmtInt(stats.data?.uptime_days, lang, "—"),
      delta: t("card.uptime_caption", "Hub availability"),
      icon: "spark" as const,
    },
  ];

  const greeting = `${t("welcome_greeting", "Hello")}${session.data?.name ? `, ${session.data.name}` : ""}.`;

  return (
    <>
      <Topbar
        crumbs={[t("workspace", "Workspace"), t("nav.overview", "Overview")]}
        actions={
          <Btn
            variant="secondary"
            size="sm"
            icon="refresh"
            onClick={() => {
              stats.refetch();
              sites.refetch();
              keys.refetch();
            }}
          >
            {t("refresh", "Refresh")}
          </Btn>
        }
      />
      <div className="page-pad">
        <div className="page-head page-head-split">
          <div className="page-head-text">
            <div className="eyebrow" style={{ marginBottom: 8 }}>
              {t("welcome_eyebrow", "Welcome back")}
            </div>
            <h1 className="h-1" style={{ margin: 0 }}>
              {greeting}
            </h1>
            <div className="body" style={{ color: "var(--text-muted)", marginTop: 6 }}>
              {summary}
            </div>
          </div>
          <div className="page-head-actions">
            <Link to="/connect">
              <Btn variant="secondary" icon="plug">
                {t("connect_client", "Connect client")}
              </Btn>
            </Link>
            <Link to="/sites">
              <Btn variant="primary" icon="plus">
                {t("add_site_short", "Add site")}
              </Btn>
            </Link>
          </div>
        </div>

        {isAdmin && (
          <AdminStatsPanel stats={stats.data} lang={lang} t={t} />
        )}

        <div className="stat-grid">
          {cards.map((s) => {
            const Ic = Icons[s.icon];
            return (
              <div key={s.label} className="card card-pad" style={{ padding: 18 }}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "flex-start",
                    marginBottom: 10,
                  }}
                >
                  <div style={{ fontSize: 12, color: "var(--text-muted)" }}>{s.label}</div>
                  <Ic style={{ width: 16, height: 16, color: "var(--text-subtle)" }} />
                </div>
                <div
                  style={{
                    fontSize: 28,
                    fontWeight: 600,
                    letterSpacing: "-0.02em",
                    marginBottom: 6,
                  }}
                >
                  {s.value}
                </div>
                <div className="caption">{s.delta}</div>
              </div>
            );
          })}
        </div>

        <Card>
          <CardHead
            icon="sites"
            title={t("your_sites", "Your sites")}
            subtitle={t("health_connection_status", "Health and connection status")}
            action={
              <Link to="/sites">
                <Btn variant="ghost" size="sm" iconRight="arrow">
                  {t("manage", "Manage")}
                </Btn>
              </Link>
            }
          />
          <div>
            {sites.isLoading ? (
              <div className="card-body">
                <div className="shimmer" style={{ height: 28, borderRadius: 4, marginBottom: 6 }} />
                <div className="shimmer" style={{ height: 28, borderRadius: 4, marginBottom: 6 }} />
                <div className="shimmer" style={{ height: 28, borderRadius: 4 }} />
              </div>
            ) : !sites.data || sites.data.length === 0 ? (
              <EmptyState
                icon="sites"
                title={t("no_sites", "No sites yet")}
                action={
                  <Link to="/sites">
                    <Btn variant="primary" icon="plus">
                      {t("add_first_site", "Add your first site")}
                    </Btn>
                  </Link>
                }
              >
                {t(
                  "register_first_site_body",
                  "Register a Coolify project, WordPress site, or other supported plugin to get started.",
                )}
              </EmptyState>
            ) : (
              <table className="table mobile-stack">
                <thead>
                  <tr>
                    <th>{t("table.site", "Site")}</th>
                    <th>{t("table.type", "Type")}</th>
                    <th>{t("table.status", "Status")}</th>
                    <th>{t("table.last_tested", "Last tested")}</th>
                  </tr>
                </thead>
                <tbody>
                  {sites.data.map((s) => {
                    const status = normalizeSiteStatus(s.status, s.last_tested_at);
                    return (
                      <tr key={s.id}>
                        <td className="row-head" data-label={t("table.site", "Site")}>
                          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                            <div
                              style={{
                                width: 8,
                                height: 8,
                                borderRadius: 2,
                                background:
                                  status === "healthy"
                                    ? "var(--success)"
                                    : status === "warning"
                                      ? "var(--warning)"
                                      : status === "error"
                                        ? "var(--danger)"
                                        : "var(--text-subtle)",
                              }}
                            />
                            <span style={{ fontWeight: 500 }}>{s.alias}</span>
                          </div>
                        </td>
                        <td data-label={t("table.type", "Type")}>
                          <Badge>{s.plugin_type}</Badge>
                        </td>
                        <td data-label={t("table.status", "Status")}>
                          {status === "healthy" ? (
                            <Badge variant="success" dot>
                              {t("status_healthy", "healthy")}
                            </Badge>
                          ) : status === "warning" ? (
                            <Badge variant="warning" dot>
                              {t("status_warning", "warning")}
                            </Badge>
                          ) : status === "error" ? (
                            <Badge variant="danger" dot>
                              {t("status_error", "error")}
                            </Badge>
                          ) : status === "unknown" ? (
                            <Badge variant="warning">{t("status_unknown", "unknown")}</Badge>
                          ) : (
                            <Badge>{t("status_untested", "untested")}</Badge>
                          )}
                        </td>
                        <td className="caption" data-label={t("table.last_tested", "Last tested")}>
                          {fmtDateTime(s.last_tested_at, lang)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        </Card>
      </div>
    </>
  );
}

// ---------- Admin-only stats panel ----------

function AdminStatsPanel({
  stats,
  lang,
  t,
}: {
  stats: DashboardStats | undefined;
  lang: Lang;
  t: (key: string, fallback: string) => string;
}) {
  if (!stats) return null;
  const adminCards = [
    {
      label: t("card.total_users_label", "Registered users"),
      value: fmtNumber(stats.users_count, lang, "—"),
      delta: t("card.total_users_caption", "All-time registrations"),
      icon: "user" as const,
    },
    {
      label: t("card.recent_users_label", "New users (7d)"),
      value: fmtNumber(stats.recent_users_count, lang, "—"),
      delta: t("card.recent_users_caption", "Joined in the last 7 days"),
      icon: "activity" as const,
    },
    {
      label: t("card.user_sites_label", "User sites"),
      value: fmtNumber(stats.user_sites_count, lang, "—"),
      delta: t("card.user_sites_caption", "Sites across all accounts"),
      icon: "sites" as const,
    },
    {
      label: t("card.tools_label", "Available tools"),
      value: fmtNumber(stats.tools_count, lang, "—"),
      delta: t("card.tools_caption", "Active MCP tools"),
      icon: "plug" as const,
    },
  ];
  return (
    <div style={{ marginBottom: 20 }}>
      <div className="caption" style={{ marginBottom: 8, color: "var(--text-muted)", display: "flex", alignItems: "center", gap: 6 }}>
        <Icons.shield style={{ width: 12, height: 12 }} />
        {t("badge.admin", "Admin")} · {t("card.platform_stats", "Platform stats")}
      </div>
      <div className="stat-grid">
        {adminCards.map((s) => {
          const Ic = Icons[s.icon];
          return (
            <div key={s.label} className="card card-pad" style={{ padding: 18, borderColor: "oklch(from var(--brand-500) l c h / 0.25)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 10 }}>
                <div style={{ fontSize: 12, color: "var(--text-muted)" }}>{s.label}</div>
                <Ic style={{ width: 16, height: 16, color: "var(--text-subtle)" }} />
              </div>
              <div style={{ fontSize: 28, fontWeight: 600, letterSpacing: "-0.02em", marginBottom: 6 }}>{s.value}</div>
              <div className="caption">{s.delta}</div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
