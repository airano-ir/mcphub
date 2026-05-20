// Zustand UI store — theme, lang, brand hue, density, sidebar collapse.
// Persisted to localStorage so the shell remembers preferences across reloads.
import { create } from "zustand";
import { persist } from "zustand/middleware";

export type ThemePref = "dark" | "light" | "system";
export type Theme = ThemePref; // legacy alias — keep for callers that import {Theme}
export type Lang = "en" | "fa";

type UiState = {
  theme: ThemePref;
  lang: Lang;
  brandHue: number;
  density: number;
  /** Desktop only — narrow icon-rail vs full-width sidebar. Persisted. */
  sidebarCollapsed: boolean;
  /** Mobile only — slide-in drawer open vs hidden. Resets on each visit. */
  sidebarMobileOpen: boolean;
  toast: string;
  setTheme: (t: ThemePref) => void;
  setLang: (l: Lang) => void;
  setBrandHue: (h: number) => void;
  setDensity: (d: number) => void;
  setSidebarCollapsed: (v: boolean) => void;
  toggleSidebar: () => void;
  setSidebarMobileOpen: (v: boolean) => void;
  toggleSidebarMobile: () => void;
  setToast: (m: string) => void;
};

export const useUiStore = create<UiState>()(
  persist(
    (set, get) => ({
      theme: "system",
      lang: "en",
      brandHue: 205,
      density: 1,
      sidebarCollapsed: false,
      sidebarMobileOpen: false,
      toast: "",
      setTheme: (theme) => set({ theme }),
      setLang: (lang) => set({ lang }),
      setBrandHue: (brandHue) => set({ brandHue }),
      setDensity: (density) => set({ density }),
      setSidebarCollapsed: (sidebarCollapsed) => set({ sidebarCollapsed }),
      toggleSidebar: () => set({ sidebarCollapsed: !get().sidebarCollapsed }),
      setSidebarMobileOpen: (sidebarMobileOpen) => set({ sidebarMobileOpen }),
      toggleSidebarMobile: () => set({ sidebarMobileOpen: !get().sidebarMobileOpen }),
      setToast: (toast) => set({ toast }),
    }),
    {
      name: "mcphub-ui",
      // Mobile drawer state is intentionally NOT persisted — re-opening the
      // tab should land you with the drawer closed regardless of how you
      // last left it.
      partialize: (s) => ({
        theme: s.theme,
        lang: s.lang,
        brandHue: s.brandHue,
        density: s.density,
        sidebarCollapsed: s.sidebarCollapsed,
      }),
    },
  ),
);

// Single source of truth for the "is this a mobile viewport?" check. Used by
// the Topbar toggle button to decide whether to open the mobile drawer or
// collapse the desktop sidebar.
export const MOBILE_QUERY = "(max-width: 900px)";
export function isMobileViewport(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return window.matchMedia(MOBILE_QUERY).matches;
}

function resolveTheme(pref: ThemePref): "dark" | "light" {
  if (pref !== "system") return pref;
  if (typeof window === "undefined" || !window.matchMedia) return "dark";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function applyUiToDom(state: Pick<UiState, "theme" | "lang" | "brandHue" | "density">) {
  const html = document.documentElement;
  html.setAttribute("data-theme", resolveTheme(state.theme));
  html.setAttribute("data-theme-pref", state.theme);
  html.setAttribute("dir", state.lang === "fa" ? "rtl" : "ltr");
  html.setAttribute("lang", state.lang);
  html.style.setProperty("--brand-hue", String(state.brandHue));
  html.style.setProperty("--density", String(state.density));
}
