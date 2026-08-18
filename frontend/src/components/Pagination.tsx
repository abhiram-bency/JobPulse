interface Props {
  page: number
  pageSize: number
  total: number
  onPageChange: (page: number) => void
}

export default function Pagination({ page, pageSize, total, onPageChange }: Props) {
  const pages = Math.max(1, Math.ceil(total / pageSize))
  const canPrev = page > 1
  const canNext = page < pages

  return (
    <div className="pagination">
      <button
        type="button"
        className="pagination__button"
        disabled={!canPrev}
        onClick={() => onPageChange(page - 1)}
      >
        Previous
      </button>
      <span className="pagination__info">
        Page {page} of {pages} · {total} jobs
      </span>
      <button
        type="button"
        className="pagination__button"
        disabled={!canNext}
        onClick={() => onPageChange(page + 1)}
      >
        Next
      </button>
    </div>
  )
}