import type { JobFilters } from '../api'

interface Props {
  filters: JobFilters
  onChange: (filters: JobFilters) => void
  onClear: () => void
}

const hasAnyFilter = (filters: JobFilters) =>
  Boolean(filters.search?.trim() || filters.location?.trim() || filters.company?.trim())

export default function Filters({ filters, onChange, onClear }: Props) {
  const update = (key: keyof JobFilters, value: string) => onChange({ ...filters, [key]: value })

  return (
    <div className="filters">
      <input
        type="search"
        className="filter-input"
        placeholder="Search jobs…"
        value={filters.search ?? ''}
        onChange={(e) => update('search', e.target.value)}
        aria-label="Search jobs"
      />
      <input
        type="text"
        className="filter-input"
        placeholder="Location (e.g. Remote)"
        value={filters.location ?? ''}
        onChange={(e) => update('location', e.target.value)}
        aria-label="Filter by location"
      />
      <input
        type="text"
        className="filter-input"
        placeholder="Company"
        value={filters.company ?? ''}
        onChange={(e) => update('company', e.target.value)}
        aria-label="Filter by company"
      />
      {hasAnyFilter(filters) ? (
        <button type="button" className="filter-clear" onClick={onClear}>
          Clear
        </button>
      ) : null}
    </div>
  )
}