import { useCallback, useEffect, useState } from 'react'
import type { Health, Job, JobFilters, Paginated, Source, SyncRun } from './api'
import { fetchHealth, fetchJobs, fetchSources, runSync } from './api'
import Filters from './components/Filters'
import JobCard from './components/JobCard'
import KpiCard from './components/KpiCard'
import Pagination from './components/Pagination'
import SourceBanner from './components/SourceBanner'
import SyncButton from './components/SyncButton'
import SyncProgress, { type SyncPhase } from './components/SyncProgress'
import { timeAgo } from './time'

const PAGE_SIZE = 20

function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [sources, setSources] = useState<Source[]>([])
  const [jobs, setJobs] = useState<Paginated<Job> | null>(null)
  const [page, setPage] = useState(1)
  const [filters, setFilters] = useState<JobFilters>({})
  const [jobsError, setJobsError] = useState<string | null>(null)

  const [syncPhase, setSyncPhase] = useState<SyncPhase>('idle')
  const [syncStep, setSyncStep] = useState(0)
  const [syncResult, setSyncResult] = useState<SyncRun | null>(null)
  const [syncError, setSyncError] = useState<string | null>(null)

  const refreshAll = useCallback(async () => {
    try {
      const [h, s] = await Promise.all([fetchHealth(), fetchSources()])
      setHealth(h)
      setSources(s)
    } catch {
      setJobsError('Could not load source health.')
    }
  }, [])

  const loadJobs = useCallback(
    async (targetPage: number, nextFilters: JobFilters) => {
      setJobsError(null)
      try {
        const result = await fetchJobs({
          page: targetPage,
          page_size: PAGE_SIZE,
          filters: nextFilters,
        })
        setJobs(result)
        setPage(result.page)
      } catch (err) {
        setJobsError(err instanceof Error ? err.message : 'Could not load jobs.')
        setJobs(null)
      }
    },
    [],
  )

  useEffect(() => {
    void refreshAll()
  }, [refreshAll])

  useEffect(() => {
    void loadJobs(page, filters)
  }, [loadJobs, page, filters])

  const changeFilters = (next: JobFilters) => {
    setFilters(next)
    setPage(1)
  }

  const source = sources[0] ?? null

  const handleRunSync = async () => {
    setSyncPhase('running')
    setSyncStep(0)
    setSyncResult(null)
    setSyncError(null)

    const advanceTimer = window.setInterval(() => {
      setSyncStep((step) => Math.min(step + 1, 3))
    }, 550)

    try {
      const result = await runSync(source?.id)
      setSyncResult(result)
      setSyncPhase(result.status === 'success' ? 'success' : result.status === 'suspicious' ? 'suspicious' : 'failed')
      setSyncError(result.error_message)
      await refreshAll()
      await loadJobs(page, filters)
    } catch (err) {
      setSyncPhase('failed')
      setSyncError(err instanceof Error ? err.message : 'Sync failed.')
    } finally {
      window.clearInterval(advanceTimer)
    }
  }

  const buttonState =
    syncPhase === 'running' ? 'running' : syncPhase === 'success' ? 'success' : syncPhase === 'failed' ? 'failed' : 'idle'

  const healthBanner =
    source && source.health !== 'healthy' ? (
      <div className={`notice notice--${source.health}`} role="status">
        <strong>Source {source.health === 'failed' ? 'unavailable' : 'degraded'}</strong>
        <span>
          The latest sync could not retrieve fresh jobs. Last successful sync:{' '}
          {timeAgo(source.last_success_at)}. Existing listings are still available.
        </span>
      </div>
    ) : null

  const jobList = jobs && jobs.items.length > 0 ? (
    <>
      <div className="job-list">
        {jobs.items.map((job) => (
          <JobCard key={job.id} job={job} />
        ))}
      </div>
      <Pagination
        page={jobs.page}
        pageSize={jobs.page_size}
        total={jobs.total}
        onPageChange={(next) => void loadJobs(next, filters)}
      />
    </>
  ) : jobsError ? (
    <div className="empty-state" role="alert">
      <p className="empty-state__title">Could not load jobs</p>
      <p className="empty-state__text">{jobsError}</p>
    </div>
  ) : jobs ? (
    <div className="empty-state">
      <p className="empty-state__title">No jobs available</p>
      <p className="empty-state__text">
        The source has not returned any valid listings yet.
      </p>
    </div>
  ) : (
    <div className="empty-state">
      <p className="empty-state__text">Loading jobs…</p>
    </div>
  )

  return (
    <div className="page">
      <header className="header">
        <div className="header__brand">
          <h1 className="header__title">JobPulse</h1>
          <p className="header__subtitle">Job ingestion dashboard</p>
        </div>
        <SyncButton state={buttonState} disabled={!source?.enabled} onClick={() => void handleRunSync()} />
      </header>

      <main className="main">
        {healthBanner}
        <SourceBanner source={source} />

        <SyncProgress phase={syncPhase} step={syncStep} result={syncResult} error={syncError} />

        <section className="kpi-grid" aria-label="Ingestion statistics">
          <KpiCard label="Jobs" value={source?.job_count ?? 0} hint="in database" />
          <KpiCard
            label="New"
            value={source?.last_sync?.jobs_created ?? 0}
            hint="last sync"
          />
          <KpiCard
            label="Updated"
            value={source?.last_sync?.jobs_updated ?? 0}
            hint="last sync"
          />
          <KpiCard
            label="Last Sync"
            value={timeAgo(source?.last_sync?.completed_at ?? null)}
            hint={
              source?.last_sync?.status === 'suspicious'
                ? 'completed with warnings'
                : source?.last_sync?.status === 'failed'
                  ? 'sync failed'
                  : undefined
            }
          />
        </section>

        <Filters
          filters={filters}
          onChange={changeFilters}
          onClear={() => changeFilters({})}
        />

        {jobList}
      </main>

      <footer className="footer">
        {health ? (
          <span>
            {health.app} v{health.version} · database {health.database}
          </span>
        ) : null}
      </footer>
    </div>
  )
}

export default App