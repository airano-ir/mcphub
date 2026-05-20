import { Logo } from "../components/Logo";
import { Badge } from "../components/primitives";
import { Icons, type IconName } from "../components/icons";
import { useSession } from "../lib/queries";
import { useT } from "../lib/i18n";
import { PublicControls } from "../components/PublicControls";

const GITHUB_URL = "https://github.com/airano-ir/mcphub";
const BLOG_URL = "https://blog.palebluedot.live/";
const SUPPORT_URL = "https://nowpayments.io/donation/airano";
const PUBLIC_PLUGINS = [
  "WordPress",
  "WooCommerce",
  "WordPress Specialist",
  "Supabase",
  "OpenPanel",
  "Gitea",
  "n8n",
  "Coolify",
];

export function LandingPage() {
  const t = useT();
  const session = useSession();
  const signedIn = session.data?.authenticated === true;
  const servedFromPublicRoot =
    typeof window !== "undefined" && !window.location.pathname.startsWith("/dashboard");
  const dashboardPath = (path: string) => (servedFromPublicRoot ? `/dashboard${path}` : path);
  const primaryTo = signedIn ? dashboardPath("/overview") : dashboardPath("/onboarding");
  const primaryLabel = signedIn
    ? t("landing.continue_dashboard", "Continue to dashboard")
    : t("landing.start_60", "Start in 60 seconds");
  const secondaryTo = signedIn ? dashboardPath("/sites") : dashboardPath("/login");
  const secondaryLabel = signedIn ? t("my_sites", "Sites") : t("login.sign_in", "Sign in");

  return (
    <div className="landing-page" style={{ background: "var(--bg)", position: "relative", overflow: "hidden", minHeight: "100vh" }}>
      <nav
        style={{
          position: "sticky",
          top: 0,
          zIndex: 50,
          background: "oklch(from var(--bg) l c h / 0.7)",
          backdropFilter: "blur(12px)",
          WebkitBackdropFilter: "blur(12px)",
          borderBottom: "1px solid var(--border)",
        }}
      >
        <div className="container landing-nav-inner" style={{ display: "flex", alignItems: "center", minHeight: 64, gap: 24 }}>
          <span className="logo-wrap">
            <Logo size={26} />
            <span className="logo-text">
              MCP <span>·</span> Hub
            </span>
          </span>
          <div className="landing-nav-links" style={{ display: "flex", gap: 20, marginLeft: 24 }}>
            <a href="#features" className="body-sm" style={{ color: "var(--text-muted)" }}>
              {t("landing.nav.features", "Features")}
            </a>
            <a href="#integrations" className="body-sm" style={{ color: "var(--text-muted)" }}>
              {t("landing.nav.integrations", "Integrations")}
            </a>
            <a href={BLOG_URL} className="body-sm" style={{ color: "var(--text-muted)" }}>
              {t("landing.nav.blog", "Blog")}
            </a>
            <a href={GITHUB_URL} className="body-sm" style={{ color: "var(--text-muted)" }}>
              {t("landing.nav.docs", "Docs")}
            </a>
          </div>
          <div style={{ flex: 1 }} />
          <PublicControls compact />
          <a href={signedIn ? dashboardPath("/overview") : dashboardPath("/login")} className="btn btn-ghost btn-sm">
            {signedIn ? t("dashboard", "Dashboard") : t("login.sign_in", "Sign in")}
          </a>
          <a href={signedIn ? secondaryTo : primaryTo} className="btn btn-primary btn-sm">
            {signedIn ? t("nav.sites", "Sites") : t("landing.get_started", "Get started")}{" "}
            <Icons.arrow style={{ width: 12, height: 12 }} />
          </a>
        </div>
      </nav>

      <section className="landing-hero" style={{ position: "relative", paddingTop: 80, paddingBottom: 100 }}>
        <div
          className="orb"
          style={{
            width: 520,
            height: 520,
            background: "var(--brand-500)",
            top: -100,
            right: -80,
            animation: "float 18s ease-in-out infinite",
          }}
        />
        <div
          className="orb"
          style={{
            width: 420,
            height: 420,
            background: "var(--accent-500)",
            bottom: -180,
            left: -60,
            opacity: 0.25,
            animation: "float 22s ease-in-out infinite reverse",
          }}
        />
        <div
          className="grid-pattern"
          style={{
            position: "absolute",
            inset: 0,
            opacity: 0.4,
            maskImage: "radial-gradient(ellipse at center, black 30%, transparent 75%)",
            WebkitMaskImage: "radial-gradient(ellipse at center, black 30%, transparent 75%)",
          }}
        />

        <div className="container" style={{ position: "relative" }}>
          <div style={{ maxWidth: 820 }}>
            <Badge variant="brand" dot style={{ marginBottom: 20 }}>
              {t("landing.hero_badge", "MCP 1.0 · Claude · ChatGPT · Cursor · Gemini")}
            </Badge>
            <h1 className="h-display" style={{ margin: "0 0 24px", color: "var(--text)" }}>
              {t("landing.hero_title_line1", "One hub for every")}
              <br />
              <em>{t("landing.hero_title_em", "AI connection")}</em>{" "}
              {t("landing.hero_title_line2", "to your sites.")}
            </h1>
            <p
              style={{
                fontSize: 19,
                lineHeight: 1.55,
                color: "var(--text-muted)",
                maxWidth: 640,
                margin: 0,
              }}
            >
              {t(
                "landing.hero_body",
                "MCP Hub is the control plane between your self-hosted services and the AI tools that work on them. Issue keys, connect Claude.ai, Claude Desktop, ChatGPT, Cursor, or Codex, and review every call from one clean surface.",
              )}
            </p>
            <div className="landing-hero-actions" style={{ display: "flex", gap: 12, marginTop: 32 }}>
              <a href={primaryTo} className="btn btn-primary btn-lg">
                {primaryLabel} <Icons.arrow style={{ width: 14, height: 14 }} />
              </a>
              <a href={secondaryTo} className="btn btn-secondary btn-lg">
                <Icons.sparkles style={{ width: 14, height: 14 }} />
                {secondaryLabel}
              </a>
            </div>
          </div>
        </div>
      </section>

      <section
        id="integrations"
        style={{ padding: "80px 0", borderTop: "1px solid var(--border)" }}
      >
        <div className="container">
          <div style={{ maxWidth: 620, marginBottom: 36 }}>
            <div className="eyebrow" style={{ marginBottom: 12 }}>
              {t("landing.integrations.eyebrow", "Integrations")}
            </div>
            <h2 className="h-1" style={{ margin: 0 }}>
              {t("landing.integrations.title", "Service-specific tools, one MCP surface.")}
            </h2>
          </div>
          <div className="landing-integrations-grid" style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 14 }}>
            {PUBLIC_PLUGINS.map((name) => (
              <div key={name} className="tile" style={{ padding: 18 }}>
                <div className="h-3" style={{ margin: 0 }}>
                  {name}
                </div>
                <div className="caption" style={{ marginTop: 6 }}>
                  {t("landing.integrations.tile", "Scoped tools, keys, health, and audit logs.")}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section
        id="features"
        style={{ padding: "80px 0", borderTop: "1px solid var(--border)" }}
      >
        <div className="container">
          <div style={{ maxWidth: 600, marginBottom: 48 }}>
            <div className="eyebrow" style={{ marginBottom: 12 }}>
              {t("landing.features_eyebrow", "Features")}
            </div>
            <h2 className="h-1" style={{ margin: 0 }}>
              {t("landing.features_title", "Everything your AI agents need, nothing they don't.")}
            </h2>
          </div>
          <div className="landing-features-grid" style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 20 }}>
            {(
              [
                {
                  icon: "sites",
                  titleKey: "landing.feature.sites.title",
                  title: "Services as first-class objects",
                  descKey: "landing.feature.sites.desc",
                  desc: "Register WordPress, WooCommerce, WordPress Specialist, Supabase, OpenPanel, Gitea, n8n, and Coolify. Each service becomes a discoverable MCP resource with its own tools and access level.",
                  tagKey: "landing.feature.sites.tag",
                  tag: "Core",
                },
                {
                  icon: "key",
                  titleKey: "landing.feature.keys.title",
                  title: "Scoped API keys",
                  descKey: "landing.feature.keys.desc",
                  desc: "Create keys for one service or all sites. Tool tiers stay service-specific and can be tightened later.",
                  tagKey: "landing.feature.keys.tag",
                  tag: "Security",
                },
                {
                  icon: "shield",
                  titleKey: "landing.feature.oauth.title",
                  title: "OAuth 2.1 + PKCE",
                  descKey: "landing.feature.oauth.desc",
                  desc: "Connect browser-based clients like Claude.ai Connectors and ChatGPT, while desktop clients can use direct URLs or bearer tokens.",
                  tagKey: "landing.feature.oauth.tag",
                  tag: "Auth",
                },
                {
                  icon: "activity",
                  titleKey: "landing.feature.health.title",
                  title: "Service health",
                  descKey: "landing.feature.health.desc",
                  desc: "Track credential checks, latency, and service status so agents know what is available before they act.",
                  tagKey: "landing.feature.health.tag",
                  tag: "Observability",
                },
                {
                  icon: "logs",
                  titleKey: "landing.feature.audit.title",
                  title: "Full audit trail",
                  descKey: "landing.feature.audit.desc",
                  desc: "Every tool call, auth event, and settings change is searchable and tied back to the user or key.",
                  tagKey: "landing.feature.audit.tag",
                  tag: "Compliance",
                },
                {
                  icon: "zap",
                  titleKey: "landing.feature.protocol.title",
                  title: "MCP-native tools",
                  descKey: "landing.feature.protocol.desc",
                  desc: "Expose plugin tools through MCP without forcing users to learn every service API by hand.",
                  tagKey: "landing.feature.protocol.tag",
                  tag: "Protocol",
                },
              ] as {
                icon: IconName;
                titleKey: string;
                title: string;
                descKey: string;
                desc: string;
                tagKey: string;
                tag: string;
              }[]
            ).map((f) => {
              const Ic = Icons[f.icon];
              return (
                <div key={f.titleKey} className="tile" style={{ padding: 24 }}>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "flex-start",
                      marginBottom: 18,
                    }}
                  >
                    <div
                      style={{
                        width: 38,
                        height: 38,
                        borderRadius: 10,
                        background: "oklch(from var(--brand-500) l c h / 0.12)",
                        color: "var(--brand-400)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        border: "1px solid oklch(from var(--brand-500) l c h / 0.2)",
                      }}
                    >
                      <Ic style={{ width: 18, height: 18 }} />
                    </div>
                    <Badge>{t(f.tagKey, f.tag)}</Badge>
                  </div>
                  <div className="h-3" style={{ marginBottom: 8 }}>
                    {t(f.titleKey, f.title)}
                  </div>
                  <div className="body-sm" style={{ color: "var(--text-muted)" }}>
                    {t(f.descKey, f.desc)}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </section>

      <section style={{ padding: "80px 0" }}>
        <div className="container">
          <div
            style={{
              border: "1px solid var(--border)",
              borderRadius: 20,
              padding: "56px 48px",
              background:
                "linear-gradient(135deg, oklch(from var(--brand-500) l c h / 0.15), oklch(from var(--accent-500) l c h / 0.08) 60%, var(--bg-elevated) 100%)",
              position: "relative",
              overflow: "hidden",
            }}
          >
            <div className="dot-pattern" style={{ position: "absolute", inset: 0, opacity: 0.3 }} />
            <div
              style={{
                position: "relative",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 40,
                flexWrap: "wrap",
              }}
            >
              <div style={{ maxWidth: 560 }}>
                <h2 className="h-1" style={{ margin: "0 0 10px" }}>
                  {t("landing.cta_title", "Spin up your hub, in a minute.")}
                </h2>
                <p className="body" style={{ color: "var(--text-muted)", margin: 0 }}>
                  {t(
                    "landing.cta_body",
                    "Deploy on any Coolify instance. Free for personal use. Self-hosted forever.",
                  )}
                </p>
              </div>
              <div style={{ display: "flex", gap: 10 }}>
                <a href={primaryTo} className="btn btn-primary btn-lg">
                  {signedIn ? t("dashboard", "Dashboard") : t("landing.create_account", "Create account")}{" "}
                  <Icons.arrow style={{ width: 14, height: 14 }} />
                </a>
                <a href={GITHUB_URL} className="btn btn-secondary btn-lg">
                  <Icons.github style={{ width: 14, height: 14 }} />
                  GitHub
                </a>
              </div>
            </div>
          </div>
        </div>
      </section>

      <footer style={{ borderTop: "1px solid var(--border)", padding: "40px 0 60px" }}>
        <div
          className="container"
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            gap: 40,
            flexWrap: "wrap",
          }}
        >
          <div style={{ maxWidth: 320 }}>
            <span className="logo-wrap" style={{ marginBottom: 12 }}>
              <Logo size={22} />
              <span className="logo-text">
                MCP <span>·</span> Hub
              </span>
            </span>
            <div className="caption">
              {t(
                "landing.footer_tagline",
                "The self-hosted MCP control plane for WordPress, Coolify, Gitea, and more.",
              )}
            </div>
          </div>
          <div style={{ display: "flex", gap: 18, flexWrap: "wrap" }}>
            <a href={BLOG_URL} className="body-sm" style={{ color: "var(--text-muted)" }}>
              {t("landing.nav.blog", "Blog")}
            </a>
            <a href={GITHUB_URL} className="body-sm" style={{ color: "var(--text-muted)" }}>
              GitHub
            </a>
            <a href={SUPPORT_URL} className="body-sm" style={{ color: "var(--text-muted)" }}>
              {t("support_mcphub", "Support MCP Hub")}
            </a>
          </div>
        </div>
        <div
          className="container"
          style={{
            marginTop: 32,
            paddingTop: 20,
            borderTop: "1px solid var(--border)",
            display: "flex",
            justifyContent: "space-between",
            fontSize: 12,
            color: "var(--text-subtle)",
          }}
        >
          <div>© airano.ir · MCP Hub</div>
        </div>
      </footer>
    </div>
  );
}
