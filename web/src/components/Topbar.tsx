import { useEffect, useRef, useState, type ReactNode } from "react";
import { Icons } from "./icons";
import { isMobileViewport, useUiStore, type ThemePref } from "../lib/store";
import { useT } from "../lib/i18n";

const THEME_ORDER: ThemePref[] = ["light", "dark", "system"];

export function Topbar({
  title,
  crumbs = [],
  actions,
  showThemeToggle = true,
}: {
  title?: string;
  crumbs?: string[];
  actions?: ReactNode;
  showThemeToggle?: boolean;
}) {
  const t = useT();
  const [langOpen, setLangOpen] = useState(false);
  const langMenuRef = useRef<HTMLDivElement | null>(null);
  const { theme, setTheme, lang, setLang, sidebarCollapsed, toggleSidebar, sidebarMobileOpen, toggleSidebarMobile } =
    useUiStore();
  const ThemeIcon = theme === "dark" ? Icons.moon : theme === "light" ? Icons.sun : Icons.monitor;
  const cycleTheme = () => {
    const idx = THEME_ORDER.indexOf(theme);
    setTheme(THEME_ORDER[(idx + 1) % THEME_ORDER.length]);
  };
  // Same button serves two layouts: on phones it toggles the slide-in
  // drawer, on desktops it collapses the sidebar to an icon rail.
  const onMenuClick = () => {
    if (isMobileViewport()) toggleSidebarMobile();
    else toggleSidebar();
  };
  const menuExpanded = isMobileViewport() ? sidebarMobileOpen : !sidebarCollapsed;

  useEffect(() => {
    if (!langOpen) return;
    const onPointerDown = (event: PointerEvent) => {
      if (!langMenuRef.current?.contains(event.target as Node)) {
        setLangOpen(false);
      }
    };
    window.addEventListener("pointerdown", onPointerDown);
    return () => window.removeEventListener("pointerdown", onPointerDown);
  }, [langOpen]);

  const chooseLang = (next: "en" | "fa") => {
    setLang(next);
    setLangOpen(false);
  };

  return (
    <div className="topbar">
      <button
        type="button"
        className="btn btn-ghost btn-sm topbar-menu-btn"
        onClick={onMenuClick}
        title={t("topbar.toggle_sidebar", "Toggle sidebar")}
        aria-label={t("topbar.toggle_sidebar", "Toggle sidebar")}
        aria-expanded={menuExpanded}
        style={{ padding: 6 }}
      >
        <Icons.menu style={{ width: 18, height: 18 }} />
      </button>
      <div className="topbar-crumbs">
        {crumbs.map((c, i) => (
          <span key={i} style={{ display: "inline-flex", alignItems: "center", gap: 10 }}>
            {i > 0 ? <Icons.chevR style={{ width: 12, height: 12, color: "var(--text-subtle)" }} /> : null}
            <span style={{ color: i === crumbs.length - 1 ? "var(--text)" : "var(--text-muted)" }}>{c}</span>
          </span>
        ))}
        {!crumbs.length && title ? <span style={{ fontWeight: 500 }}>{title}</span> : null}
      </div>
      <div style={{ flex: 1 }} />
      {actions ? <div className="topbar-actions">{actions}</div> : null}
      {showThemeToggle ? (
        <div className="topbar-controls">
          <div className="lang-menu-wrap" ref={langMenuRef}>
            <button
              type="button"
              className="btn btn-ghost btn-sm topbar-lang-btn"
              onClick={() => setLangOpen((open) => !open)}
              title={t("topbar.change_language", "Change language")}
              aria-label={t("topbar.change_language", "Change language")}
              aria-haspopup="menu"
              aria-expanded={langOpen}
              style={{ padding: "6px 10px", display: "inline-flex", alignItems: "center", gap: 6 }}
            >
              <Icons.globe style={{ width: 14, height: 14 }} />
              <span style={{ fontSize: 11.5, fontWeight: 600, letterSpacing: "0.06em" }}>
                {lang === "fa" ? "FA" : "EN"}
              </span>
            </button>
            {langOpen ? (
              <div className="lang-menu" role="menu" aria-label={t("topbar.change_language", "Change language")}>
                <button
                  type="button"
                  role="menuitemradio"
                  aria-checked={lang === "en"}
                  className={lang === "en" ? "is-active" : ""}
                  onClick={() => chooseLang("en")}
                >
                  <span>English</span>
                  {lang === "en" ? <Icons.check style={{ width: 14, height: 14 }} /> : null}
                </button>
                <button
                  type="button"
                  role="menuitemradio"
                  aria-checked={lang === "fa"}
                  className={lang === "fa" ? "is-active" : ""}
                  onClick={() => chooseLang("fa")}
                >
                  <span>فارسی</span>
                  {lang === "fa" ? <Icons.check style={{ width: 14, height: 14 }} /> : null}
                </button>
              </div>
            ) : null}
          </div>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={cycleTheme}
            title={`${t("topbar.cycle_theme", "Switch theme")} · ${t(`theme.${theme}`, theme)}`}
            aria-label={t("topbar.cycle_theme", "Switch theme")}
            style={{ padding: 6 }}
          >
            <ThemeIcon style={{ width: 16, height: 16 }} />
          </button>
          <button
            type="button"
            className="btn btn-ghost btn-sm topbar-notifs"
            style={{ padding: 6 }}
            title={t("topbar.notifications", "Notifications")}
            aria-label={t("topbar.notifications", "Notifications")}
          >
            <Icons.bell style={{ width: 16, height: 16 }} />
          </button>
        </div>
      ) : null}
    </div>
  );
}
