import type { SyncRun } from '../api'

const STEPS = ['Fetching source', 'Parsing jobs', 'Validating records', 'Saving jobs']

export type SyncPhase = 'running' | 'success' | 'failed' | 'suspicious' | 'idle'

interface Props {
  phase: SyncPhase
  step: number
  result: SyncRun | null
  error: string | null
}

function StepList({ step }: { step: number }) {
  return (
    <ol className="sync-steps">
      {STEPS.map((label, index) => (
        <li
          key={label}
          className={
            index < step
              ? 'sync-step sync-step--done'
              : index === step
                ? 'sync-step sync-step--active'
                : 'sync-step'
          }
        >
          {index < step ? '✓' : index === step ? <span className="spinner spinner--sm" /> : '•'}{' '}
          {label}
        </li>
      ))}
    </ol>
  )
}

export default function SyncProgress({ phase, step, result, error }: Props) {
  if (phase === 'idle') return null
  if (phase === 'running') {
    return (
      <div className="sync-panel" role="status" aria-live="polite">
        <p className="sync-panel__heading">Syncing…</p>
        <StepList step={step} />
      </div>
    )
  }
  if (phase === 'failed') {
    return (
      <div className="sync-panel sync-panel--failed" role="alert">
        <p className="sync-panel__heading">⚠ Sync failed</p>
        <p className="sync-panel__message">{error || 'The source could not be reached.'}</p>
        <p className="sync-panel__note">
          Existing job data has been preserved. Retries follow the configured backoff policy.
        </p>
      </div>
    )
  }
  if (phase === 'suspicious') {
    return (
      <div className="sync-panel sync-panel--warning" role="status" aria-live="polite">
        <p className="sync-panel__heading">⚠ Sync completed with warnings</p>
        <p className="sync-panel__message">{error}</p>
        <p className="sync-panel__note">Existing job data has been preserved.</p>
      </div>
    )
  }
  // success
  return (
    <div className="sync-panel sync-panel--success" role="status" aria-live="polite">
      <p className="sync-panel__heading">✓ Sync completed</p>
      <div className="sync-stats">
        <div className="sync-stat">
          <span className="sync-stat__value">{result?.jobs_found ?? 0}</span>
          <span className="sync-stat__label">found</span>
        </div>
        <div className="sync-stat">
          <span className="sync-stat__value sync-stat__value--accent">
            {result?.jobs_created ?? 0}
          </span>
          <span className="sync-stat__label">new</span>
        </div>
        <div className="sync-stat">
          <span className="sync-stat__value">{result?.jobs_updated ?? 0}</span>
          <span className="sync-stat__label">updated</span>
        </div>
        <div className="sync-stat">
          <span className="sync-stat__value">{result?.jobs_skipped ?? 0}</span>
          <span className="sync-stat__label">unchanged</span>
        </div>
      </div>
    </div>
  )
}