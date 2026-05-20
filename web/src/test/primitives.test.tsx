import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Badge, Btn, Switch, Seg, Toast } from "../components/primitives";

describe("Badge", () => {
  it("renders children with variant class", () => {
    const { container } = render(<Badge variant="success">healthy</Badge>);
    const span = container.firstChild as HTMLElement;
    expect(span.className).toContain("badge");
    expect(span.className).toContain("badge-success");
    expect(span.textContent).toBe("healthy");
  });

  it("adds badge-dot class when dot=true", () => {
    const { container } = render(<Badge dot>x</Badge>);
    expect((container.firstChild as HTMLElement).className).toContain("badge-dot");
  });
});

describe("Btn", () => {
  it("invokes onClick", () => {
    const handler = vi.fn();
    render(<Btn onClick={handler}>click</Btn>);
    fireEvent.click(screen.getByText("click"));
    expect(handler).toHaveBeenCalled();
  });

  it("respects disabled", () => {
    const handler = vi.fn();
    render(
      <Btn onClick={handler} disabled>
        x
      </Btn>,
    );
    fireEvent.click(screen.getByText("x"));
    expect(handler).not.toHaveBeenCalled();
  });
});

describe("Switch", () => {
  it("toggles via click", () => {
    const handler = vi.fn();
    const { container } = render(<Switch on={false} onChange={handler} />);
    fireEvent.click(container.firstChild as HTMLElement);
    expect(handler).toHaveBeenCalledWith(true);
  });

  it("reflects on state via class", () => {
    const { container } = render(<Switch on={true} onChange={() => {}} />);
    expect((container.firstChild as HTMLElement).className).toContain("on");
  });
});

describe("Seg", () => {
  it("highlights active option and switches on click", () => {
    const handler = vi.fn();
    render(
      <Seg
        value="a"
        onChange={handler}
        options={[
          { value: "a", label: "A" },
          { value: "b", label: "B" },
        ]}
      />,
    );
    expect(screen.getByText("A").className).toContain("is-active");
    fireEvent.click(screen.getByText("B"));
    expect(handler).toHaveBeenCalledWith("b");
  });
});

describe("Toast", () => {
  it("renders msg", () => {
    render(<Toast msg="saved" onClose={() => {}} />);
    expect(screen.getByText("saved")).toBeInTheDocument();
  });

  it("renders nothing without msg", () => {
    const { container } = render(<Toast msg="" onClose={() => {}} />);
    expect(container.firstChild).toBeNull();
  });
});
