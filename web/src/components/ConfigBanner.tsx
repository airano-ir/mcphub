import { useState } from "react";
import { useConfigHealth, useSession } from "../lib/queries";
import { useUiStore } from "../lib/store";

// Admin-only banner that surfaces operator misconfiguration warnings
// (missing MASTER_API_KEY, ephemeral session secret, disabled site
// management, …) returned by GET /api/dashboard/config-health. Each warning
// ships bilingual copy, so we just pick the field for the active language.
//
// Dismissal is per-tab (sessionStorage) and keyed by the set of active
// warning codes: fixing one config issue or hitting a new one re-shows the
// banner, but routine navigation within a session does not nag.
export function ConfigBanner() {
  const { data: session } = useSession();
  const isAdmin = session?.is_admin ?? false;
  const lang = useUiStore((s) => s.lang);
  const { data: warnings } = useConfigHealth(isAdmin);
  const [dismissedKey, setDismissedKey] = useState<string | null>(() => {
    try {
      return sessionStorage.getItem("mcphub-confighealth-dismissed");
    } catch {
      return null;
    }
  });

  if (!isAdmin || !warnings || warnings.length === 0) return null;

  const key = warnings.map((w) => w.code).sort().join(",");
  if (dismissedKey === key) return null;

  const hasCritical = warnings.some((w) => w.severity === "critical");
  const accent = hasCritical ? "var(--danger, #e5484d)" : "var(--warning, #d9920a)";

  const dismiss = () => {
    try {
      sessionStorage.setItem("mcphub-confighealth-dismissed", key);
    } catch {
      /* sessionStorage unavailable — banner just won't persist dismissal */
    }
    setDismissedKey(key);
  };

  const heading =
    lang === "fa"
      ? `هشدار پیکربندی (${warnings.length} مورد)`
      : `Configuration warnings (${warnings.length})`;
  const dismissLabel = lang === "fa" ? "بستن" : "Dismiss";

  return (
    <div
      role="alert"
      style={{
        margin: "16px 16px 0",
        padding: "14px 16px",
        borderInlineStart: `3px solid ${accent}`,
        background: "var(--surface-2, rgba(127,127,127,0.08))",
        borderRadius: 8,
        fontSize: 14,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
        <strong style={{ color: accent }}>{heading}</strong>
        <button
          type="button"
          onClick={dismiss}
          className="btn btn-ghost btn-sm"
          style={{ flexShrink: 0 }}
        >
          {dismissLabel}
        </button>
      </div>
      <ul style={{ margin: "10px 0 0", paddingInlineStart: 18, display: "grid", gap: 8 }}>
        {warnings.map((w) => (
          <li key={w.code}>
            <span style={{ fontWeight: 600 }}>{lang === "fa" ? w.title_fa : w.title_en}</span>
            <div style={{ color: "var(--text-muted)", marginTop: 2 }}>
              {lang === "fa" ? w.detail_fa : w.detail_en}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
