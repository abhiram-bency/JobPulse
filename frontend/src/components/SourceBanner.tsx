import type { Source } from '../api'
import { timeAgo } from '../time'

interface Props {
  source: Source | null
}

const HEALTH_LABEL: Record<string, string> = {
  healthy: 'Healthy',
  degraded: 'Degraded',
  failed: 'Failed',
}

export default function SourceBanner({ source }: Props) {
  if (!source) return null
  return (
    <div className="source-banner">
      <span className={`health-dot health-dot--${source.health}`} aria-hidden="true" />
      <div className="source-banner__text">
        <strong>{HEALTH_LABEL[source.health] ?? source.health}</strong>
        <span className="source-banner__name">{source.name}</span>
        <span className="source-banner__meta">
          Last sync: {timeAgo(source.last_sync?.completed_at ?? null)} ·{' '}
          {source.job_count} jobs
        </span>
      </div>
    </div>
  )
}