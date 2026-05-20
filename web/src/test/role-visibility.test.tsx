import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Sidebar } from "../components/Sidebar";
import { SettingsPage } from "../pages/Settings";
import type { Session } from "../lib/types";

const state = vi.hoisted(() => ({
  session: {
    authenticated: true,
    user_id: "admin",
    email: "admin@example.com",
    name: "Admin",
    role: "admin",
    type: "master",
    is_admin: true,
    lang: "en",
  } as Session,
}));

vi.mock("../lib/queries", () => ({
  useAdminApiKeys: () => ({ data: [] }),
  useManagedSettings: () => ({ data: [], isLoading: false }),
  useOAuthClients: () => ({ data: [] }),
  useResetSettings: () => ({ mutate: vi.fn(), isPending: false }),
  useSaveSetting: () => ({ mutate: vi.fn(), isPending: false }),
  useSession: () => ({ data: state.session }),
  useSites: () => ({ data: [] }),
  useTranslations: () => ({ data: undefined }),
  useUserKeys: () => ({ data: [] }),
}));

function userSession(): Session {
  return {
    authenticated: true,
    user_id: "user",
    email: "user@example.com",
    name: "User",
    role: "user",
    type: "oauth_user",
    is_admin: false,
    lang: "en",
  };
}

function renderSidebar(session: Session) {
  render(
    <MemoryRouter>
      <Sidebar session={session} />
    </MemoryRouter>,
  );
}

describe("role-based dashboard visibility", () => {
  it("shows admin-only navigation for admins", () => {
    renderSidebar(state.session);

    expect(screen.queryByText("OAuth Clients")).not.toBeInTheDocument();
    expect(screen.getByText("Health")).toBeInTheDocument();
    expect(screen.getByText("Audit Logs")).toBeInTheDocument();
    expect(screen.getByText("Support MCP Hub")).toBeInTheDocument();
  });

  it("hides admin-only navigation for normal users", () => {
    renderSidebar(userSession());

    expect(screen.queryByText("OAuth Clients")).not.toBeInTheDocument();
    expect(screen.queryByText("Health")).not.toBeInTheDocument();
    expect(screen.queryByText("Audit Logs")).not.toBeInTheDocument();
    expect(screen.getByText("Support MCP Hub")).toBeInTheDocument();
  });

  it("shows settings limits, plugin visibility, and danger tabs only for admins", () => {
    state.session = { ...state.session, is_admin: true, role: "admin" };
    const admin = render(<SettingsPage />);

    expect(screen.getByText("Limits")).toBeInTheDocument();
    expect(screen.getByText("Public plugin visibility")).toBeInTheDocument();
    expect(screen.getByText("Danger zone")).toBeInTheDocument();

    admin.unmount();
    state.session = userSession();
    render(<SettingsPage />);

    expect(screen.queryByText("Limits")).not.toBeInTheDocument();
    expect(screen.queryByText("Public plugin visibility")).not.toBeInTheDocument();
    expect(screen.queryByText("Danger zone")).not.toBeInTheDocument();
  });
});
