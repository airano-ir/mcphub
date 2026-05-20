import { useEffect, useRef, useState } from "react";
import { Icons } from "./icons";
import { useT } from "../lib/i18n";
import { useUiStore, type ThemePref } from "../lib/store";

const THEME_ORDER: ThemePref[] = ["light", "dark", "system"];

export function PublicControls({ compact = false }: { compact?: boolean }) {
  const t = useT();
  const [langOpen, setLangOpen] = useState(false);
  const langMenuRef = useRef<HTMLDivElement | null>(null);
  const { theme, setTheme, lang, setLang } = useUiStore();
  const ThemeIcon = theme === "dark" ? Icons.moon : theme === "light" ? Icons.sun : Icons.monitor;

  const cycleTheme = () => {
    const idx = THEME_ORDER.indexOf(theme);
    setTheme(THEME_ORDER[(idx + 1) % THEME_ORDER.length]);
  };

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
    <div className="public-controls" aria-label={t("topbar.change_language", "Change language")}>
      <div className="lang-menu-wrap" ref={langMenuRef}>
        <button
          type="button"
          className="btn btn-ghost btn-sm topbar-lang-btn"
          onClick={() => setLangOpen((open) => !open)}
          title={t("topbar.change_language", "Change language")}
          aria-label={t("topbar.change_language", "Change language")}
          aria-haspopup="menu"
          aria-expanded={langOpen}
          style={{ padding: compact ? "6px 8px" : "6px 10px" }}
        >
          <Icons.globe style={{ width: 14, height: 14 }} />
          <span style={{ fontSize: 11.5, fontWeight: 600 }}>{lang === "fa" ? "FA" : "EN"}</span>
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
    </div>
  );
}
