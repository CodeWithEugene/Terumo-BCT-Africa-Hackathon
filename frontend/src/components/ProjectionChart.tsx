import { useEffect, useRef, useState } from 'react'
import { t } from '../i18n/en'
import type { Series } from '../types'

/**
 * 14 days of projected stock, drawn by hand in SVG.
 * One line (expected stock), one band (busy to quiet), dashed markers for
 * deliveries, a marker where stock runs out, barely visible weekend shading,
 * and no gridlines except the zero line. Redraws to the width of its box.
 */
export function ProjectionChart({ series, showActual }: { series: Series; showActual: boolean }) {
  const box = useRef<HTMLDivElement>(null)
  const [width, setWidth] = useState(520)
  useEffect(() => {
    if (!box.current) return
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(280, Math.round(entry.contentRect.width))))
    observer.observe(box.current)
    return () => observer.disconnect()
  }, [])

  const days = series.projection ?? []
  if (days.length === 0) return null
  const actual = showActual ? (series.actual?.days ?? []) : []
  const height = width < 420 ? 220 : 250
  const pad = { top: 30, right: 14, bottom: 48, left: 34 }
  const innerW = width - pad.left - pad.right
  const innerH = height - pad.top - pad.bottom
  const start = series.units_on_shelf
  const top = Math.max(4, start, ...days.map((d) => d.stock_high), ...actual.map((d) => d.stock)) * 1.12
  // Point 0 is "now" (the shelf this morning); point i + 1 is the end of day i.
  const x = (i: number) => pad.left + (innerW * i) / days.length
  const y = (v: number) => pad.top + innerH * (1 - v / top)
  const line = [start, ...days.map((d) => d.stock)]
  const low = [start, ...days.map((d) => d.stock_low)]
  const high = [start, ...days.map((d) => d.stock_high)]
  const path = (values: number[]) => values.map((v, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(' ')
  const band = `${path(high)} ${low.map((_, i) => `L${x(low.length - 1 - i).toFixed(1)} ${y(low[low.length - 1 - i]).toFixed(1)}`).join(' ')} Z`
  const outIndex = series.stockout_date ? days.findIndex((d) => d.date === series.stockout_date) : -1
  const every = width < 420 ? 3 : 2
  const ticks = [0, Math.round(top / 1.12 / 2), Math.round(top / 1.12)].filter((v, i, a) => a.indexOf(v) === i)
  const lastY = y(line[line.length - 1])

  return (
    <div ref={box} className="w-full">
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${t.detail.chartTitle}. ${series.status_line}`}>
        {/* weekends, barely visible */}
        {days.map((d, i) => d.weekend && <rect key={d.date} x={x(i)} y={pad.top} width={innerW / days.length} height={innerH} fill="#141b4d" opacity="0.035" />)}
        {/* range band */}
        <path d={band} fill="var(--color-sky-soft)" opacity="0.9" />
        {/* zero line and a few quiet axis numbers */}
        <line x1={pad.left} x2={width - pad.right} y1={y(0)} y2={y(0)} stroke="var(--color-ink)" strokeOpacity="0.35" />
        {ticks.map((v) => (
          <text key={v} x={pad.left - 8} y={y(v) + 4} textAnchor="end" fontSize="11" fill="var(--color-muted)">
            {v}
          </text>
        ))}
        {/* deliveries */}
        {days.map(
          (d, i) =>
            d.is_delivery_day && (
              <g key={`d-${d.date}`}>
                <line x1={x(i) + innerW / days.length / 2} x2={x(i) + innerW / days.length / 2} y1={pad.top - 4} y2={y(0)} stroke="var(--color-ink)" strokeOpacity="0.45" strokeDasharray="3 4" />
                {d.delivery >= 0.05 && (
                  <text x={x(i) + innerW / days.length / 2} y={pad.top - 9} textAnchor="middle" fontSize="11" fill="var(--color-body)">
                    +{d.delivery >= 10 ? d.delivery.toFixed(0) : d.delivery}
                  </text>
                )}
              </g>
            ),
        )}
        {/* what really happened (only when asked for) */}
        {actual.length > 0 && (
          <path
            d={path([start, ...actual.map((d) => d.stock)])}
            fill="none"
            stroke="var(--color-muted)"
            strokeWidth="1.5"
            strokeDasharray="2 4"
            strokeLinecap="round"
          />
        )}
        {actual.map(
          (d, i) =>
            d.shortage_requests > 0 && (
              <path key={`a-${d.date}`} d={`M${x(i + 1) - 4} ${y(0) - 4}l8 8m0-8l-8 8`} stroke="var(--color-act)" strokeWidth="1.5" strokeLinecap="round" />
            ),
        )}
        {/* expected stock */}
        <path d={path(line)} fill="none" stroke="var(--color-ink)" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
        <circle cx={x(0)} cy={y(start)} r="3.5" fill="var(--color-ink)" />
        {/* the point where stock runs out */}
        {outIndex >= 0 && (
          <g>
            <circle cx={x(outIndex + 1)} cy={y(0)} r="5.5" fill="white" stroke="var(--color-act)" strokeWidth="2" />
            <text x={Math.min(x(outIndex + 1) + 9, width - pad.right - 52)} y={y(0) + 18} fontSize="12" fontWeight="500" fill="var(--color-act)">
              {t.detail.chartOut}
            </text>
          </g>
        )}
        {/* direct label on the line, not a legend */}
        {start > top * 0.25 ? (
          <text x={x(0) + 10} y={Math.max(pad.top + 4, y(start) - 10)} fontSize="12" fontWeight="500" fill="var(--color-ink)">
            {t.detail.chartLine}
          </text>
        ) : (
          <text x={width - pad.right} y={Math.min(lastY - 10, y(top * 0.3))} textAnchor="end" fontSize="12" fontWeight="500" fill="var(--color-ink)">
            {t.detail.chartLine}
          </text>
        )}
        {/* days in words */}
        {days.map(
          (d, i) =>
            i % every === 0 && (
              <text key={`x-${d.date}`} x={x(i) + innerW / days.length / 2} y={height - 8} textAnchor="middle" fontSize="11" fill="var(--color-body)">
                {d.label.replace(/ [A-Z][a-z]+$/, '')}
              </text>
            ),
        )}
      </svg>
      <p className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-[0.8125rem] text-muted">
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-4 rounded-sm bg-sky-soft" aria-hidden="true" />
          {t.detail.chartBand}
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block h-3 border-l border-dashed border-ink/60" aria-hidden="true" />
          {t.detail.chartDelivery}
        </span>
        {actual.length > 0 && (
          <span className="inline-flex items-center gap-1.5">
            <span className="inline-block w-4 border-t-2 border-dotted border-muted" aria-hidden="true" />
            {t.detail.chartActual}
          </span>
        )}
      </p>
    </div>
  )
}
