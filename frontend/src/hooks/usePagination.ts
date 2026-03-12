import { useState, useCallback } from 'react'

export function usePagination(initialPage = 1, pageSize = 15) {
  const [page, setPage] = useState(initialPage)
  const [total, setTotal] = useState(0)

  const goToPage = useCallback((newPage: number) => {
    setPage(Math.max(1, Math.min(newPage, Math.ceil(total / pageSize))))
  }, [total, pageSize])

  const nextPage = useCallback(() => {
    goToPage(page + 1)
  }, [page, goToPage])

  const prevPage = useCallback(() => {
    goToPage(page - 1)
  }, [page, goToPage])

  const reset = useCallback(() => {
    setPage(initialPage)
  }, [initialPage])

  const totalPages = Math.ceil(total / pageSize)
  const hasNextPage = page < totalPages
  const hasPrevPage = page > 1

  return {
    page,
    pageSize,
    total,
    setTotal,
    totalPages,
    goToPage,
    nextPage,
    prevPage,
    reset,
    hasNextPage,
    hasPrevPage,
  }
}
