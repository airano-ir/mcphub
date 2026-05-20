import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { SiteToolsPage } from "../pages/SiteTools";

const state = vi.hoisted(() => ({
  pluginType: "woocommerce",
  providers: [] as string[],
}));

vi.mock("../lib/queries", () => ({
  useDeleteSiteProviderKey: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useOpenRouterImageModels: () => ({
    data: [
      {
        id: "google/gemini-2.5-flash-image",
        name: "Gemini 2.5 Flash Image",
        price_per_image_usd: 0.039,
      },
    ],
    isLoading: false,
    isError: false,
  }),
  useSetSiteProviderDefaultModel: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useSetSiteProviderKey: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useSiteCapabilities: () => ({
    isLoading: false,
    data: {
      ok: true,
      plugin_type: state.pluginType,
      probe_available: true,
      granted: ["read_write"],
      ai_providers_configured: state.providers,
      tier: "admin",
      fit: { status: "ok", required: ["write_products"], missing: [] },
    },
  }),
  useSite: () => ({
    data: {
      id: "site-1",
      alias: "shop",
      plugin_type: state.pluginType,
      tool_scope: "admin",
    },
  }),
  useSiteProviderKeys: () => ({
    data: { ok: true, providers: state.providers, default_models: { openrouter: "google/gemini-2.5-flash-image" } },
  }),
  useSiteTools: () => ({
    isLoading: false,
    data: {
      site_id: "site-1",
      plugin_type: state.pluginType,
      tool_scope: "admin",
      scope_presets: [],
      configured_providers: state.providers,
      tools: [
        {
          name: "woocommerce_generate_and_upload_image",
          description: "Generate an image and upload it to WooCommerce media.",
          plugin_type: "woocommerce",
          category: "media",
          sensitivity: null,
          required_scope: "write",
          enabled: true,
          provider_key_required: true,
          provider_key_configured: state.providers.length > 0,
          available: state.providers.length > 0,
          unavailable_reason: state.providers.length > 0 ? null : "provider_key",
        },
      ],
    },
  }),
  useToggleSiteTool: () => ({ mutateAsync: vi.fn() }),
  useTranslations: () => ({ data: undefined }),
  useUpdateSiteToolScope: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

function renderPage() {
  render(
    <MemoryRouter initialEntries={["/sites/site-1/tools"]}>
      <Routes>
        <Route path="/sites/:id/tools" element={<SiteToolsPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("SiteTools AI image provider UI", () => {
  it("shows provider-key management for WooCommerce image tools", () => {
    state.pluginType = "woocommerce";
    state.providers = [];

    renderPage();

    expect(screen.getByText("AI Image Generation")).toBeInTheDocument();
    expect(screen.getByText("OpenAI")).toBeInTheDocument();
    expect(screen.getByText("OpenRouter")).toBeInTheDocument();
    expect(screen.getByText("Needs an AI provider key — configure one above.")).toBeInTheDocument();
    expect(screen.getByText("needs AI provider key")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Configure key" })).toBeInTheDocument();
    expect(screen.getByText("woocommerce_generate_and_upload_image")).toBeInTheDocument();
  });

  it("shows service readiness guidance for the current tool scope", () => {
    state.pluginType = "woocommerce";
    state.providers = [];

    renderPage();

    expect(screen.getByText("Service readiness")).toBeInTheDocument();
    expect(screen.getByText("Credential requirement for Admin")).toBeInTheDocument();
    expect(screen.getByText("credential fits selected tier")).toBeInTheDocument();
    expect(screen.getByText(/Configured AI providers/)).toBeInTheDocument();
    expect(screen.getByText(/Media and AI image upload tools additionally need/)).toBeInTheDocument();
    expect(screen.getByText(/Admin grants the full destructive surface/)).toBeInTheDocument();
  });

  it("shows OpenRouter default image model selection when the key is set", () => {
    state.pluginType = "woocommerce";
    state.providers = ["openrouter"];

    renderPage();

    expect(screen.getByText("Default image model")).toBeInTheDocument();
    expect(screen.getByText("Gemini 2.5 Flash Image")).toBeInTheDocument();
    expect(screen.getByText(/Current default:/)).toBeInTheDocument();
  });

  it("hides provider-key management for non-WordPress services", () => {
    state.pluginType = "coolify";
    state.providers = [];

    renderPage();

    expect(screen.queryByText("AI Image Generation")).not.toBeInTheDocument();
  });
});
