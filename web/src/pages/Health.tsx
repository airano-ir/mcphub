import { Topbar } from "../components/Topbar";
import { Card, CardHead, Donut, Badge } from "../components/primitives";
import { useDashboardStats, useHealth } from "../lib/queries";
import { useT } from "../lib/i18n";
import { useUiStore } from "../lib/store";
import { fmtDateTime } from "../lib/format";

type StatusVariant = "success" | "warning" | "danger" | "default";

function statusVariant(s: string | undefined): StatusVariant {
  if (s === "healthy" || s === "ok" || s === "up") return "success";
  if (s === "degraded" || s === "warning") return "warning";
  if (s === "down" || s === "error" || s === "critical") return "danger";
  return "default";
}

function alertVariant(level: string | undefined): StatusVariant {
  if (level === "error" || level === "critical") return "danger";
  if (level === "warning" || level === "warn") return "warning";
  return "default";
}

export function HealthPage() {
  const t = useT();
  const lang = useUiStore((s) => s.lang);
  const health = useHealth();
  const stats = useDashboardStats();
  const data = health.data;
  const isLoading = health.isLoading;

  const overall = data?.system_status ?? "unknown";
  const isHealthy = overall === "healthy";
  const projects = Object.entries(data?.projects_health ?? {});
  const summary = data?.projects_summary ?? { total: 0, healthy: 0, unhealthy: 0 };
  const metrics = data?.metrics ?? {};
  const uptime = data?.uptime ?? {};
  const alerts = data?.alerts ?? [];

  return (
    <>
      <Topbar crumbs={[t("nav.observability", "Observability"), t("health", "Health")]} />
      <div className="page-pad">
        <div className="page-head">
          <h1 className="h-1" style={{ margin: 0 }}>
            {t("health_status", "Health")}
          </h1>
          <div className="body" style={{ color: "var(--text-muted)", marginTop: 6 }}>
            {t("health.intro", "Hub and per-site status. Auto-refreshing every 30 seconds.")}
          </div>
        </div>

        {isLoading ? (
          <Card className="shimmer" style={{ height: 110, marginBottom: 20 }} />
        ) : (
          <Card style={{ marginBottom: 20, padding: 0, overflow: "hidden" }}>
            <div className="health-overview">
              <Donut
                value={isHealthy ? 100 : overall === "degraded" ? 60 : 25}
                size={64}
                color={
                  isHealthy
                    ? "var(--success)"
                    : overall === "degraded"
                      ? "var(--warning)"
                      : "var(--danger)"
                }
              />
              <div className="health-overview-text">
                <div className="health-overview-title">
                  <div className="h-2" style={{ margin: 0 }}>
                    {isHealthy
                      ? t("health.all_operational", "All systems operational")
                      : overall === "degraded"
                        ? t("health.degraded", "Degraded")
                        : overall === "down"
                          ? t("health.down", "Down")
                          : `${t("status", "Status")}: ${overall}`}
                  </div>
                  <Badge variant={statusVariant(overall)} dot>
                    {t(`status_${overall}`, overall)}
                  </Badge>
                  <span
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 6,
                      fontSize: 12,
                      color: isHealthy ? "var(--success)" : "var(--warning)",
                    }}
                  >
                    <span className="live-dot" /> {t("status.live", "live")}
                  </span>
                </div>
                <div className="caption" style={{ marginTop: 4 }}>
                  {t("health.up", "Up")}:{" "}
                  <strong style={{ color: "var(--text)" }}>{uptime.formatted ?? "—"}</strong>
                  {" · "}
                  {t("health.last_check", "Last check")}:{" "}
                  <strong style={{ color: "var(--text)" }}>
                    {fmtDateTime(uptime.current_time, lang)}
                  </strong>
                </div>
              </div>
              <div className="health-overview-stats">
                <Stat
                  label={t("total_tools", "Tools")}
                  value={stats.data?.tools_count ?? "—"}
                />
                <Stat
                  label={t("health.projects_label", "Projects")}
                  value={`${summary.healthy ?? 0}/${summary.total ?? 0}`}
                />
                <Stat
                  label={t("health.alerts_label", "Alerts")}
                  value={alerts.length}
                  tone={alerts.length > 0 ? "warning" : "default"}
                />
              </div>
            </div>
          </Card>
        )}

        <div className="health-metrics-grid">
          <Card>
            <CardHead
              title={t("health.metrics_title", "Request metrics")}
              subtitle={t("health.metrics_subtitle", "Across the live process")}
            />
            <div className="health-stat-grid">
              <Stat
                label={t("health.total_requests", "Total requests")}
                value={metrics.total_requests ?? "—"}
              />
              <Stat
                label={t("health.per_minute", "Per minute")}
                value={metrics.requests_per_minute ?? "—"}
              />
              <Stat
                label={t("health.avg_response", "Avg response (ms)")}
                value={metrics.average_response_time_ms ?? "—"}
              />
              <Stat
                label={t("health.error_rate", "Error rate")}
                value={
                  metrics.error_rate_percent != null ? `${metrics.error_rate_percent.toFixed(2)}%` : "—"
                }
                tone={
                  metrics.error_rate_percent != null && metrics.error_rate_percent > 1
                    ? "danger"
                    : "default"
                }
              />
            </div>
          </Card>

          <Card>
            <CardHead
              title={t("health.recent_alerts", "Recent alerts")}
              subtitle={`${alerts.length} ${t("active", "active")}`}
            />
            <div style={{ padding: 12 }}>
              {alerts.length === 0 ? (
                <div className="caption" style={{ padding: 12 }}>
                  {t("health.no_alerts", "No active alerts.")}
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {alerts.slice(0, 6).map((a, i) => (
                    <div
                      key={i}
                      style={{
                        display: "flex",
                        gap: 10,
                        padding: 10,
                        borderRadius: 6,
                        background: "var(--bg-sunken)",
                        border: "1px solid var(--border)",
                      }}
                    >
                      <Badge variant={alertVariant(a.level)} className="badge-fixed">
                        {a.level ?? "info"}
                      </Badge>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 13, fontWeight: 500 }}>
                          {a.message ?? a.source ?? "(no message)"}
                        </div>
                        {a.path || a.status_code != null ? (
                          <div className="mono caption" style={{ marginTop: 2 }}>
                            {a.status_code != null ? `${a.status_code} ` : ""}
                            {a.path ?? ""}
                          </div>
                        ) : null}
                        {a.timestamp ? (
                          <div className="caption" style={{ marginTop: 2 }}>
                            {a.timestamp}
                          </div>
                        ) : null}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </Card>
        </div>

        <Card>
          <CardHead
            title={t("health.projects_label", "Projects")}
            subtitle={`${projects.length} ${t("health.registered", "registered")}`}
          />
          {isLoading ? (
            <div className="card-body">
              <div className="shimmer" style={{ height: 28, borderRadius: 4, marginBottom: 6 }} />
              <div className="shimmer" style={{ height: 28, borderRadius: 4, marginBottom: 6 }} />
              <div className="shimmer" style={{ height: 28, borderRadius: 4 }} />
            </div>
          ) : projects.length === 0 ? (
            <div className="card-body caption">
              {t("health.no_projects", "No projects to monitor yet.")}
            </div>
          ) : (
            <table className="table mobile-stack">
              <thead>
                <tr>
                  <th>{t("table.project", "Project")}</th>
                  <th>{t("status", "Status")}</th>
                  <th>{t("table.latency", "Latency")}</th>
                  <th>{t("table.uptime", "Uptime")}</th>
                  <th>{t("table.tools", "Tools")}</th>
                  <th>{t("table.last_check", "Last check")}</th>
                </tr>
              </thead>
              <tbody>
                {projects.map(([id, p]) => (
                  <tr key={id}>
                    <td className="row-head" data-label={t("table.project", "Project")} style={{ fontWeight: 500 }}>
                      {id}
                    </td>
                    <td data-label={t("status", "Status")}>
                      <Badge variant={statusVariant(p.status)} dot>
                        {t(`status_${p.status ?? "unknown"}`, p.status ?? "unknown")}
                      </Badge>
                    </td>
                    <td className="mono" data-label={t("table.latency", "Latency")}>
                      {p.latency_ms != null ? `${p.latency_ms} ms` : "—"}
                    </td>
                    <td className="mono" data-label={t("table.uptime", "Uptime")}>
                      {p.uptime_percent != null ? `${p.uptime_percent.toFixed(2)}%` : "—"}
                    </td>
                    <td className="mono" data-label={t("table.tools", "Tools")}>
                      {p.tool_count ?? "—"}
                    </td>
                    <td className="caption" data-label={t("table.last_check", "Last check")}>
                      {fmtDateTime(p.last_check, lang)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Card>
      </div>
    </>
  );
}

function Stat({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: string | number;
  tone?: "default" | "warning" | "danger";
}) {
  const color =
    tone === "danger"
      ? "var(--danger)"
      : tone === "warning"
        ? "var(--warning, #d97706)"
        : "var(--text)";
  return (
    <div>
      <div className="caption">{label}</div>
      <div className="mono" style={{ fontSize: 18, fontWeight: 500, color }}>
        {value}
      </div>
    </div>
  );
}

