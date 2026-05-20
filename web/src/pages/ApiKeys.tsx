import { useState, type CSSProperties } from "react";
import { Link } from "react-router-dom";
import { Topbar } from "../components/Topbar";
import { Card, Badge, Btn, CopyField } from "../components/primitives";
import { Icons } from "../components/icons";
import {
  useAdminApiKeys,
  useCreateAdminApiKey,
  useCreateUserKey,
  useDeleteAdminApiKey,
  useDeleteUserKey,
  useRevokeAdminApiKey,
  useSession,
  useSites,
  useUserKeys,
} from "../lib/queries";
import { useUiStore } from "../lib/store";
import { useT } from "../lib/i18n";
import { fmtDateTime } from "../lib/format";

// ---------- Scope tiers (mirrors core/tool_access.SCOPE_TO_CATEGORIES + "custom") ----------
// Six tiers per F.19.2.2; "admin" is treated as destructive per F.19.2.3.
type ScopeTier = "read" | "read:sensitive" | "deploy" | "write" | "admin" | "custom";

type TierInfo = { value: ScopeTier; label: string; hint: string; danger?: boolean; warning?: boolean };

const SCOPE_TIERS: TierInfo[] = [
  { value: "read", label: "Read", hint: "Read-only listing and inspection across resources." },
  {
    value: "read:sensitive",
    label: "Read sensitive",
    hint: "Includes backups, env vars, and other privacy-bearing reads.",
    warning: true,
  },
  { value: "deploy", label: "Deploy", hint: "Trigger deployments and lifecycle actions, no edits." },
  { value: "write", label: "Write", hint: "Create / update / delete resources and configuration." },
  {
    value: "admin",
    label: "Admin",
    hint: "Full control including system-level operations. Treat the key as a credential.",
    danger: true,
  },
  { value: "custom", label: "Custom", hint: "Pick scopes/categories manually after creation." },
];

function scopeBadgeVariant(scope: string | undefined): "default" | "warning" | "danger" {
  if (scope === "admin") return "danger";
  if (scope === "read:sensitive" || scope === "install") return "warning";
  return "default";
}

export function ApiKeysPage() {
  const session = useSession();
  const isAdminKeySession = (session.data?.is_admin ?? false) && session.data?.type !== "oauth_user";
  const isAdmin = isAdminKeySession;
  return isAdmin ? <AdminApiKeys /> : <UserApiKeys />;
}

// ---------- Admin variant ----------

function AdminApiKeys() {
  const t = useT();
  const keys = useAdminApiKeys();
  const create = useCreateAdminApiKey();
  const revoke = useRevokeAdminApiKey();
  const del = useDeleteAdminApiKey();
  const setToast = useUiStore((s) => s.setToast);
  const lang = useUiStore((s) => s.lang);
  const [showCreate, setShowCreate] = useState(false);
  const [createdKey, setCreatedKey] = useState<string | null>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);

  const onCreate = async (description: string, scope: string) => {
    try {
      const r = await create.mutateAsync({ description, scope });
      setCreatedKey(r.key);
    } catch (e: any) {
      setToast(`Create failed: ${e.message}`);
    }
  };

  return (
    <>
      <Topbar
        crumbs={[t("workspace", "Workspace"), t("api_keys", "API keys")]}
        actions={
          <Btn variant="primary" size="sm" icon="plus" onClick={() => setShowCreate(true)}>
            {t("generate_key", "New key")}
          </Btn>
        }
      />
      <div className="page-pad">
        <div className="page-head">
          <h1 className="h-1" style={{ margin: 0 }}>
            {t("api_keys", "API keys")}
          </h1>
          <div className="body" style={{ color: "var(--text-muted)", marginTop: 6, maxWidth: 640 }}>
            {t(
              "api_keys.admin_intro",
              "Personal and machine keys for MCP clients. Each key is scoped and logged independently.",
            )}
          </div>
        </div>

        {createdKey && <CreatedKeyAlert value={createdKey} t={t} onDismiss={() => setCreatedKey(null)} />}

        {showCreate && (
          <CreateKeyDialog
            t={t}
            onCancel={() => setShowCreate(false)}
            onCreate={async (d, s) => {
              await onCreate(d, s);
              setShowCreate(false);
            }}
          />
        )}

        <Card>
          <table className="table mobile-stack">
            <thead>
              <tr>
                <th>{t("table.description", "Description")}</th>
                <th>{t("table.prefix", "Prefix")}</th>
                <th>{t("table.scope", "Scope")}</th>
                <th>{t("table.created", "Created")}</th>
                <th>{t("table.last_used", "Last used")}</th>
                <th>{t("status", "Status")}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {keys.isLoading ? (
                <SkeletonRows cols={7} />
              ) : (keys.data ?? []).length === 0 ? (
                <tr>
                  <td colSpan={7} className="caption">
                    {t("no_api_keys", "No keys yet")}.{" "}
                    {t("api_keys.admin_empty_cta", "Create one to authenticate MCP clients.")}
                  </td>
                </tr>
              ) : (
                (keys.data ?? []).map((k) => (
                  <tr key={k.id}>
                    <td className="row-head" data-label={t("table.description", "Description")} style={{ fontWeight: 500 }}>
                      {k.description || k.id}
                    </td>
                    <td className="mono caption" data-label={t("table.prefix", "Prefix")}>
                      {k.prefix ? `${k.prefix}…` : "—"}
                    </td>
                    <td data-label={t("table.scope", "Scope")}>
                      <Badge variant={scopeBadgeVariant(k.scope)} className="badge-fixed" title={k.scope}>
                        {k.scope || "default"}
                      </Badge>
                    </td>
                    <td className="caption" data-label={t("table.created", "Created")}>
                      {fmtDateTime(k.created_at, lang)}
                    </td>
                    <td className="caption" data-label={t("table.last_used", "Last used")}>
                      {fmtDateTime(k.last_used, lang)}
                    </td>
                    <td data-label={t("status", "Status")}>
                      {k.status === "active" ? (
                        <Badge variant="success" dot>
                          {t("active", "active")}
                        </Badge>
                      ) : k.status === "revoked" ? (
                        <Badge variant="danger">{t("status.revoked", "revoked")}</Badge>
                      ) : (
                        <Badge>{k.status ?? "—"}</Badge>
                      )}
                    </td>
                    <td className="cell-actions" style={{ textAlign: "right" }}>
                      <div style={{ display: "inline-flex", gap: 4 }}>
                        <Btn
                          variant="ghost"
                          size="sm"
                          disabled={pendingId === k.id || k.status === "revoked"}
                          onClick={async () => {
                            if (
                              !confirm(
                                t(
                                  "api_keys.confirm_revoke",
                                  'Revoke "{name}"?\nThe key will stop working immediately.',
                                ).replace("{name}", k.description || k.id),
                              )
                            )
                              return;
                            setPendingId(k.id);
                            try {
                              await revoke.mutateAsync(k.id);
                              setToast(t("api_keys.toast_revoked", "Key revoked"));
                            } finally {
                              setPendingId(null);
                            }
                          }}
                        >
                          {pendingId === k.id ? <Spinner /> : t("action.revoke", "Revoke")}
                        </Btn>
                        <Btn
                          variant="ghost"
                          size="sm"
                          disabled={pendingId === k.id}
                          onClick={async () => {
                            if (
                              !confirm(
                                t(
                                  "api_keys.confirm_delete",
                                  'Delete "{name}" permanently?\nThis cannot be undone.',
                                ).replace("{name}", k.description || k.id),
                              )
                            )
                              return;
                            setPendingId(k.id);
                            try {
                              await del.mutateAsync(k.id);
                              setToast(t("api_keys.toast_deleted", "Key deleted"));
                            } finally {
                              setPendingId(null);
                            }
                          }}
                          style={{ color: "var(--danger)", padding: 6 }}
                          icon={pendingId === k.id ? undefined : "trash"}
                        >
                          {pendingId === k.id ? <Spinner /> : null}
                        </Btn>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </Card>
      </div>
    </>
  );
}

// ---------- User variant ----------

function UserApiKeys() {
  const t = useT();
  const keys = useUserKeys();
  const sites = useSites();
  const create = useCreateUserKey();
  const del = useDeleteUserKey();
  const setToast = useUiStore((s) => s.setToast);
  const lang = useUiStore((s) => s.lang);
  const [showCreate, setShowCreate] = useState(false);
  const [createdKey, setCreatedKey] = useState<string | null>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);

  const siteById = new Map((sites.data ?? []).map((site) => [site.id, site]));
  const hasServices = (sites.data ?? []).length > 0;

  const onCreate = async (name: string, siteId: string, expiryDays: number | undefined) => {
    try {
      const body: { name: string; site_id?: string; expires_in_days?: number } = { name };
      if (siteId) body.site_id = siteId;
      if (expiryDays && expiryDays > 0) body.expires_in_days = expiryDays;
      const r = await create.mutateAsync(body);
      setCreatedKey(r.key);
    } catch (e: any) {
      setToast(`Create failed: ${e.message}`);
    }
  };

  return (
    <>
      <Topbar
        crumbs={[t("nav.account", "Account"), t("api_keys", "API keys")]}
        actions={
          <Btn
            variant="primary"
            size="sm"
            icon="plus"
            disabled={!hasServices && !sites.isLoading}
            title={!hasServices && !sites.isLoading ? t("api_keys.no_services_title", "Add a service first") : undefined}
            onClick={() => setShowCreate(true)}
          >
            {t("generate_key", "New key")}
          </Btn>
        }
      />
      <div className="page-pad">
        <div className="page-head">
          <h1 className="h-1" style={{ margin: 0 }}>
            {t("user_api_keys", "Your API keys")}
          </h1>
          <div className="body" style={{ color: "var(--text-muted)", marginTop: 6 }}>
            {t(
              "api_keys.user_intro",
              "Use these to authenticate MCP clients to your hub.",
            )}
          </div>
        </div>

        {createdKey && <CreatedKeyAlert value={createdKey} t={t} onDismiss={() => setCreatedKey(null)} />}

        {!sites.isLoading && !hasServices ? (
          <Card style={{ marginBottom: 16 }}>
            <div style={{ padding: 20, display: "flex", gap: 12, alignItems: "flex-start" }}>
              <Icons.sites style={{ width: 18, height: 18, color: "var(--brand-400)", flexShrink: 0 }} />
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, marginBottom: 4 }}>
                  {t("api_keys.no_services_title", "Add a service before creating API keys")}
                </div>
                <div className="caption" style={{ marginBottom: 12 }}>
                  {t(
                    "api_keys.no_services_body",
                    "API keys authenticate clients to your services. Add your first service from Sites, then create a key for that service or all services.",
                  )}
                </div>
                <Link to="/sites?create=1" className="btn btn-primary btn-sm">
                  <Icons.plus style={{ width: 12, height: 12 }} />
                  {t("add_site_short", "Add site")}
                </Link>
              </div>
            </div>
          </Card>
        ) : null}

        {showCreate && (
          <CreateKeyDialog
            t={t}
            simple
            sites={sites.data ?? []}
            sitesLoading={sites.isLoading}
            onCancel={() => setShowCreate(false)}
            onCreate={async (name, siteId, expiry) => {
              await onCreate(name, siteId, expiry);
              setShowCreate(false);
            }}
          />
        )}

        <Card>
          <table className="table mobile-stack">
            <thead>
              <tr>
                <th>{t("api_key_name", "Name")}</th>
                <th>{t("table.prefix", "Prefix")}</th>
                <th>{t("table.service", "Service")}</th>
                <th>{t("table.created", "Created")}</th>
                <th>{t("table.expiry", "Expires")}</th>
                <th>{t("table.last_used", "Last used")}</th>
                <th>{t("status", "Status")}</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {keys.isLoading ? (
                <SkeletonRows cols={7} />
              ) : (keys.data ?? []).length === 0 ? (
                <tr>
                  <td colSpan={7} className="caption">
                    {t("no_api_keys", "No keys yet")}.{" "}
                    {t("api_keys.user_empty_cta", "Create one to connect a client.")}
                  </td>
                </tr>
              ) : (
                (keys.data ?? []).map((k) => (
                  <tr key={k.id}>
                    <td className="row-head" data-label={t("api_key_name", "Name")} style={{ fontWeight: 500 }}>
                      {k.name}
                    </td>
                    <td className="mono caption" data-label={t("table.prefix", "Prefix")}>
                      {k.prefix ? `${k.prefix}…` : "—"}
                    </td>
                    <td data-label={t("table.service", "Service")}>
                      <Badge className="badge-fixed" title={k.site_id ?? undefined}>
                        {k.site_id ? (siteById.get(k.site_id)?.alias ?? t("site_not_found", "Site not found")) : t("all_sites", "All sites")}
                      </Badge>
                    </td>
                    <td className="caption" data-label={t("table.created", "Created")}>
                      {fmtDateTime(k.created_at, lang)}
                    </td>
                    <td className="caption" data-label={t("table.expiry", "Expires")}>
                      {k.expires_at ? fmtDateTime(k.expires_at, lang) : t("never", "Never")}
                    </td>
                    <td className="caption" data-label={t("table.last_used", "Last used")}>
                      {fmtDateTime(k.last_used, lang)}
                    </td>
                    <td data-label={t("status", "Status")}>
                      {k.status === "active" ? (
                        <Badge variant="success" dot>
                          {t("active", "active")}
                        </Badge>
                      ) : k.status === "expired" ? (
                        <Badge variant="warning">{t("status.expired", "expired")}</Badge>
                      ) : (
                        <Badge>{k.status ?? "—"}</Badge>
                      )}
                    </td>
                    <td className="cell-actions" style={{ textAlign: "right" }}>
                      <Btn
                        variant="ghost"
                        size="sm"
                        disabled={pendingId === k.id}
                        onClick={async () => {
                          if (
                            !confirm(
                              t(
                                "api_keys.confirm_delete_user",
                                'Delete "{name}"?\nThe key will stop working immediately.',
                              ).replace("{name}", k.name),
                            )
                          )
                            return;
                          setPendingId(k.id);
                          try {
                            await del.mutateAsync(k.id);
                            setToast(t("api_keys.toast_deleted", "Key deleted"));
                          } finally {
                            setPendingId(null);
                          }
                        }}
                        icon={pendingId === k.id ? undefined : "trash"}
                        style={{ color: "var(--danger)", padding: 6 }}
                      >
                        {pendingId === k.id ? <Spinner /> : null}
                      </Btn>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </Card>
      </div>
    </>
  );
}

// ---------- Shared bits ----------

function CreatedKeyAlert({
  value,
  t,
  onDismiss,
}: {
  value: string;
  t: ReturnType<typeof useT>;
  onDismiss: () => void;
}) {
  return (
    <div className="alert alert-warning" style={{ marginBottom: 16 }}>
      <Icons.warning style={{ width: 16, height: 16, flexShrink: 0 }} />
      <div style={{ flex: 1 }}>
        <div style={{ fontWeight: 500, color: "var(--text)", marginBottom: 8 }}>
          {t("key_shown_once", "Save this key — it's shown only once.")}
        </div>
        <CopyField value={value} />
      </div>
      <Btn variant="ghost" size="sm" onClick={onDismiss}>
        Dismiss
      </Btn>
    </div>
  );
}

function CreateKeyDialog({
  t,
  simple = false,
  sites = [],
  sitesLoading = false,
  onCancel,
  onCreate,
}: {
  t: ReturnType<typeof useT>;
  simple?: boolean;
  sites?: { id: string; alias: string; plugin_type: string }[];
  sitesLoading?: boolean;
  onCancel: () => void;
  onCreate: (description: string, scope: string, expiryDays?: number) => Promise<void> | void;
}) {
  const [name, setName] = useState("");
  // F.19.2.2: default checks the broadest tier so everything works out of
  // the box; users explicitly downgrade to a tighter scope.
  const [scope, setScope] = useState<ScopeTier>("admin");
  const [siteId, setSiteId] = useState("");
  const [expiryDays, setExpiryDays] = useState<string>("");

  const selectedTier = SCOPE_TIERS.find((s) => s.value === scope);
  const canCreate = !!name;

  return (
    <Card style={{ marginBottom: 16, padding: 20 }}>
      <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
        <div className="field">
          <label>
            {simple ? t("api_key_name", "Name") : t("api_keys.description", "Description")}
          </label>
          <input
            className="input"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={
              simple
                ? "claude-desktop"
                : t("api_keys.description_placeholder", "What's this key for?")
            }
            autoFocus
          />
        </div>

        {!simple ? (
          <div className="field">
          <label>{t("scope", "Scope")}</label>
          <div style={tierGridStyle}>
            {SCOPE_TIERS.map((tier) => {
              const active = tier.value === scope;
              return (
                <button
                  type="button"
                  key={tier.value}
                  onClick={() => setScope(tier.value)}
                  style={tierTileStyle(active, tier)}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span style={{ fontWeight: 500 }}>
                      {t(`tier.${tier.value.replace(":", "_")}`, tier.label)}
                    </span>
                    {tier.danger ? (
                      <Badge variant="danger" className="badge-fixed">
                        {t("badge.admin", "admin")}
                      </Badge>
                    ) : tier.warning ? (
                      <Badge variant="warning" className="badge-fixed">
                        {t("badge.sensitive", "sensitive")}
                      </Badge>
                    ) : null}
                  </div>
                  <div className="caption" style={{ marginTop: 4 }}>
                    {t(`tier.${tier.value.replace(":", "_")}.hint`, tier.hint)}
                  </div>
                </button>
              );
            })}
          </div>
          {selectedTier?.danger ? (
            <div className="alert alert-danger" style={{ marginTop: 10 }}>
              <Icons.warning style={{ width: 16, height: 16, flexShrink: 0 }} />
              <div style={{ flex: 1, fontSize: 13 }}>
                {t(
                  "api_keys.admin_warning",
                  "Admin scope grants full system control including destructive operations (deletes, env writes, system tools). Anyone holding this key can act as you across every site. Prefer a narrower tier unless the client genuinely needs it.",
                )}
              </div>
            </div>
          ) : selectedTier?.warning ? (
            <div className="alert alert-warning" style={{ marginTop: 10 }}>
              <Icons.warning style={{ width: 16, height: 16, flexShrink: 0 }} />
              <div style={{ flex: 1, fontSize: 13 }}>
                {t(
                  "api_keys.sensitive_warning",
                  "Reads backup files and env vars, which often contain secrets. Treat the key as a credential and avoid sharing it in unencrypted channels.",
                )}
              </div>
            </div>
          ) : null}
          </div>
        ) : (
          <div className="field">
            <label>{t("table.service", "Service")}</label>
            <select
              className="input"
              value={siteId}
              onChange={(e) => setSiteId(e.target.value)}
              disabled={sitesLoading}
            >
              <option value="">
                {sitesLoading
                  ? t("loading", "Loading…")
                  : t("all_sites", "All sites")}
              </option>
              {sites.map((site) => (
                <option key={site.id} value={site.id}>
                  {site.alias} · {site.plugin_type}
                </option>
              ))}
            </select>
            <div className="caption">
              {t(
                "api_keys.service_hint",
                "The key is limited to the selected service. Tool tiers are managed on that service's Tool Access page.",
              )}
            </div>
          </div>
        )}

        {simple && (
          <div className="field">
            <label>{t("api_keys.expiry_label", "Expires in (days, optional)")}</label>
            <input
              className="input"
              type="number"
              min={1}
              max={365}
              value={expiryDays}
              onChange={(e) => setExpiryDays(e.target.value)}
              placeholder={t("api_keys.expiry_placeholder", "Leave blank for no expiry")}
            />
          </div>
        )}

        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <Btn variant="ghost" onClick={onCancel}>
            {t("cancel", "Cancel")}
          </Btn>
          <Btn
            variant="primary"
            disabled={!canCreate}
            onClick={() =>
              canCreate && onCreate(name, simple ? siteId : scope, expiryDays ? Number(expiryDays) : undefined)
            }
          >
            {t("create", "Create")}
          </Btn>
        </div>
      </div>
    </Card>
  );
}

function SkeletonRows({ cols }: { cols: number }) {
  return (
    <>
      {[0, 1, 2].map((i) => (
        <tr key={i}>
          {Array.from({ length: cols }).map((_, j) => (
            <td key={j}>
              <div className="shimmer" style={{ height: 16, borderRadius: 4 }} />
            </td>
          ))}
        </tr>
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

const tierGridStyle: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))",
  gap: 8,
};

function tierTileStyle(active: boolean, tier: TierInfo): CSSProperties {
  const accent = tier.danger
    ? "var(--danger)"
    : tier.warning
      ? "var(--warning, #d97706)"
      : "var(--brand-400)";
  return {
    textAlign: "left",
    padding: "10px 12px",
    background: active ? "var(--surface)" : "var(--bg-sunken)",
    border: `1px solid ${active ? accent : "var(--border)"}`,
    borderRadius: 8,
    cursor: "pointer",
    color: "var(--text)",
    fontSize: 13,
    transition: "background 120ms, border-color 120ms",
  };
}
