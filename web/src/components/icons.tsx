// Lucide-style inline SVG icons.
// Stroke 1.75, 24px viewBox. Color via currentColor so they inherit from text.
import type { SVGProps, ReactNode, FC } from "react";

type Props = SVGProps<SVGSVGElement>;

const make =
  (path: ReactNode, viewBox = "0 0 24 24"): FC<Props> =>
  (props) => (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox={viewBox}
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      width={16}
      height={16}
      {...props}
    >
      {path}
    </svg>
  );

export const Icons = {
  home: make(
    <>
      <path d="M3 12 12 3l9 9" />
      <path d="M5 10v10h14V10" />
    </>,
  ),
  sites: make(
    <>
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M3 9h18" />
      <path d="M8 4v5" />
    </>,
  ),
  plug: make(
    <>
      <path d="M9 2v6" />
      <path d="M15 2v6" />
      <path d="M6 8h12v4a6 6 0 0 1-12 0V8Z" />
      <path d="M12 18v4" />
    </>,
  ),
  key: make(
    <>
      <circle cx="8" cy="15" r="4" />
      <path d="m10.5 12.5 9-9" />
      <path d="m18 5 3 3" />
      <path d="m15 8 3 3" />
    </>,
  ),
  shield: make(<path d="M12 3 4 6v6c0 5 3.5 8.5 8 9 4.5-.5 8-4 8-9V6l-8-3Z" />),
  activity: make(<path d="M22 12h-4l-3 9L9 3l-3 9H2" />),
  logs: make(
    <>
      <path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9Z" />
      <path d="M14 3v6h6" />
      <path d="M8 13h8" />
      <path d="M8 17h6" />
    </>,
  ),
  settings: make(
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3h0A1.7 1.7 0 0 0 10 3.1V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8v0a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z" />
    </>,
  ),
  search: make(
    <>
      <circle cx="11" cy="11" r="7" />
      <path d="m21 21-4.3-4.3" />
    </>,
  ),
  user: make(
    <>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 21a8 8 0 0 1 16 0" />
    </>,
  ),
  bell: make(
    <>
      <path d="M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
      <path d="M10.3 21a2 2 0 0 0 3.4 0" />
    </>,
  ),
  chev: make(<path d="m6 9 6 6 6-6" />),
  chevR: make(<path d="m9 6 6 6-6 6" />),
  check: make(<path d="M20 6 9 17l-5-5" />),
  plus: make(
    <>
      <path d="M12 5v14" />
      <path d="M5 12h14" />
    </>,
  ),
  arrow: make(
    <>
      <path d="M5 12h14" />
      <path d="m12 5 7 7-7 7" />
    </>,
  ),
  copy: make(
    <>
      <rect x="8" y="8" width="13" height="13" rx="2" />
      <path d="M5 16V5a2 2 0 0 1 2-2h11" />
    </>,
  ),
  eye: make(
    <>
      <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" />
      <circle cx="12" cy="12" r="3" />
    </>,
  ),
  eyeOff: make(
    <>
      <path d="M10.7 5.1A8 8 0 0 1 12 5c6.5 0 10 7 10 7a16 16 0 0 1-3.3 4" />
      <path d="M6.1 6.1A16 16 0 0 0 2 12s3.5 7 10 7a10 10 0 0 0 4.5-1" />
      <path d="m2 2 20 20" />
      <path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" />
    </>,
  ),
  trash: make(
    <>
      <path d="M3 6h18" />
      <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6" />
    </>,
  ),
  edit: make(
    <>
      <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
      <path d="m18.5 2.5 3 3L12 15l-4 1 1-4 9.5-9.5Z" />
    </>,
  ),
  download: make(
    <>
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <path d="m7 10 5 5 5-5" />
      <path d="M12 15V3" />
    </>,
  ),
  link: make(
    <>
      <path d="M10 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1" />
      <path d="M14 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1" />
    </>,
  ),
  github: make(
    <>
      <path d="M15 22v-4a3.4 3.4 0 0 0-1-2.8c3.3-.3 6.6-1.6 6.6-7A5.5 5.5 0 0 0 19 4.8 5 5 0 0 0 18.9 1s-1.2-.3-4 1.5a13.4 13.4 0 0 0-7 0C5.1.7 3.9 1 3.9 1A5 5 0 0 0 3.8 4.8 5.5 5.5 0 0 0 2.4 8.2c0 5.4 3.3 6.7 6.5 7A3.4 3.4 0 0 0 8 18v4" />
      <path d="M9 18c-4 1.5-4.5-2-6.5-2" />
    </>,
  ),
  terminal: make(
    <>
      <path d="m4 17 6-6-6-6" />
      <path d="M12 19h8" />
    </>,
  ),
  chart: make(
    <>
      <path d="M3 3v18h18" />
      <path d="m7 15 4-4 4 4 6-6" />
    </>,
  ),
  spark: make(
    <path d="M12 3v3M12 18v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M3 12h3M18 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1" />,
  ),
  zap: make(<path d="M13 2 3 14h7l-1 8 10-12h-7l1-8Z" />),
  globe: make(
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18" />
      <path d="M12 3a14 14 0 0 1 0 18" />
      <path d="M12 3a14 14 0 0 0 0 18" />
    </>,
  ),
  users: make(
    <>
      <circle cx="9" cy="8" r="4" />
      <path d="M2 21a7 7 0 0 1 14 0" />
      <path d="M16 3.1a4 4 0 0 1 0 7.8" />
      <path d="M22 21a7 7 0 0 0-6-6.9" />
    </>,
  ),
  logout: make(
    <>
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <path d="m16 17 5-5-5-5" />
      <path d="M21 12H9" />
    </>,
  ),
  moon: make(<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z" />),
  monitor: make(
    <>
      <rect x="2" y="3" width="20" height="14" rx="2" />
      <path d="M8 21h8M12 17v4" />
    </>,
  ),
  sun: make(
    <>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </>,
  ),
  menu: make(
    <>
      <path d="M4 6h16" />
      <path d="M4 12h16" />
      <path d="M4 18h16" />
    </>,
  ),
  x: make(
    <>
      <path d="M18 6 6 18" />
      <path d="m6 6 12 12" />
    </>,
  ),
  sparkles: make(
    <>
      <path d="M12 3v4M12 17v4M5 12H1M23 12h-4M7 7 4 4M20 20l-3-3M7 17l-3 3M20 4l-3 3" />
      <circle cx="12" cy="12" r="3" />
    </>,
  ),
  info: make(
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 8v.01" />
      <path d="M11 12h1v4h1" />
    </>,
  ),
  warning: make(
    <>
      <path d="m12 3 10 17H2L12 3z" />
      <path d="M12 9v5" />
      <path d="M12 18v.01" />
    </>,
  ),
  server: make(
    <>
      <rect x="3" y="4" width="18" height="7" rx="2" />
      <rect x="3" y="13" width="18" height="7" rx="2" />
      <path d="M7 8h.01M7 17h.01" />
    </>,
  ),
  filter: make(<path d="M4 4h16l-6 8v7l-4-2v-5L4 4z" />),
  refresh: make(
    <>
      <path d="M3 12a9 9 0 0 1 15-6.7L21 8" />
      <path d="M21 3v5h-5" />
      <path d="M21 12a9 9 0 0 1-15 6.7L3 16" />
      <path d="M3 21v-5h5" />
    </>,
  ),
  clock: make(
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </>,
  ),
  cube: make(
    <>
      <path d="M21 8 12 3 3 8l9 5 9-5Z" />
      <path d="M3 8v8l9 5 9-5V8" />
      <path d="M12 13v8" />
    </>,
  ),
  rocket: make(
    <>
      <path d="M5 13 3 19l6-2" />
      <path d="M14 6s6-5 8-2-2 8-2 8l-9 9-6-6 9-9Z" />
      <circle cx="15" cy="9" r="1.5" />
    </>,
  ),
  wrench: make(
    <path d="M15 5a4 4 0 0 1-4.5 4L4 15.5 8.5 20 15 13.5a4 4 0 0 1 5-5l-3-3 3-3a4 4 0 0 0-5 2.5Z" />,
  ),
  bolt: make(<path d="M13 3 3 14h7l-1 7 10-11h-7l1-7Z" />),
  docs: make(
    <>
      <path d="M4 4v16a2 2 0 0 0 2 2h12V2H6a2 2 0 0 0-2 2Z" />
      <path d="M18 2v20" />
      <path d="M8 7h6M8 11h6M8 15h4" />
    </>,
  ),
  command: make(
    <path d="M6 2a4 4 0 1 1-4 4V2h4Zm12 0a4 4 0 1 0 4 4V2h-4ZM6 22a4 4 0 1 0-4-4v4h4Zm12 0a4 4 0 1 1 4-4v4h-4ZM6 6h12v12H6V6Z" />,
  ),
  external: make(
    <>
      <path d="M14 3h7v7" />
      <path d="M10 14 21 3" />
      <path d="M21 14v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5" />
    </>,
  ),
} as const;

export type IconName = keyof typeof Icons;
