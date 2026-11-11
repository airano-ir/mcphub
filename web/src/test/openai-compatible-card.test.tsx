import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { OpenAICompatibleCard } from "../components/OpenAICompatibleCard";

const add = vi.fn();

vi.mock("../lib/queries", () => ({
  useAddOpenAICompatibleConfig: () => ({ mutateAsync: add, isPending: false }),
  useDeleteOpenAICompatibleConfig: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useOpenAICompatibleConfigs: () => ({ data: [], isLoading: false, isError: false }),
  useOpenAICompatibleModels: () => ({ data: [], isLoading: false, isError: false, refetch: vi.fn() }),
  useSetOpenAICompatibleModel: () => ({ mutateAsync: vi.fn(), isPending: false }),
}));

vi.mock("../lib/i18n", () => ({
  useT: () => (_key: string, fallback: string) => fallback,
}));

describe("OpenAICompatibleCard", () => {
  it("renders the public connection fields", () => {
    render(<OpenAICompatibleCard siteId="site-1" t={((_: string, fallback: string) => fallback) as never} />);

    expect(screen.getByText("Add OpenAI Compatible")).toBeInTheDocument();
    expect(screen.getByText("API Type")).toBeInTheDocument();
    expect(screen.getByText("Base URL")).toBeInTheDocument();
    expect(screen.getByText("API Key")).toBeInTheDocument();
    expect(screen.getByText("Model ID (optional)")).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Chat Completions (OpenAI-compatible)" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "OpenAI Images (/images/*)" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "OpenAI Responses (/responses)" })).toBeInTheDocument();
  });
});
