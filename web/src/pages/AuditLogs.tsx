import { useEffect, useState, type CSSProperties } from "react";
import { Topbar } from "../components/Topbar";
import { Card, Badge, Btn, Avatar, Seg } from "../components/primitives";
import { Icons } from "../components/icons";
import { useAuditLogs } from "../lib/queries";
import { useT } from "../lib/i18n";
import { useUiStore } from "../lib/store";
import { fmtDateTime, fmtNumber } from "../lib/format";

type LevelFilter = "all" | "info" | "warn" | "error";

const PAGE_SIZES = [25, 50, 100, 200] as const;

function levelBadge(level: string | undefined) {
  if (level === "error")
    return (
      <Badge variant="danger" dot>
        error
      </Badge>
    );
  if (level === "warn")
    return (
      <Badge variant="warning" dot>
        warn
      </Badge>
    );
  return (
    <Badge variant="success" dot>
      {level ?? "info"}
    </Badge>
  );
}

function resultBadge(r: string | undefined) {
  if (!r) return null;
  if (r === "ok")
    return (
      <Badge variant="success" className="badge-fixed">
        ok
      </Badge>
    );
  if (r === "denied")
    return (
      <Badge variant="warning" className="badge-fixed">
        denied
      </Badge>
    );
  if (r === "error")
    return (
      <Badge variant="danger" className="badge-fixed">
        error
      </Badge>
    );
  return <Badge className="badge-fixed">{r}</Badge>;
}

export function AuditLogsPage() {
  const t = useT();
  const lang = useUiStore((s) => s.lang);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState<number>(50);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState(""); // debounced value used in query
  const [level, setLevel] = useState<LevelFilter>("all");
  const [date, setDate] = useState<string>("");
  const [eventType, setEventType] = useState<string>("");

  // Debounce search so each keystroke doesn't refetch.
  useEffect(() => {
    const id = setTimeout(() => setSearch(searchInput), 300);
    return () => clearTimeout(id);
  }, [searchInput]);

  // Reset to page 1 whenever a filter changes so the user doesn't land on
  // an empty page.
  useEffect(() => {
    setPage(1);
  }, [search, level, date, eventType, pageSize]);

  const logs = useAuditLogs({
    page,
    limit: pageSize,
    level: level === "all" ? undefined : level,
    search: search || undefined,
    date: date || undefined,
    eventType: eventType || undefined,
  });

  const entries = logs.data?.entries ?? [];
  const total = logs.data?.total ?? 0;
  const totalPages = logs.data?.pages ?? 1;

  return (
    <>
      <Topbar
        crumbs={[t("nav.observability", "Observability"), t("audit_logs", "Audit logs")]}
        actions={
          <Btn variant="secondary" size="sm" icon="refresh" onClick={() => logs.refetch()}>
            {t("refresh", "Refresh")}
          </Btn>
        }
      />
      <div className="page-pad">
        <div className="page-head">
          <h1 className="h-1" style={{ margin: 0 }}>
            {t("audit_logs", "Audit logs")}
          </h1>
          <div className="body" style={{ color: "var(--text-muted)", marginTop: 6 }}>
            {t(
              "audit.intro",
              "Every authentication, tool call, and config change. GDPR-compliant. Filters apply server-side.",
            )}
          </div>
        </div>

        <div className="audit-filter" style={filterRowStyle}>
          <div style={searchBoxStyle}>
            <Icons.search style={{ width: 14, height: 14, color: "var(--text-subtle)" }} />
            <input
              placeholder={t("audit.search_placeholder", "Search actor / event / target / message…")}
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              style={inputResetStyle}
            />
          </div>
          <input
            type="text"
            placeholder={t("audit.event_type_placeholder", "event_type (e.g. tool_call)")}
            value={eventType}
            onChange={(e) => setEventType(e.target.value)}
            className="input"
            style={{ width: 220, fontFamily: "var(--font-mono)", fontSize: 12 }}
          />
          <input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="input"
            style={{ width: 170 }}
            title={t("audit.date_filter_title", "Filter by single day (YYYY-MM-DD)")}
          />
          <Seg
            value={level}
            onChange={setLevel}
            options={[
              { value: "all", label: t("all", "All") },
              { value: "info", label: t("audit.level.info", "Info") },
              { value: "warn", label: t("audit.level.warn", "Warn") },
              { value: "error", label: t("error", "Error") },
            ]}
          />
          <select
            className="input"
            style={{ width: 90, fontFamily: "var(--font-mono)" }}
            value={String(pageSize)}
            onChange={(e) => setPageSize(Number(e.target.value))}
            title={t("audit.page_size", "Page size")}
          >
            {PAGE_SIZES.map((s) => (
              <option key={s} value={s}>
                {t("audit.per_page", "{n}/page").replace("{n}", String(s))}
              </option>
            ))}
          </select>
        </div>

        <Card style={{ padding: 0 }}>
          <table className="table mobile-stack">
            <thead>
              <tr>
                <th style={{ width: 150 }}>{t("audit.col.time", "Time")}</th>
                <th>{t("audit.col.actor", "Actor")}</th>
                <th>{t("audit.col.event", "Event")}</th>
                <th>{t("audit.col.target", "Target")}</th>
                <th>{t("audit.col.message", "Message")}</th>
                <th>{t("audit.col.result", "Result")}</th>
                <th>{t("audit.col.level", "Level")}</th>
                <th>{t("audit.col.duration", "Duration")}</th>
              </tr>
            </thead>
            <tbody>
              {logs.isLoading ? (
                <SkeletonRows cols={8} />
              ) : entries.length === 0 ? (
                <tr>
                  <td colSpan={8} className="caption" style={{ padding: 24, textAlign: "center" }}>
                    {t("audit.no_entries", "No matching entries.")}
                    {search || level !== "all" || date || eventType ? (
                      <>
                        {" "}
                        <a
                          href="#"
                          onClick={(e) => {
                            e.preventDefault();
                            setSearchInput("");
                            setSearch("");
                            setLevel("all");
                            setDate("");
                            setEventType("");
                          }}
                          style={{ color: "var(--brand-400)" }}
                        >
                          {t("audit.clear_filters", "Clear filters")}
                        </a>
                      </>
                    ) : null}
                  </td>
                </tr>
              ) : (
                entries.map((r, i) => (
                  <tr key={r.id ?? i}>
                    <td
                      className="row-head mono"
                      data-label={t("audit.col.time", "Time")}
                      style={{ color: "var(--text-muted)", fontSize: 11.5 }}
                    >
                      {fmtDateTime(r.timestamp, lang)}
                    </td>
                    <td data-label={t("audit.col.actor", "Actor")}>
                      <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                        <Avatar name={r.actor || "system"} size={20} />
                        {r.actor ?? "system"}
                        {r.ip ? (
                          <span className="mono caption" title={`from ${r.ip}`}>
                            ({r.ip})
                          </span>
                        ) : null}
                      </div>
                    </td>
                    <td
                      className="mono"
                      data-label={t("audit.col.event", "Event")}
                      style={{ color: "var(--brand-400)" }}
                    >
                      {r.event_type}
                    </td>
                    <td data-label={t("audit.col.target", "Target")} style={{ color: "var(--text-muted)" }}>
                      {r.target ?? "—"}
                    </td>
                    <td
                      className="caption"
                      data-label={t("audit.col.message", "Message")}
                      style={{ maxWidth: 320, wordBreak: "break-word" }}
                    >
                      {r.message ?? "—"}
                    </td>
                    <td data-label={t("audit.col.result", "Result")}>{resultBadge(r.result)}</td>
                    <td data-label={t("audit.col.level", "Level")}>{levelBadge(r.level)}</td>
                    <td className="mono caption" data-label={t("audit.col.duration", "Duration")}>
                      {r.duration_ms != null ? `${fmtNumber(r.duration_ms, lang)} ms` : "—"}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </Card>

        <div style={paginationStyle}>
          <span className="caption">
            {total > 0
              ? t("audit.range_of", "{from}–{to} of {total}")
                  .replace("{from}", fmtNumber((page - 1) * pageSize + 1, lang))
                  .replace("{to}", fmtNumber(Math.min(page * pageSize, total), lang))
                  .replace("{total}", fmtNumber(total, lang))
              : t("audit.zero_entries", "0 entries")}
          </span>
          <Btn variant="secondary" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
            {lang === "fa" ? "→ " : "← "}
            {t("previous", "Previous")}
          </Btn>
          <span className="caption" style={{ alignSelf: "center" }}>
            {t("audit.page_label", "Page")}{" "}
            <strong style={{ color: "var(--text)" }}>{fmtNumber(page, lang)}</strong> /{" "}
            {fmtNumber(totalPages, lang)}
          </span>
          <Btn
            variant="secondary"
            size="sm"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
          >
            {t("next", "Next")}
            {lang === "fa" ? " ←" : " →"}
          </Btn>
        </div>
      </div>
    </>
  );
}

function SkeletonRows({ cols }: { cols: number }) {
  return (
    <>
      {[0, 1, 2, 3, 4].map((i) => (
        <tr key={i}>
          {Array.from({ length: cols }).map((_, j) => (
            <td key={j}>
              <div className="shimmer" style={{ height: 14, borderRadius: 4 }} />
            </td>
          ))}
        </tr>
      ))}
    </>
  );
}

const filterRowStyle: CSSProperties = {
  display: "flex",
  gap: 10,
  alignItems: "center",
  marginBottom: 16,
  flexWrap: "wrap",
};

const searchBoxStyle: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 8,
  padding: "7px 10px",
  flex: 1,
  minWidth: 280,
  background: "var(--bg-sunken)",
  border: "1px solid var(--border)",
  borderRadius: 8,
  fontSize: 13,
};

const inputResetStyle: CSSProperties = {
  flex: 1,
  background: "none",
  border: "none",
  color: "var(--text)",
  outline: "none",
};

const paginationStyle: CSSProperties = {
  display: "flex",
  gap: 12,
  justifyContent: "flex-end",
  alignItems: "center",
  marginTop: 16,
};
