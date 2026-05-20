import { useState, type CSSProperties } from "react";
import { Topbar } from "../components/Topbar";
import { Card, Badge, Btn } from "../components/primitives";
import { Icons } from "../components/icons";
import { useCreateOAuthClient, useDeleteOAuthClient, useOAuthClients } from "../lib/queries";
import { useUiStore } from "../lib/store";
import { useT } from "../lib/i18n";

const DEFAULT_REDIRECT_URIS = [
  "https://chatgpt.com/connector/oauth/jl0vrVeOwbY8",
  "https://claude.ai/api/mcp/auth_callback",
].join("\n");

function isValidUrl(value: string): boolean {
  try {
    const u = new URL(value.trim());
    return u.protocol === "https:" || u.protocol === "http:";
  } catch {
    return false;
  }
}

export function OAuthClientsPage() {
  const t = useT();
  const clients = useOAuthClients();
  const create = useCreateOAuthClient();
  const del = useDeleteOAuthClient();
  const setToast = useUiStore((s) => s.setToast);
  const [showCreate, setShowCreate] = useState(false);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);

  const onDelete = async (id: string, name: string) => {
    if (
      !confirm(
        t(
          "oauth.confirm_delete",
          'Delete OAuth client "{name}"?\nUsers signed in via this client will be cut off.',
        ).replace("{name}", name),
      )
    )
      return;
    setPendingDeleteId(id);
    try {
      await del.mutateAsync(id);
      setToast(t("oauth.toast_deleted", "Client deleted"));
    } catch (e: any) {
      setToast(
        t("oauth.toast_delete_failed", "Delete failed: {error}").replace("{error}", e.message),
      );
    } finally {
      setPendingDeleteId(null);
    }
  };

  return (
    <>
      <Topbar
        crumbs={[t("workspace", "Workspace"), t("oauth_clients", "OAuth clients")]}
        actions={
          <Btn variant="primary" size="sm" icon="plus" onClick={() => setShowCreate(true)}>
            {t("create", "New client")}
          </Btn>
        }
      />
      <div className="page-pad">
        <div
          className="page-head"
          style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}
        >
          <div>
            <h1 className="h-1" style={{ margin: 0 }}>
              {t("oauth.title", "OAuth 2.1 clients")}
            </h1>
            <div className="body" style={{ color: "var(--text-muted)", marginTop: 6, maxWidth: 640 }}>
              {t(
                "oauth.intro",
                "Register third-party apps that authorize users against your hub. Tool access is managed per service.",
              )}
            </div>
          </div>
        </div>

        {showCreate && (
          <CreateClientDialog
            t={t}
            onCancel={() => setShowCreate(false)}
            onCreate={async (name, redirects) => {
              try {
                await create.mutateAsync({ name, redirect_uris: redirects });
                setToast(t("oauth.toast_created", "Client created"));
                setShowCreate(false);
              } catch (e: any) {
                setToast(
                  t("oauth.toast_create_failed", "Create failed: {error}").replace(
                    "{error}",
                    e.message,
                  ),
                );
              }
            }}
          />
        )}

        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {clients.isLoading ? (
            <ClientSkeletons />
          ) : (clients.data ?? []).length === 0 ? (
            <Card>
              <div style={{ padding: 32, textAlign: "center" }}>
                <div className="caption" style={{ marginBottom: 12 }}>
                  {t("oauth.empty", "No OAuth clients yet.")}
                </div>
                <Btn variant="primary" icon="plus" onClick={() => setShowCreate(true)}>
                  {t("oauth.register_first", "Register first client")}
                </Btn>
              </div>
            </Card>
          ) : (
            (clients.data ?? []).map((c) => (
              <Card key={c.id}>
                <div style={{ padding: 20, display: "flex", gap: 18, alignItems: "flex-start" }}>
                  <div style={iconBoxStyle}>
                    <Icons.shield style={{ width: 22, height: 22, color: "var(--brand-400)" }} />
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
                      <div className="h-3" style={{ margin: 0 }}>
                        {c.name}
                      </div>
                      <Badge variant="success" dot>
                        {t("status.live", "live")}
                      </Badge>
                    </div>
                    <div className="mono caption" style={{ marginBottom: 12 }}>
                      {c.id}
                    </div>
                    <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 20 }}>
                      <div>
                        <div className="eyebrow" style={{ marginBottom: 6 }}>
                          {t("oauth.redirect_uris", "Redirect URIs")}
                        </div>
                        {c.redirect_uris.length === 0 ? (
                          <div className="caption">{t("oauth.none", "— none —")}</div>
                        ) : (
                          c.redirect_uris.map((r: string) => (
                            <div key={r} className="mono" style={{ fontSize: 11.5, wordBreak: "break-all" }}>
                              {r}
                            </div>
                          ))
                        )}
                      </div>
                    </div>
                  </div>
                  <Btn
                    variant="ghost"
                    size="sm"
                    icon={pendingDeleteId === c.id ? undefined : "trash"}
                    style={{ color: "var(--danger)" }}
                    disabled={pendingDeleteId === c.id}
                    onClick={() => onDelete(c.id, c.name)}
                  >
                    {pendingDeleteId === c.id ? <Spinner /> : t("delete", "Delete")}
                  </Btn>
                </div>
              </Card>
            ))
          )}
        </div>
      </div>
    </>
  );
}

function CreateClientDialog({
  t,
  onCancel,
  onCreate,
}: {
  t: ReturnType<typeof useT>;
  onCancel: () => void;
  onCreate: (name: string, redirects: string[]) => Promise<void> | void;
}) {
  const [name, setName] = useState("");
  const [redirectsRaw, setRedirectsRaw] = useState(DEFAULT_REDIRECT_URIS);

  const redirects = redirectsRaw
    .split(/\r?\n/)
    .map((s) => s.trim())
    .filter(Boolean);
  const invalid = redirects.filter((r) => !isValidUrl(r));
  const canSubmit = name.length > 0 && redirects.length > 0 && invalid.length === 0;

  return (
    <Card style={{ marginBottom: 16, padding: 20 }}>
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <div className="field">
          <label>{t("api_key_name", "Name")}</label>
          <input className="input" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
        </div>

        <div className="field">
          <label>{t("oauth.redirect_uris_one_per_line", "Redirect URIs (one per line)")}</label>
          <textarea
            className="input"
            rows={3}
            value={redirectsRaw}
            onChange={(e) => setRedirectsRaw(e.target.value)}
            placeholder="https://example.com/oauth/callback"
            style={{ fontFamily: "var(--font-mono)", fontSize: 12 }}
          />
          {invalid.length > 0 ? (
            <div className="caption" style={{ color: "var(--danger)", marginTop: 4 }}>
              {t("oauth.invalid_uris", "{n} URI(s) not valid http(s) URLs:")
                .replace("{n}", String(invalid.length))}{" "}
              {invalid.map((r) => `"${r}"`).join(", ")}
            </div>
          ) : redirects.length > 0 ? (
            <div className="caption" style={{ marginTop: 4 }}>
              {t("oauth.valid_uris", "{n} valid URI(s).").replace("{n}", String(redirects.length))}
            </div>
          ) : null}
        </div>

        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <Btn variant="ghost" onClick={onCancel}>
            {t("cancel", "Cancel")}
          </Btn>
          <Btn variant="primary" disabled={!canSubmit} onClick={() => onCreate(name, redirects)}>
            {t("create", "Create")}
          </Btn>
        </div>
      </div>
    </Card>
  );
}

function ClientSkeletons() {
  return (
    <>
      {[0, 1].map((i) => (
        <Card key={i} className="shimmer" style={{ height: 120 }} />
      ))}
    </>
  );
}

function Spinner() {
  return (
    <span
      aria-label="loading"
      style={{
        display: "inline-block",
        width: 14,
        height: 14,
        border: "2px solid var(--border)",
        borderTopColor: "var(--brand-400)",
        borderRadius: "50%",
        animation: "spin 0.8s linear infinite",
      }}
    />
  );
}

const iconBoxStyle: CSSProperties = {
  width: 48,
  height: 48,
  borderRadius: 10,
  background: "oklch(from var(--brand-500) l c h / 0.12)",
  border: "1px solid oklch(from var(--brand-500) l c h / 0.25)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  flexShrink: 0,
};
