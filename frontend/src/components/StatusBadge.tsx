import { t } from '../i18n/en'
import { cx } from '../lib/format'
import type { Status } from '../types'
import { Icon } from './Icon'

const tone: Record<Status, string> = {
  act: 'text-act',
  watch: 'text-watch',
  steady: 'text-steady',
  not_held: 'text-muted',
}

/** Status is always a word and an icon, never colour alone. */
export function StatusBadge({ status, className }: { status: Status; className?: string }) {
  return (
    <span className={cx('inline-flex items-center gap-1.5 text-sm font-medium', tone[status], className)}>
      <Icon name={status} size={16} />
      {t.status[status]}
    </span>
  )
}
