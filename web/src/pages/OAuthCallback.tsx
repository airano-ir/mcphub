import { useEffect, type CSSProperties } from "react";
import { useSearchParams } from "react-router-dom";
import { Card, Btn } from "../components/primitives";
import { Icons } from "../components/icons";
import { useT } from "../lib/i18n";
import { useUiStore } from "../lib/store";

/**
 * OAuth Callback Page — shows success/failure after the OAuth redirect.
 *
 * The backend `/oauth/site/callback` handler exchanges the code, stores the
 * tokens, and redirects to `/dashboard/sites?msg=oauth_success` or
 * `/dashboard/sites?error=...`.  This page is a fallback that renders a
 * full-page status message if the user lands on `/oauth/callback` directly
 * (e.g. the SPA catches the redirect params before the server-side handler).
 *
 * It reads `msg` and `error` query params to determine which state to show.
 */
export function OAuthCallbackPage() {
  const t = useT();
  const [params] = useSearchParams();
  const setToast = useUiStore((s) => s.setToast);

  const msg = params.get("msg");
  const error = params.get("error");
  const detail = params.get("detail");

  const success = msg === "oauth_success";
  const failure = !!error;

  useEffect(() => {
    if (success) {
      setToast(t("sites.oauth.callback_success_title", "Authorization successful"));
    } else if (failure) {
      setToast(`${t("sites.oauth.callback_error_title", "Authorization failed")}: ${error}`);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [success, failure, error]);

  return (
    <div style={pageStyle}>
      <Card style={cardStyle}>
        <div style={contentStyle}>
          {success ? (
            <>
              <div style={iconWrapStyle}>
                <Icons.shield style={{ width: 32, height: 32, color: "var(--success, #22c55e)" }} />
              </div>
              <h2 className="h-2" style={{ margin: 0 }}>
                {t("sites.oauth.callback_success_title", "Authorization successful")}
              </h2>
              <p className="body" style={{ color: "var(--text-muted)", textAlign: "center" }}>
                {t(
                  "sites.oauth.callback_success_body",
                  "Your Google account is now connected. You can close this page.",
                )}
              </p>
            </>
          ) : failure ? (
            <>
              <div style={iconWrapStyle}>
                <Icons.warning style={{ width: 32, height: 32, color: "var(--danger)" }} />
              </div>
              <h2 className="h-2" style={{ margin: 0 }}>
                {t("sites.oauth.callback_error_title", "Authorization failed")}
              </h2>
              <p className="body" style={{ color: "var(--text-muted)", textAlign: "center" }}>
                {t(
                  "sites.oauth.callback_error_body",
                  "The OAuth authorization did not complete successfully.",
                )}
                {detail ? `\n\n${detail}` : ""}
              </p>
            </>
          ) : (
            <>
              <div style={iconWrapStyle}>
                <Icons.info style={{ width: 32, height: 32, color: "var(--brand-400)" }} />
              </div>
              <h2 className="h-2" style={{ margin: 0 }}>
                {t("sites.oauth.callback_success_title", "Authorization successful")}
              </h2>
              <p className="body" style={{ color: "var(--text-muted)", textAlign: "center" }}>
                {t(
                  "sites.oauth.callback_success_body",
                  "Your Google account is now connected. You can close this page.",
                )}
              </p>
            </>
          )}
          <div style={{ marginTop: 20 }}>
            <Btn variant="primary" onClick={() => (window.location.href = "/dashboard/sites")}>
              {t("my_sites", "Sites")}
            </Btn>
          </div>
        </div>
      </Card>
    </div>
  );
}

const pageStyle: CSSProperties = {
  minHeight: "100vh",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  padding: 20,
};

const cardStyle: CSSProperties = {
  width: "min(480px, 100%)",
};

const contentStyle: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  gap: 14,
  padding: "32px 24px",
  textAlign: "center",
};

const iconWrapStyle: CSSProperties = {
  width: 64,
  height: 64,
  borderRadius: "50%",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  background: "var(--surface)",
  border: "1px solid var(--border)",
};