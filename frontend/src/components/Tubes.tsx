/**
 * Test tubes drawn by us in SVG: glass outline, a highlight, a rounded base and
 * a liquid level. Used very faintly and without motion behind the sign-in
 * screen, and with depth on the landing page. Never behind data.
 */
export function Tube({
  x,
  y,
  height = 150,
  width = 34,
  level = 0.55,
  rotate = 0,
  liquid = 'var(--color-sky)',
  opacity = 1,
}: {
  x: number
  y: number
  height?: number
  width?: number
  level?: number
  rotate?: number
  liquid?: string
  opacity?: number
}) {
  const r = width / 2
  const inner = width - 8
  const liquidHeight = (height - r - 14) * level
  const liquidTop = height - 4 - liquidHeight
  return (
    <g transform={`translate(${x} ${y}) rotate(${rotate} ${r} ${height / 2})`} opacity={opacity}>
      {/* liquid, clipped by the rounded base */}
      <path
        d={`M4 ${liquidTop} h${inner} v${liquidHeight - inner / 2} a${inner / 2} ${inner / 2} 0 0 1 -${inner} 0 z`}
        fill={liquid}
        opacity="0.55"
      />
      <ellipse cx={r} cy={liquidTop} rx={inner / 2} ry="3" fill={liquid} opacity="0.8" />
      {/* glass */}
      <path
        d={`M1 6 v${height - r - 6} a${r - 1} ${r - 1} 0 0 0 ${width - 2} 0 v-${height - r - 6}`}
        fill="none"
        stroke="var(--color-ink)"
        strokeOpacity="0.35"
        strokeWidth="1.5"
      />
      <rect x="-2" y="0" width={width + 4} height="7" rx="3.5" fill="white" stroke="var(--color-ink)" strokeOpacity="0.35" strokeWidth="1.5" />
      {/* highlight */}
      <path d={`M${width - 8} 16 v${height - r - 30}`} stroke="white" strokeWidth="3" strokeLinecap="round" opacity="0.8" />
    </g>
  )
}

export function TubesBackdrop() {
  return (
    <svg
      className="pointer-events-none absolute inset-0 h-full w-full"
      viewBox="0 0 1200 700"
      preserveAspectRatio="xMaxYMid slice"
      aria-hidden="true"
    >
      <g opacity="0.22">
        <Tube x={820} y={70} height={210} width={44} level={0.6} rotate={-10} />
        <Tube x={930} y={220} height={260} width={54} level={0.42} rotate={8} />
        <Tube x={1060} y={90} height={180} width={38} level={0.7} rotate={14} />
        <Tube x={760} y={400} height={170} width={36} level={0.5} rotate={-18} />
        <Tube x={1090} y={380} height={220} width={46} level={0.35} rotate={-6} />
      </g>
    </svg>
  )
}
