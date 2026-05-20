import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { LogoWordmark } from "../components/Logo";
import { Card, Btn } from "../components/primitives";
import { Icons } from "../components/icons";
import { useT } from "../lib/i18n";
import { PublicControls } from "../components/PublicControls";

// Onboarding is a redesigned welcome flow that bridges to OAuth login and the
// native SPA Sites dialog for the actual work.
export function OnboardingPage() {
  const t = useT();
  const [step, setStep] = useState(0);
  const steps = [
    t("onboarding.step_signin", "Sign in"),
    t("onboarding.step_add_site", "Add a site"),
    t("onboarding.step_get_key", "Get your key"),
  ];
  const navigate = useNavigate();

  return (
    <div style={{ minHeight: "100vh", background: "var(--bg)", position: "relative" }}>
      <div className="onboarding-topbar">
        <Link to="/landing" className="logo-link">
          <LogoWordmark size={26} />
        </Link>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <PublicControls compact />
          <Link to="/login" className="btn btn-ghost btn-sm">
            {t("onboarding.have_account", "Already have an account?")}{" "}
            <span style={{ color: "var(--brand-400)" }}>{t("login.sign_in", "Sign in")}</span>
          </Link>
        </div>
      </div>

      <div className="onboarding-body">
        <div className="stepper onboarding-stepper">
          {steps.map((s, i) => (
            <div
              key={s}
              className={`step ${step === i ? "is-active" : ""} ${step > i ? "is-done" : ""}`}
            >
              <div className="n">
                {step > i ? <Icons.check style={{ width: 12, height: 12 }} /> : i + 1}
              </div>
              <div>
                <div style={{ fontSize: 13, fontWeight: 500 }}>{s}</div>
                <div className="caption">
                  {t("onboarding.step_n_of", "Step {n} of {total}")
                    .replace("{n}", String(i + 1))
                    .replace("{total}", String(steps.length))}
                </div>
              </div>
            </div>
          ))}
        </div>

        <Card>
          {step === 0 && (
            <div style={{ padding: 28 }}>
              <h2 className="h-2" style={{ marginTop: 0 }}>
                {t("onboarding.signin_title", "Sign in with your GitHub or Google account")}
              </h2>
              <div className="body" style={{ color: "var(--text-muted)", marginBottom: 20 }}>
                {t(
                  "onboarding.signin_body",
                  "We use OAuth — no passwords, no email verification dance. Takes a few seconds.",
                )}
              </div>
              <div className="onboarding-oauth">
                <a href="/auth/github" className="btn btn-secondary btn-lg">
                  <Icons.github style={{ width: 16, height: 16 }} />
                  {t("login.continue_github", "Continue with GitHub")}
                </a>
                <a href="/auth/google" className="btn btn-secondary btn-lg">
                  <Icons.sparkles style={{ width: 16, height: 16 }} />
                  {t("login.continue_google", "Continue with Google")}
                </a>
              </div>
              <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 24 }}>
                <Btn variant="ghost" onClick={() => setStep(1)} iconRight="arrow">
                  {t("onboarding.skip_signed_in", "Skip — already signed in")}
                </Btn>
              </div>
            </div>
          )}

          {step === 1 && (
            <div style={{ padding: 28 }}>
              <h2 className="h-2" style={{ marginTop: 0 }}>
                {t("onboarding.add_site_title", "Add your first site")}
              </h2>
              <div className="body" style={{ color: "var(--text-muted)", marginBottom: 20 }}>
                {t(
                  "onboarding.add_site_body",
                  "Pick a Coolify project, WordPress site, Gitea instance, or any other supported plugin. You can add more later.",
                )}
              </div>
              <div className="onboarding-actions">
                <Link to="/sites?create=1" className="btn btn-primary btn-lg">
                  {t("onboarding.add_site_cta", "Add a site")}{" "}
                  <Icons.arrow style={{ width: 14, height: 14 }} />
                </Link>
                <Btn variant="ghost" onClick={() => setStep(0)}>
                  {t("back", "Back")}
                </Btn>
                <Btn variant="ghost" onClick={() => setStep(2)} iconRight="arrow">
                  {t("onboarding.skip", "Skip")}
                </Btn>
              </div>
            </div>
          )}

          {step === 2 && (
            <div style={{ padding: 28 }}>
              <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 8 }}>
                <div
                  style={{
                    width: 28,
                    height: 28,
                    borderRadius: "50%",
                    background: "var(--success)",
                    color: "#000",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  <Icons.check style={{ width: 14, height: 14 }} />
                </div>
                <h2 className="h-2" style={{ margin: 0 }}>
                  {t("onboarding.done_title", "You're set")}
                </h2>
              </div>
              <div className="body" style={{ color: "var(--text-muted)", marginBottom: 24 }}>
                {t(
                  "onboarding.done_body",
                  "Head over to API keys to create one, or jump to Connect to wire up an AI client.",
                )}
              </div>
              <div className="onboarding-actions">
                <Btn variant="primary" size="lg" iconRight="arrow" onClick={() => navigate("/connect")}>
                  {t("onboarding.connect_client", "Connect a client")}
                </Btn>
                <Btn variant="secondary" size="lg" onClick={() => navigate("/overview")}>
                  {t("onboarding.go_dashboard", "Go to dashboard")}
                </Btn>
              </div>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
