import { useState } from 'react'

export type SyncButtonState = 'idle' | 'running' | 'success' | 'failed'

interface Props {
  state: SyncButtonState
  disabled?: boolean
  onClick: () => void
}

export default function SyncButton({ state, disabled, onClick }: Props) {
  const [bounce, setBounce] = useState(false)
  const className = `sync-button sync-button--${state}${bounce ? ' sync-button--pop' : ''}`

  const handleClick = () => {
    if (state === 'running') return
    setBounce(true)
    window.setTimeout(() => setBounce(false), 350)
    onClick()
  }

  const content =
    state === 'running' ? (
      <>
        <span className="spinner" aria-hidden="true" />
        Syncing…
      </>
    ) : state === 'success' ? (
      <>✓ Synced</>
    ) : state === 'failed' ? (
      <>⚠ Retry</>
    ) : (
      <>Run Sync</>
    )

  return (
    <button
      type="button"
      className={className}
      onClick={handleClick}
      disabled={disabled || state === 'running'}
      aria-live="polite"
    >
      {content}
    </button>
  )
}