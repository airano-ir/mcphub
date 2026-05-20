import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { Logo, LogoWordmark } from "../components/Logo";

describe("Logo", () => {
  it("renders the brand mark with default size", () => {
    const { container } = render(<Logo />);
    const svg = container.querySelector("svg");
    expect(svg).toBeInTheDocument();
    expect(svg).toHaveAttribute("width", "28");
    expect(svg).toHaveAttribute("aria-label", "MCP Hub");
  });

  it("uses CSS vars for fills by default (theme-aware)", () => {
    const { container } = render(<Logo />);
    const paths = container.querySelectorAll("path");
    expect(paths).toHaveLength(2);
    expect(paths[0].getAttribute("fill")).toContain("var(--brand-500)");
    expect(paths[1].getAttribute("fill")).toContain("var(--accent-500)");
  });

  it("falls back to original colors when original=true", () => {
    const { container } = render(<Logo original />);
    const paths = container.querySelectorAll("path");
    expect(paths[0].getAttribute("fill")).toBe("#51b9f4");
    expect(paths[1].getAttribute("fill")).toBe("#fec13d");
  });

  it("LogoWordmark renders text and SVG", () => {
    const { getByText, container } = render(<LogoWordmark />);
    expect(getByText(/MCP/)).toBeInTheDocument();
    expect(getByText(/Hub/)).toBeInTheDocument();
    expect(container.querySelector("svg")).toBeInTheDocument();
  });
});
