import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { SiteFormDialog } from "../components/SiteFormDialog";
import type { Site } from "../lib/types";

vi.mock("../lib/queries", () => ({
  useCreateSite: () => ({ mutateAsync: vi.fn() }),
  usePluginCatalog: () => ({
    isLoading: false,
    data: [
      {
        type: "wordpress",
        name: "WordPress",
        fields: [
          { name: "username", label: "Username", type: "text", required: true },
          { name: "app_password", label: "Application Password", type: "password", required: true },
        ],
      },
      {
        type: "woocommerce",
        name: "WooCommerce",
        fields: [
          { name: "consumer_key", label: "Consumer Key", type: "text", required: true },
          { name: "consumer_secret", label: "Consumer Secret", type: "password", required: true },
        ],
      },
      {
        type: "coolify",
        name: "Coolify",
        fields: [],
      },
    ],
  }),
  useTranslations: () => ({ data: undefined }),
  useUpdateSite: () => ({ mutateAsync: vi.fn() }),
}));

const noop = vi.fn();

describe("SiteFormDialog AI image placement", () => {
  it("shows AI Image Generation guidance while adding a WordPress site", () => {
    render(<SiteFormDialog mode="create" onCancel={noop} onDone={noop} />);

    expect(screen.getByText("AI Image Generation")).toBeInTheDocument();
    expect(screen.getByText(/After creating this service/)).toBeInTheDocument();
  });

  it("shows the tools-page link while editing a WooCommerce site", () => {
    const site = {
      id: "site-1",
      alias: "shop",
      url: "https://shop.example.com",
      plugin_type: "woocommerce",
      status: "active",
    } as Site;

    render(<SiteFormDialog mode="edit" site={site} onCancel={noop} onDone={noop} />);

    const link = screen.getByRole("link", { name: "Open AI Image Generation settings" });
    expect(link).toHaveAttribute("href", "/dashboard/sites/site-1/tools");
  });
});
