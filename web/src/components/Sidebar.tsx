import { NavLink } from "react-router-dom";
import { Icons, type IconName } from "./icons";
import { LogoWordmark } from "./Logo";
import { Avatar } from "./primitives";
import type { Session } from "../lib/types";
import { useSites, useUserKeys, useAdminApiKeys } from "../lib/queries";
import { useT } from "../lib/i18n";
import { useUiStore } from "../lib/store";
import { fmtInt } from "../lib/format";

type NavItem = { id: string; label: string; icon: IconName; to: string; count?: number; adminOnly?: boolean };

const SUPPORT_URL = "https://nowpayments.io/donation/airano";

export function Sidebar({ session }: { session: Session | undefined }) {
  const t = useT();
  const collapsed = useUiStore((s) => s.sidebarCollapsed);
  const lang = useUiStore((s) => s.lang);
  const isAdmin = session?.is_admin ?? false;
  const isAdminKeySession = isAdmin && session?.type !== "oauth_user";

  const sites = useSites();
  const userKeys = useUserKeys();
  const adminKeys = useAdminApiKeys();

  // NavLink `to` props are relative to the BrowserRouter basename
  // (`/dashboard`) — do NOT prefix them or you'll get
  // `/dashboard/dashboard/...`.
  const groups: { label: string; items: NavItem[] }[] = [
    {
      label: t("nav.manage", "Manage"),
      items: [
        { id: "overview", label: t("nav.overview", "Overview"), icon: "home", to: "/overview" },
        {
          id: "sites",
          label: t("nav.sites", "Sites"),
          icon: "sites",
          to: "/sites",
          count: sites.data?.length,
        },
        { id: "connect", label: t("nav.connect", "Connect"), icon: "plug", to: "/connect" },
      ],
    },
    {
      label: t("nav.access", "Access"),
      items: [
        {
          id: "apikeys",
          label: t("nav.api_keys", "API Keys"),
          icon: "key",
          to: "/api-keys",
          count: isAdminKeySession ? adminKeys.data?.length : userKeys.data?.length,
        },
      ],
    },
    ...(isAdmin
      ? [
          {
            label: t("nav.observability", "Observability"),
            items: [
              {
                id: "health",
                label: t("nav.health", "Health"),
                icon: "activity" as IconName,
                to: "/health",
                adminOnly: true,
              },
              {
                id: "audit",
                label: t("nav.audit", "Audit Logs"),
                icon: "logs" as IconName,
                to: "/audit-logs",
                adminOnly: true,
              },
            ],
          },
        ]
      : []),
    {
      label: t("nav.account", "Account"),
      items: [
        { id: "settings", label: t("nav.settings", "Settings"), icon: "settings", to: "/settings" },
      ],
    },
  ];

  return (
    <aside data-collapsed={collapsed ? "true" : "false"}>
      <NavLink
        to="/landing"
        className="logo-link"
        style={{ padding: "4px 8px 16px", display: "flex", justifyContent: collapsed ? "center" : "flex-start" }}
        title="MCP Hub"
      >
        <LogoWordmark size={28} iconOnly={collapsed} />
      </NavLink>

      {!collapsed && (
        <div className="jumpto" aria-hidden="false">
          <Icons.search style={{ width: 14, height: 14 }} />
          <span style={{ flex: 1 }}>{t("nav.jump_to", "Jump to…")}</span>
          <span className="kbd">⌘K</span>
        </div>
      )}

      {groups.map((g) => (
        <div key={g.label} className="nav-group">
          {!collapsed && (
            <div className="eyebrow nav-group-label">{g.label}</div>
          )}
          {g.items.map((it) => {
            const Ic = Icons[it.icon];
            return (
              <NavLink
                key={it.id}
                to={it.to}
                className={({ isActive }) => `nav-item ${isActive ? "is-active" : ""}`}
                title={collapsed ? it.label : undefined}
                aria-label={it.label}
              >
                <Ic />
                {!collapsed && <span className="nav-item-label">{it.label}</span>}
                {!collapsed && it.count != null ? <span className="count">{fmtInt(it.count, lang)}</span> : null}
              </NavLink>
            );
          })}
        </div>
      ))}

      <div className="sidebar-footer">
        <a
          href={SUPPORT_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="nav-item sidebar-support-link"
          title={collapsed ? t("support_mcphub", "Support MCP Hub") : undefined}
          aria-label={t("support_mcphub", "Support MCP Hub")}
        >
          <Icons.link />
          {!collapsed && <span className="nav-item-label">{t("support_mcphub", "Support MCP Hub")}</span>}
        </a>
        <div className="sidebar-user">
          <Avatar name={session?.name || session?.email || "User"} size={30} />
          {!collapsed && (
            <div className="sidebar-user-meta">
              <div className="sidebar-user-name">{session?.name || "User"}</div>
              <div className="caption sidebar-user-email">{session?.email || ""}</div>
            </div>
          )}
          {!collapsed && (
            <a
              href="/dashboard/logout"
              className="btn btn-ghost btn-sm"
              style={{ padding: 6 }}
              title={t("nav.logout", "Log out")}
              aria-label={t("nav.logout", "Log out")}
            >
              <Icons.logout style={{ width: 14, height: 14 }} />
            </a>
          )}
        </div>
      </div>
    </aside>
  );
}
