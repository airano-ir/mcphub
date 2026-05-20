// Logo + wordmark — uses the original brand mark from core/templates/static/logo.svg.
// Path data is inlined so we can drive fills with CSS variables (theme-aware).
// `original=true` swaps to the source palette (#51b9f4 / #fec13d) for marketing.

type LogoProps = {
  size?: number;
  className?: string;
  /** When true, use the original brand colors instead of the theme tokens. */
  original?: boolean;
};

export function Logo({ size = 28, className, original = false }: LogoProps) {
  const a = original ? "#51b9f4" : "var(--brand-500)";
  const b = original ? "#fec13d" : "var(--accent-500)";
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 1024 1024"
      xmlns="http://www.w3.org/2000/svg"
      aria-label="MCP Hub"
      className={className}
    >
      <path
        fill={a}
        d="m496.4 11.5q5.4-0.4 10.9-0.5 5.4-0.1 10.9 0.1 5.4 0.2 10.8 0.7 5.5 0.4 10.9 1.2c56.2 7.7 99.4 36 133.3 81.3 31 41.4 41 94.3 34.8 144.5-6.9 54.7-31.6 89.2-71.8 124.8-9.7 8.6-19.4 21-29.9 28.7 8 7.2 17.5 17 25.1 24.8 8.6-11.9 22.8-24.8 33.4-35.4 10.6-10.1 20.7-22.2 32.2-31.2 44.5-34.8 109.1-43.7 163.2-31.3 97.6 22.4 162.8 115.9 151.4 215.3-12.8 111.6-114.9 189.3-225.7 173.7-56.9-8-89.1-29.9-126.7-72.5-8.4-9.5-20.3-19-28.1-29.2-3 4.4-20.1 21-24.7 25.2q0.8 0.7 1.6 1.4c10.3 8.9 20.5 20.3 30 29.2 31.4 29.2 55.6 55.7 65.1 98.8 3 13.7 4.9 22.1 6.1 36.6 4.1 52.5-11.2 105-46 144.9-28.1 32.3-64.1 56.5-106.4 64.9-9.6 2-17.3 3.9-27.3 4.6-11.3 1.4-27.3 0.9-38.7-0.3-55.1-6.2-100.6-31.3-135.2-74.7-6.8-8.5-12.8-17.6-18.1-27.2-5.2-9.5-9.7-19.4-13.3-29.7-3.6-10.3-6.3-20.8-8.1-31.6-1.9-10.7-2.8-21.5-2.8-32.4-0.3-41.9 11.1-88.4 38.8-121 5-5.8 10.5-11.8 16.2-17.1 15.8-14.8 31.2-33.3 48-46.7-7.7-8-17.1-16.5-24.2-24.6-8.4 9.8-18.5 19-27.4 28.3-10.5 10.8-20.7 21.7-31.8 31.9-36.3 32.8-85.8 44.5-133.6 42.7-12.8-0.5-25.5-2.3-38-5.3-12.5-3-24.6-7.3-36.2-12.7-11.7-5.4-22.7-11.9-33.1-19.4-10.3-7.6-19.9-16.2-28.6-25.6-46.8-50.7-62.6-116.6-46.9-183.1 8.7-41.1 30.3-72.1 60.7-100.4 64.9-60.6 180.9-67.1 250.4-10.7 10.9 8.8 22.5 21.5 32.4 31.7 10.5 10.9 21.9 21.7 32.1 33 8.1-11 14.4-15.9 23.9-24.9-37.7-41.9-77.8-63.2-94-122.1-17.9-65.2-8.7-131.9 34.5-185.2 37.9-46.8 81.1-66.8 139.9-73.5z"
      />
      <path
        fill={b}
        d="M210 432c44 0.6 79 36 79 80 0 44-36 79-80 79-44 0-80-36-80-80 0-44 37-80 81-79z m294-302c44-5 83 27 87 71 5 44-27 83-71 87-44 4-83-27-87-71-4-44 27-83 71-87z m0 606c44-5 83 27 88 70 5 44-27 83-71 88-44 5-83-27-88-71-5-43 27-83 71-87z m302-302c44-5 83 26 88 70 5 44-26 83-70 88-44 5-83-26-88-70-5-44 26-83 70-88z"
      />
    </svg>
  );
}

type WordmarkProps = {
  /** Logo mark size in px. The wordmark text auto-scales to feel proportional. */
  size?: number;
  /** Hide the text — useful when the sidebar is collapsed. */
  iconOnly?: boolean;
  className?: string;
};

export function LogoWordmark({ size = 28, iconOnly = false, className }: WordmarkProps) {
  // The brand "MCP Hub" must always read left-to-right regardless of page
  // direction — flipping it to "Hub MCP" in RTL would mangle the proper noun.
  // `dir="ltr"` pins the inline flow, then `unicode-bidi: bidi-override` (set
  // via .logo-text in CSS) keeps the order stable even when the surrounding
  // paragraph is RTL.
  return (
    <span
      className={`logo-wrap${className ? ` ${className}` : ""}`}
      style={{ ["--logo-size" as string]: `${size}px` }}
      dir="ltr"
    >
      <Logo size={size} />
      {iconOnly ? null : (
        <span className="logo-text" aria-hidden={false}>
          <span className="logo-text-primary">MCP</span>
          <span className="logo-text-secondary">Hub</span>
        </span>
      )}
    </span>
  );
}
