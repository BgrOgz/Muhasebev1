import { RiskLevel } from '../types'

interface Props {
  level?: RiskLevel
  size?: 'sm' | 'md'
}

const LABELS: Record<string, string> = {
  low: '🟢 Düşük',
  medium: '🟡 Orta',
  high: '🔴 Yüksek',
}

const CLASSES: Record<string, string> = {
  low: 'badge-low',
  medium: 'badge-medium',
  high: 'badge-high',
}

export function RiskBadge({ level, size = 'md' }: Props) {
  const key = level ?? 'medium'
  return (
    <span className={`${CLASSES[key]} ${size === 'sm' ? 'text-xs px-2 py-0.5' : ''}`}>
      {LABELS[key] ?? key}
    </span>
  )
}
