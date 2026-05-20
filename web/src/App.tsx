import { useEffect } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Shell } from "./components/Shell";
import { applyUiToDom, useUiStore } from "./lib/store";
import { useSession } from "./lib/queries";
import { Toast } from "./components/primitives";
import { ApiError, setCsrfToken } from "./lib/api";

import { LandingPage } from "./pages/Landing";
import { LoginPage } from "./pages/Login";
import { OnboardingPage } from "./pages/Onboarding";
import { OverviewPage } from "./pages/Overview";
import { SitesPage } from "./pages/Sites";
import { SiteToolsPage } from "./pages/SiteTools";
import { ConnectPage } from "./pages/Connect";
import { ApiKeysPage } from "./pages/ApiKeys";
import { OAuthClientsPage } from "./pages/OAuthClients";
import { HealthPage } from "./pages/Health";
import { AuditLogsPage } from "./pages/AuditLogs";
import { SettingsPage } from "./pages/Settings";
import { NotFoundPage } from "./pages/NotFound";

function RequireAuth({ children, adminOnly = false }: { children: React.ReactNode; adminOnly?: boolean }) {
  const { data, isLoading, error } = useSession();
  const location = useLocation();

  if (isLoading) {
    return (
      <div style={{ minHeight: "100vh", display: "grid", placeItems: "center", color: "var(--text-muted)" }}>
        Loading…
      </div>
    );
  }

  const unauthenticated =
    (error instanceof ApiError && error.status === 401) || data?.authenticated === false;

  if (unauthenticated) {
    // Post-G.12 the SPA owns `/dashboard/*`; the login page is its own SPA
    // route so we can client-side navigate instead of a full reload. Wrap in
    // a Navigate to preserve scroll + state across the protected → login
    // transition without a flash of the legacy form.
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={`/login?next=${next}`} replace />;
  }

  if (adminOnly && data && !data.is_admin) {
    return <Navigate to="/sites" replace />;
  }

  return <>{children}</>;
}

function RootPage() {
  const session = useSession();
  const isDashboardRoot =
    typeof window !== "undefined" &&
    (window.location.pathname === "/dashboard" || window.location.pathname === "/dashboard/");
  if (isDashboardRoot && session.data?.authenticated === true) {
    return <Navigate to="/overview" replace />;
  }
  return <LandingPage />;
}

export function App() {
  const ui = useUiStore();
  const { theme, lang, brandHue, density } = ui;
  const session = useSession();

  // Apply theme/lang/hue/density to <html> on every change.
  useEffect(() => {
    applyUiToDom({ theme, lang, brandHue, density });
  }, [theme, lang, brandHue, density]);

  // When the user picks "system" theme, follow OS-level preference changes
  // live (e.g. macOS auto dark mode at sunset) without a reload.
  useEffect(() => {
    if (theme !== "system" || typeof window === "undefined" || !window.matchMedia) return;
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => applyUiToDom({ theme, lang, brandHue, density });
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, [theme, lang, brandHue, density]);

  // Sync language from server session on the user's *first* visit only.
  // The zustand-persist middleware seeds `lang` from localStorage
  // synchronously, so if the user already has a stored choice we must not
  // overwrite it with whatever Accept-Language the server inferred — that
  // was forcing a refresh on /dashboard/* to flip back to English.
  useEffect(() => {
    if (!session.data?.lang) return;
    let userPicked = false;
    try {
      const persisted = localStorage.getItem("mcphub-ui");
      if (persisted) {
        const parsed = JSON.parse(persisted);
        if (parsed?.state?.lang) userPicked = true;
      }
    } catch {
      /* localStorage unavailable / corrupt — fall through to server hint */
    }
    if (userPicked) return;
    if (session.data.lang !== lang) ui.setLang(session.data.lang);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [session.data?.lang]);

  // Mirror the server-issued CSRF token into the api.ts module so every
  // mutating request can echo it as X-CSRF-Token. /api/me is fetched on
  // every mount and refreshed by react-query, so the token stays current.
  useEffect(() => {
    setCsrfToken(session.data?.csrf_token ?? null);
  }, [session.data?.csrf_token]);

  return (
    <>
      <Routes>
        {/* Public */}
        <Route path="/" element={<RootPage />} />
        <Route path="/landing" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/onboarding" element={<OnboardingPage />} />

        {/* Protected — wrapped in Shell */}
        <Route
          element={
            <RequireAuth>
              <Shell />
            </RequireAuth>
          }
        >
          <Route path="/overview" element={<OverviewPage />} />
          <Route path="/sites" element={<SitesPage />} />
          <Route path="/sites/:id/tools" element={<SiteToolsPage />} />
          <Route path="/connect" element={<ConnectPage />} />
          <Route path="/api-keys" element={<ApiKeysPage />} />
          <Route path="/settings" element={<SettingsPage />} />

          {/* Admin only */}
          <Route
            path="/oauth-clients"
            element={
              <RequireAuth adminOnly>
                <OAuthClientsPage />
              </RequireAuth>
            }
          />
          <Route
            path="/health"
            element={
              <RequireAuth adminOnly>
                <HealthPage />
              </RequireAuth>
            }
          />
          <Route
            path="/audit-logs"
            element={
              <RequireAuth adminOnly>
                <AuditLogsPage />
              </RequireAuth>
            }
          />
        </Route>

        <Route path="*" element={<NotFoundPage />} />
      </Routes>

      <Toast msg={ui.toast} onClose={() => ui.setToast("")} />
    </>
  );
}
