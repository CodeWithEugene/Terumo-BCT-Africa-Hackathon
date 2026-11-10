import type { ReactNode } from 'react'
import { Icon } from './Icon'

/** A simple rack outline, drawn in the hairline colour. Used for quiet states. */
export function RackArt({ filled = 0 }: { filled?: number }) {
  return (
    <svg width="132" height="72" viewBox="0 0 132 72" fill="none" aria-hidden="true">
      <path d="M6 58h120M14 58V26M118 58V26M6 26h120" stroke="var(--color-line)" strokeWidth="2" strokeLinecap="round" />
      {Array.from({ length: 8 }, (_, i) => (
        <g key={i}>
          <rect x={20 + i * 12} y="12" width="8" height="40" rx="4" stroke="#c9ced6" strokeWidth="1.5" fill="white" />
          <rect
            x={21.5 + i * 12}
            y={i < filled ? 28 : 50}
            width="5"
            height={i < filled ? 22.5 : 0.5}
            rx="2.5"
            fill="var(--color-sky)"
          />
        </g>
      ))}
    </svg>
  )
}

export function QuietState({ title, text, art, action }: { title: string; text: string; art?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-start gap-4 rounded-card border border-line px-5 py-8 sm:flex-row sm:items-center sm:gap-8 sm:px-8">
      {art ?? <RackArt filled={8} />}
      <div>
        <p className="text-lg font-semibold text-ink">{title}</p>
        <p className="mt-1 max-w-[52ch]">{text}</p>
        {action && <div className="mt-4">{action}</div>}
      </div>
    </div>
  )
}

export function Banner({ icon = 'offline', children, action }: { icon?: string; children: ReactNode; action?: ReactNode }) {
  return (
    <div
      role="status"
      className="mb-6 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-card border border-[#f1dfb4] bg-watch-soft px-4 py-3 text-sm text-ink"
    >
      <span className="text-watch">
        <Icon name={icon} />
      </span>
      <p className="min-w-0 flex-1">{children}</p>
      {action}
    </div>
  )
}

export function Button({
  variant = 'primary',
  icon,
  children,
  className = '',
  ...rest
}: {
  variant?: 'primary' | 'sky' | 'outline' | 'text'
  icon?: string
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  const look = {
    primary: 'bg-primary text-white hover:bg-[#0e1338] border border-primary',
    sky: 'bg-sky text-ink hover:bg-[#5db9e0] border border-sky',
    outline: 'bg-white text-ink border border-ink/30 hover:border-ink',
    text: 'text-ink underline-offset-4 hover:underline border border-transparent',
  }[variant]
  return (
    <button
      type="button"
      className={`inline-flex min-h-11 items-center justify-center gap-2 rounded-control px-4 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${look} ${className}`}
      {...rest}
    >
      {icon && <Icon name={icon} size={18} />}
      {children}
    </button>
  )
}
