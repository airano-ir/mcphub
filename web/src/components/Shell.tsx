import { useEffect } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { useSession } from "../lib/queries";
import { useUiStore } from "../lib/store";

export function Shell() {
  const { data: session } = useSession();
  const collapsed = useUiStore((s) => s.sidebarCollapsed);
  const mobileOpen = useUiStore((s) => s.sidebarMobileOpen);
  const setMobileOpen = useUiStore((s) => s.setSidebarMobileOpen);
  const location = useLocation();

  // Auto-close the mobile drawer whenever the route changes — tapping a nav
  // item should feel like "take me there + dismiss the drawer".
  useEffect(() => {
    if (mobileOpen) setMobileOpen(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname]);

  // Prevent body scroll while the drawer is open (mobile UX expectation).
  useEffect(() => {
    if (!mobileOpen) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [mobileOpen]);

  const classes = [
    "shell",
    collapsed ? "is-collapsed" : "",
    mobileOpen ? "is-mobile-open" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={classes}>
      <Sidebar session={session} />
      <button
        type="button"
        aria-label="Close menu"
        className="sidebar-backdrop"
        onClick={() => setMobileOpen(false)}
        tabIndex={mobileOpen ? 0 : -1}
      />
      <main>
        <Outlet />
      </main>
    </div>
  );
}
