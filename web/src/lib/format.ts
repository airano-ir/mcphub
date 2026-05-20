// Formatting helpers — primarily for bilingual number rendering.
// Persian numeral output uses Intl.NumberFormat("fa-IR") which gives both
// the digit shaping (۰-۹) and grouping (٬) the user expects.

import type { Lang } from "./store";

export function fmtNumber(n: number | string | null | undefined, lang: Lang, fallback = "—"): string {
  if (n === null || n === undefined || n === "") return fallback;
  const num = typeof n === "string" ? Number(n) : n;
  if (!Number.isFinite(num)) return fallback;
  return new Intl.NumberFormat(lang === "fa" ? "fa-IR" : "en-US").format(num);
}

export function fmtInt(n: number | null | undefined, lang: Lang, fallback = "—"): string {
  if (n === null || n === undefined || !Number.isFinite(n)) return fallback;
  return fmtNumber(Math.round(n), lang, fallback);
}

// Format an ISO timestamp for display. In FA the Persian (Shamsi/Jalali)
// calendar is the user expectation — `Intl.DateTimeFormat("fa-IR")` already
// emits Shamsi by default, so we just opt into the right field set. Falls
// through cleanly when `iso` is null/empty/invalid.
export function fmtDateTime(iso: string | null | undefined, lang: Lang, fallback = "—"): string {
  if (!iso) return fallback;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return fallback;
  if (lang === "fa") {
    // Calendar defaults to "persian" for fa-IR, but pass it explicitly so an
    // older locale data store can't slip back to Gregorian.
    return new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    }).format(d);
  }
  return new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(d);
}

// Backend writes `status="active"` for sites that pass connection tests
// (see core/site_api.py:test_site_connection). The SPA's badges and the
// "Healthy sites" card both reason in terms of "healthy". This helper
// bridges the vocabulary AND folds the `last_tested_at + untested` race
// into a dedicated `unknown` bucket so the UI never says "untested" next
// to a real timestamp.
export type SiteDisplayStatus = "healthy" | "warning" | "error" | "unknown" | "untested";

export function normalizeSiteStatus(
  status: string | null | undefined,
  lastTestedAt: string | null | undefined,
): SiteDisplayStatus {
  if (status === "healthy" || status === "active") return "healthy";
  if (status === "warning") return "warning";
  if (status === "error") return "error";
  if (status === "unknown") return "unknown";
  return lastTestedAt ? "unknown" : "untested";
}
