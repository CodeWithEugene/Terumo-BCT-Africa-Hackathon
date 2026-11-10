// Small hand-drawn icons. One stroke weight, no fills, so they sit quietly beside text.
import type { SVGProps } from 'react'

const paths: Record<string, React.ReactNode> = {
  brief: (
    <>
      <rect x="3" y="5" width="18" height="14" rx="2.5" />
      <path d="M7.5 9v6M12 9v6M16.5 9v6" />
    </>
  ),
  region: (
    <>
      <rect x="3.5" y="3.5" width="7" height="7" rx="1.5" />
      <rect x="13.5" y="3.5" width="7" height="7" rx="1.5" />
      <rect x="3.5" y="13.5" width="7" height="7" rx="1.5" />
      <rect x="13.5" y="13.5" width="7" height="7" rx="1.5" />
    </>
  ),
  decisions: (
    <>
      <path d="M9 6h11M9 12h11M9 18h11" />
      <path d="M3.5 6l1.2 1.2L6.8 5M3.5 12l1.2 1.2 2.1-2.2M3.5 18l1.2 1.2 2.1-2.2" />
    </>
  ),
  accuracy: (
    <>
      <path d="M4 19V5M4 19h16" />
      <path d="M7 15l4-5 3 3 5-7" />
    </>
  ),
  privacy: (
    <>
      <path d="M12 3l7.5 3v5.5c0 4.5-3 8-7.5 9.5-4.5-1.5-7.5-5-7.5-9.5V6L12 3z" />
      <path d="M9 12l2.2 2.2L15.2 10" />
    </>
  ),
  signout: (
    <>
      <path d="M14 4h4.5A1.5 1.5 0 0120 5.5v13a1.5 1.5 0 01-1.5 1.5H14" />
      <path d="M10 8l-4 4 4 4M6 12h9" />
    </>
  ),
  steady: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M8.2 12.2l2.6 2.6 5-5.4" />
    </>
  ),
  watch: (
    <>
      <path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z" />
      <circle cx="12" cy="12" r="2.8" />
    </>
  ),
  act: (
    <>
      <path d="M12 3.5l9.5 16.5h-19L12 3.5z" />
      <path d="M12 10v4.5M12 17.2v.3" />
    </>
  ),
  not_held: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M8 12h8" />
    </>
  ),
  calendar: (
    <>
      <rect x="3.5" y="5" width="17" height="15" rx="2.5" />
      <path d="M3.5 10h17M8 3v4M16 3v4" />
    </>
  ),
  delivery: (
    <>
      <path d="M2.5 6.5h11v10h-11zM13.5 10h4l3 3v3.5h-7" />
      <circle cx="7" cy="17.5" r="1.8" />
      <circle cx="17" cy="17.5" r="1.8" />
    </>
  ),
  arrow: <path d="M5 12h14M13 6l6 6-6 6" />,
  back: <path d="M19 12H5M11 6l-6 6 6 6" />,
  chevron: <path d="M9 6l6 6-6 6" />,
  close: <path d="M6 6l12 12M18 6L6 18" />,
  user: (
    <>
      <circle cx="12" cy="8.5" r="3.8" />
      <path d="M4.5 20c1-3.8 4-5.5 7.5-5.5s6.500 1.700 7.500 5.500" />
    </>
  ),
  offline: (
    <>
      <path d="M3 9.500a13 13 0 0118 0M6.500 13a8 8 0 0111 0M12 17.500v.3" />
      <path d="M4 4l16 16" />
    </>
  ),
  retry: (
    <>
      <path d="M20 12a8 8 0 11-2.6-5.900" />
      <path d="M20 4v4.500h-4.500" />
    </>
  ),
  shelf: (
    <>
      <path d="M3 19h18M5 19V8M19 19V8M5 13h14" />
      <rect x="8" y="8.500" width="3" height="4.500" rx=".6" />
      <rect x="13" y="14.500" width="3" height="4.500" rx=".6" />
    </>
  ),
  expiry: (
    <>
      <circle cx="12" cy="12.500" r="8" />
      <path d="M12 8v4.500l3 2M9.500 2.500h5" />
    </>
  ),
  trend: <path d="M3.500 17l5.500-6 4 3.500 7-8.500M15 6h5v5" />,
  unmet: (
    <>
      <circle cx="12" cy="12" r="8.500" />
      <path d="M9 9l6 6M15 9l-6 6" />
    </>
  ),
  school: (
    <>
      <path d="M2.500 9.500L12 5l9.500 4.500L12 14 2.500 9.500z" />
      <path d="M6.500 11.500V16c1.500 1.500 3.500 2 5.500 2s4-.5 5.500-2v-4.500" />
    </>
  ),
  centre: (
    <>
      <path d="M4 20V9l8-5 8 5v11" />
      <path d="M9.500 20v-5.500h5V20M12 8.500v3M10.500 10h3" />
    </>
  ),
  supply: (
    <>
      <path d="M12 3.500c3 3.800 5 6.500 5 9.500a5 5 0 01-10 0c0-3 2-5.700 5-9.500z" />
    </>
  ),
  supply_forecast: (
    <>
      <path d="M12 3.500c3 3.800 5 6.500 5 9.500a5 5 0 01-10 0c0-3 2-5.700 5-9.500z" />
      <path d="M9.800 13.500a2.300 2.300 0 002.200 2.300" />
    </>
  ),
  minimum: <path d="M4 18h16M12 5v9M8.500 10.500L12 14l3.500-3.500" />,
  info: (
    <>
      <circle cx="12" cy="12" r="8.500" />
      <path d="M12 11v5.500M12 7.700v.3" />
    </>
  ),
  check: <path d="M5 12.500l4.500 4.500L19 7" />,
  edit: <path d="M4 20h4L19.500 8.500l-4-4L4 16v4zM13.500 6.500l4 4" />,
  minus: <path d="M6 12h12" />,
  plus: <path d="M12 6v12M6 12h12" />,
  table: (
    <>
      <rect x="3.500" y="5" width="17" height="14" rx="2" />
      <path d="M3.500 10h17M3.500 14.500h17M9.500 5v14" />
    </>
  ),
  code: <path d="M8.500 7L3.500 12l5 5M15.500 7l5 5-5 5" />,
}

export type IconName = keyof typeof paths

export function Icon({ name, size = 20, ...rest }: { name: string; size?: number } & SVGProps<SVGSVGElement>) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      {paths[name] ?? paths.info}
    </svg>
  )
}
