// Shared UI primitives — typed ports of prototype/src/primitives.jsx.
import { useEffect, useState } from "react";
import type { ReactNode, ButtonHTMLAttributes, HTMLAttributes, FC } from "react";
import { Icons, type IconName } from "../icons";

// ---------- Badge ----------
type BadgeVariant = "default" | "success" | "warning" | "danger" | "info" | "brand";
type BadgeProps = HTMLAttributes<HTMLSpanElement> & {
  variant?: BadgeVariant;
  dot?: boolean;
};
export function Badge({ children, variant = "default", dot = false, className = "", ...rest }: BadgeProps) {
  const cls =
    "badge " +
    (variant !== "default" ? `badge-${variant} ` : "") +
    (dot ? "badge-dot " : "") +
    className;
  return (
    <span className={cls} {...rest}>
      {children}
    </span>
  );
}

// ---------- Button ----------
type BtnVariant = "primary" | "secondary" | "ghost" | "danger";
type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: BtnVariant;
  size?: "" | "sm" | "lg";
  icon?: IconName | FC<any>;
  iconRight?: IconName | FC<any>;
  children?: ReactNode;
};
export function Btn({
  children,
  variant = "primary",
  size = "",
  icon,
  iconRight,
  className,
  ...rest
}: BtnProps) {
  const Ic = typeof icon === "string" ? Icons[icon] : icon;
  const IcR = typeof iconRight === "string" ? Icons[iconRight] : iconRight;
  const cls = `btn btn-${variant}${size ? " btn-" + size : ""}${className ? " " + className : ""}`;
  return (
    <button type="button" className={cls} {...rest}>
      {Ic ? <Ic style={{ width: 14, height: 14 }} /> : null}
      {children}
      {IcR ? <IcR style={{ width: 14, height: 14 }} /> : null}
    </button>
  );
}

// ---------- Card ----------
export function Card({ children, className = "", ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={`card ${className}`} {...rest}>
      {children}
    </div>
  );
}

export function CardHead({
  title,
  subtitle,
  action,
  icon,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
  icon?: IconName | FC<any>;
}) {
  const Ic = typeof icon === "string" ? Icons[icon] : icon;
  return (
    <div className="card-head">
      <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
        {Ic ? (
          <div
            style={{
              width: 34,
              height: 34,
              borderRadius: 8,
              background: "var(--surface)",
              border: "1px solid var(--border)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "var(--brand-400)",
            }}
          >
            <Ic style={{ width: 16, height: 16 }} />
          </div>
        ) : null}
        <div>
          <div style={{ fontSize: 14, fontWeight: 600 }}>{title}</div>
          {subtitle ? <div className="caption" style={{ marginTop: 2 }}>{subtitle}</div> : null}
        </div>
      </div>
      {action}
    </div>
  );
}

// ---------- Switch ----------
export function Switch({ on, onChange }: { on: boolean; onChange: (v: boolean) => void }) {
  return (
    <div
      role="switch"
      aria-checked={on}
      tabIndex={0}
      onClick={() => onChange(!on)}
      onKeyDown={(e) => {
        if (e.key === " " || e.key === "Enter") {
          e.preventDefault();
          onChange(!on);
        }
      }}
      className={`switch ${on ? "on" : ""}`}
    />
  );
}

// ---------- Segmented ----------
export type SegOption<T extends string> = { value: T; label: string };
export function Seg<T extends string>({
  value,
  onChange,
  options,
}: {
  value: T;
  onChange: (v: T) => void;
  options: SegOption<T>[];
}) {
  return (
    <div className="seg">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          className={o.value === value ? "is-active" : ""}
          onClick={() => onChange(o.value)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

// ---------- CopyField ----------
export function CopyField({ value, mask = false }: { value: string; mask?: boolean }) {
  const [copied, setCopied] = useState(false);
  const [show, setShow] = useState(!mask);
  const display = mask && !show ? "•".repeat(Math.min(40, value.length)) : value;
  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(value);
    } catch {
      // ignore — clipboard may be blocked
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 1400);
  };
  return (
    <div className="copy-field">
      <span>{display}</span>
      {mask ? (
        <button type="button" onClick={() => setShow((s) => !s)} title={show ? "Hide" : "Show"}>
          {show ? (
            <Icons.eyeOff style={{ width: 14, height: 14 }} />
          ) : (
            <Icons.eye style={{ width: 14, height: 14 }} />
          )}
        </button>
      ) : null}
      <button type="button" onClick={onCopy}>
        {copied ? "Copied" : "Copy"}
      </button>
    </div>
  );
}

// ---------- Spark ----------
export function Spark({ values = [], height = 20 }: { values?: number[]; height?: number }) {
  const max = Math.max(...values, 1);
  return (
    <div className="spark" style={{ height }}>
      {values.map((v, i) => (
        <span
          key={i}
          style={{
            height: `${Math.max(10, (v / max) * 100)}%`,
            opacity: 0.4 + (i / Math.max(1, values.length)) * 0.6,
          }}
        />
      ))}
    </div>
  );
}

// ---------- Donut ----------
export function Donut({ value = 40, size = 72, color }: { value?: number; size?: number; color?: string }) {
  const r = size / 2 - 6;
  const c = 2 * Math.PI * r;
  const stroke = color || "var(--brand-500)";
  return (
    <svg width={size} height={size} className="donut">
      <circle cx={size / 2} cy={size / 2} r={r} stroke="var(--surface-2)" />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        stroke={stroke}
        strokeDasharray={c}
        strokeDashoffset={c - (value / 100) * c}
        strokeLinecap="round"
      />
    </svg>
  );
}

// ---------- Avatar ----------
export function Avatar({ name = "U", size = 28 }: { name?: string; size?: number }) {
  const initial = name.trim().slice(0, 1).toUpperCase();
  const hash = [...name].reduce((a, ch) => a + ch.charCodeAt(0), 0);
  const hue = (hash * 37) % 360;
  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: "50%",
        background: `oklch(0.55 0.14 ${hue})`,
        color: "#fff",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: size * 0.42,
        fontWeight: 600,
        flexShrink: 0,
      }}
    >
      {initial}
    </div>
  );
}

// ---------- EmptyState ----------
export function EmptyState({
  icon = "cube",
  title,
  children,
  action,
}: {
  icon?: IconName;
  title: ReactNode;
  children?: ReactNode;
  action?: ReactNode;
}) {
  const Ic = Icons[icon];
  return (
    <div style={{ padding: "48px 20px", textAlign: "center" }}>
      <div
        style={{
          width: 52,
          height: 52,
          margin: "0 auto 16px",
          borderRadius: 12,
          background: "var(--surface)",
          border: "1px solid var(--border)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "var(--text-subtle)",
        }}
      >
        <Ic style={{ width: 22, height: 22 }} />
      </div>
      <div className="h-3" style={{ marginBottom: 6 }}>
        {title}
      </div>
      <div className="caption" style={{ maxWidth: 380, margin: "0 auto 16px" }}>
        {children}
      </div>
      {action}
    </div>
  );
}

// ---------- Toast ----------
export function Toast({ msg, onClose }: { msg: string; onClose: () => void }) {
  useEffect(() => {
    if (!msg) return;
    const t = setTimeout(onClose, 2800);
    return () => clearTimeout(t);
  }, [msg, onClose]);
  if (!msg) return null;
  return (
    <div
      style={{
        position: "fixed",
        bottom: 24,
        left: "50%",
        transform: "translateX(-50%)",
        background: "var(--bg-elevated)",
        border: "1px solid var(--border)",
        borderRadius: 10,
        padding: "10px 16px",
        boxShadow: "var(--shadow-pop)",
        fontSize: 13,
        zIndex: 200,
        display: "flex",
        gap: 10,
        alignItems: "center",
      }}
    >
      <Icons.check style={{ width: 14, height: 14, color: "var(--success)" }} />
      {msg}
    </div>
  );
}

// ---------- Step ----------
export function Step({
  n,
  title,
  children,
  ghost = false,
  done = false,
}: {
  n: number;
  title: ReactNode;
  children?: ReactNode;
  ghost?: boolean;
  done?: boolean;
}) {
  return (
    <div style={{ display: "flex", gap: 14 }}>
      <div
        style={{
          width: 28,
          height: 28,
          borderRadius: "50%",
          flexShrink: 0,
          background: done ? "var(--success)" : ghost ? "var(--surface)" : "var(--brand-500)",
          color: done ? "#000" : ghost ? "var(--text-muted)" : "#000",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontWeight: 600,
          fontSize: 12,
          border: ghost ? "1px solid var(--border)" : "none",
        }}
      >
        {done ? <Icons.check style={{ width: 12, height: 12 }} /> : n}
      </div>
      <div style={{ flex: 1, paddingTop: 2 }}>
        <div style={{ fontSize: 14, fontWeight: 500, marginBottom: 10 }}>{title}</div>
        {children}
      </div>
    </div>
  );
}
