import { useState } from "react";
import { LogoWordmark } from "../components/Logo";
import { Btn, Avatar } from "../components/primitives";
import { Icons } from "../components/icons";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { useSession } from "../lib/queries";
import { getCsrfToken } from "../lib/api";
import { useT } from "../lib/i18n";
import { PublicControls } from "../components/PublicControls";

function normalizeClientNext(raw: string | null): string {
  if (!raw || !raw.startsWith("/")) return "/overview";
  const dashboardPath = raw.startsWith("/dashboard/") ? raw.slice("/dashboard".length) || "/overview" : raw;
  if (
    dashboardPath === "/" ||
    dashboardPath === "/dashboard" ||
    dashboardPath === "/dashboard/" ||
    dashboardPath === "/landing" ||
    dashboardPath === "/onboarding" ||
    dashboardPath.startsWith("/login")
  ) {
    return "/overview";
  }
  if (raw.startsWith("/dashboard/")) return dashboardPath;
  return raw;
}

function toServerNext(nextPath: string): string {
  return nextPath.startsWith("/dashboard") ? nextPath : `/dashboard${nextPath}`;
}

// Login page. Master-key login posts to /api/dashboard/login (JSON, G.12);
// OAuth still uses /auth/{provider}. Server returns JSON so the SPA never has
// to hand off to the legacy Jinja form.
export function LoginPage() {
  const t = useT();
  const [apiKey, setApiKey] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const location = useLocation();
  const session = useSession();
  const nextPath = normalizeClientNext(new URLSearchParams(location.search).get("next"));

  // Hide the master-key form when the server has DISABLE_MASTER_KEY_LOGIN=true
  // (production posture). Default to false until /api/me lands so the form
  // never flashes on a host that has it disabled.
  const masterKeyEnabled = session.data?.master_key_login_enabled === true;

  const onMasterKey = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setSubmitting(true);
    try {
      const csrf = getCsrfToken() ?? session.data?.csrf_token ?? "";
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (csrf) headers["X-CSRF-Token"] = csrf;
      const res = await fetch("/api/dashboard/login", {
        method: "POST",
        body: JSON.stringify({ api_key: apiKey, next: toServerNext(nextPath) }),
        credentials: "include",
        headers,
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok && data.ok) {
        await queryClient.invalidateQueries({ queryKey: ["me"] });
        await queryClient.refetchQueries({ queryKey: ["me"], type: "active" });
        navigate(normalizeClientNext(typeof data.next === "string" ? data.next : nextPath), {
          replace: true,
        });
      } else if (res.status === 429 || data.error === "rate_limit") {
        setError(t("login.rate_limit", "Too many attempts. Please try again later."));
      } else if (res.status === 401 || data.error === "invalid") {
        setError(t("login.invalid_key", "Invalid API key"));
      } else {
        setError(`${t("login.failed", "Sign in failed")} (${res.status})`);
      }
    } catch (err: any) {
      setError(err.message || t("login.failed", "Sign in failed"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="login-shell">
      <div className="login-form-pane">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "auto" }}>
          <Link to="/landing" className="logo-link">
            <LogoWordmark size={28} />
          </Link>
          <PublicControls compact />
        </div>
        <div className="login-form-inner">
          <h1 className="h-1" style={{ margin: "0 0 8px" }}>
            {t("login.welcome", "Welcome back")}
          </h1>
          <div className="body" style={{ color: "var(--text-muted)", marginBottom: 28 }}>
            {t("login.subtitle", "Sign in to your MCP Hub")}
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            <a href="/auth/github" className="btn btn-secondary btn-lg">
              <Icons.github style={{ width: 16, height: 16 }} />
              {t("login.continue_github", "Continue with GitHub")}
            </a>
            <a href="/auth/google" className="btn btn-secondary btn-lg">
              <Icons.sparkles style={{ width: 16, height: 16 }} />
              {t("login.continue_google", "Continue with Google")}
            </a>
            {masterKeyEnabled && (
              <>
                <div className="login-divider">
                  <div className="login-divider-line" />
                  <span>{t("login.or_admin_key", "or admin key")}</span>
                  <div className="login-divider-line" />
                </div>
                <form onSubmit={onMasterKey} style={{ display: "contents" }}>
                  <div className="field">
                    <label>{t("login.master_key_label", "Master API key")}</label>
                    <input
                      className="input"
                      type="password"
                      placeholder="••••••••"
                      value={apiKey}
                      onChange={(e) => setApiKey(e.target.value)}
                    />
                  </div>
                  {error && <div className="alert alert-danger">{error}</div>}
                  <Btn variant="primary" size="lg" type="submit" disabled={!apiKey || submitting}>
                    {submitting ? t("login.signing_in", "Signing in…") : t("login.sign_in", "Sign in")}
                  </Btn>
                </form>
              </>
            )}
          </div>
        </div>
        <div className="caption login-footer">
          {t("login.footer", "© airano.ir · Self-hosted · Open source")}
        </div>
      </div>
      <div className="login-testimonial-pane">
        <div
          className="orb"
          style={{
            width: 500,
            height: 500,
            background: "var(--brand-500)",
            top: "-10%",
            insetInlineStart: "-10%",
            opacity: 0.35,
          }}
        />
        <div
          className="orb"
          style={{
            width: 420,
            height: 420,
            background: "var(--accent-500)",
            bottom: "-15%",
            insetInlineEnd: "-20%",
            opacity: 0.25,
          }}
        />
        <div className="grid-pattern" style={{ position: "absolute", inset: 0, opacity: 0.4 }} />
        <div className="login-testimonial-inner">
          <blockquote className="login-quote">
            {t(
              "login.testimonial",
              "“My six AI tools now share one key, one audit log, one revoke button. I shouldn't be this happy about a dashboard.”",
            )}
          </blockquote>
          <div style={{ display: "flex", gap: 10, alignItems: "center", marginTop: 24 }}>
            <Avatar name="Lena K." size={36} />
            <div>
              <div style={{ fontWeight: 500 }}>{t("login.testimonial_author", "Lena K.")}</div>
              <div className="caption">
                {t("login.testimonial_role", "Staff eng, self-hosted everything")}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
