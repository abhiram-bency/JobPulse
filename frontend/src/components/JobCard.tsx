import type { Job } from '../api'
import { timeAgo } from '../time'

interface Props {
  job: Job
}

export default function JobCard({ job }: Props) {
  return (
    <article className="job-card">
      <div className="job-card__main">
        <h3 className="job-card__title">{job.title}</h3>
        <div className="job-card__meta">
          {job.company ? <span className="job-card__company">{job.company}</span> : null}
          {job.location ? <span className="job-card__location">{job.location}</span> : null}
          <span className="job-card__published">Published {timeAgo(job.published_at)}</span>
        </div>
        {job.description ? (
          <p className="job-card__description">{job.description}</p>
        ) : null}
      </div>
      <a
        className="job-card__link"
        href={job.url}
        target="_blank"
        rel="noreferrer noopener"
      >
        View Job
      </a>
    </article>
  )
}