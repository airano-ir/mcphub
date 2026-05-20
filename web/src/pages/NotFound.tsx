import { Link } from "react-router-dom";
import { Btn } from "../components/primitives";
import { LogoWordmark } from "../components/Logo";
import { useT } from "../lib/i18n";

export function NotFoundPage() {
  const t = useT();
  const servedFromPublicRoot =
    typeof window !== "undefined" && !window.location.pathname.startsWith("/dashboard");
  const target = servedFromPublicRoot ? "/dashboard/overview" : "/overview";
  return (
    <div style={{ minHeight: "100vh", display: "grid", placeItems: "center", padding: 24 }}>
      <div style={{ maxWidth: 480, textAlign: "center" }}>
        <div style={{ marginBottom: 32 }}>
          <LogoWordmark size={32} />
        </div>
        <h1 className="h-1" style={{ marginBottom: 12 }}>
          {t("notfound.title", "Not found")}
        </h1>
        <p className="body" style={{ color: "var(--text-muted)", marginBottom: 28 }}>
          {t("notfound.body", "The page you were looking for doesn't exist or has moved.")}
        </p>
        <Link to={target}>
          <Btn variant="primary">{t("notfound.cta", "Back to dashboard")}</Btn>
        </Link>
      </div>
    </div>
  );
}
