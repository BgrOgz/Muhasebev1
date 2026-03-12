import { useEffect, useState, useCallback } from 'react'

interface UseFetchOptions {
  retry?: number
  cacheTime?: number // ms
}

interface FetchData<T> {
  data: T | null
  error: Error | null
  isLoading: boolean
}

interface UseFetchState<T> extends FetchData<T> {
  refetch: () => void
}

const cache = new Map<string, { data: unknown; timestamp: number }>()

export function useFetch<T>(
  url: string | null,
  fetchFn: () => Promise<T>,
  options: UseFetchOptions = {}
): UseFetchState<T> {
  const { retry = 3, cacheTime = 5 * 60 * 1000 } = options // default 5 min cache
  const [state, setState] = useState<FetchData<T>>({
    data: null,
    error: null,
    isLoading: true,
  })

  const fetchData = useCallback(
    async (attemptsLeft: number = retry) => {
      if (!url) {
        setState({ data: null, error: null, isLoading: false })
        return
      }

      // Check cache
      const cached = cache.get(url)
      if (cached && Date.now() - cached.timestamp < cacheTime) {
        setState({
          data: cached.data as T,
          error: null,
          isLoading: false,
        })
        return
      }

      setState((s) => ({ ...s, isLoading: true }))

      try {
        const result = await fetchFn()

        // Cache result
        cache.set(url, { data: result, timestamp: Date.now() })

        setState({
          data: result,
          error: null,
          isLoading: false,
        })
      } catch (err) {
        const error = err instanceof Error ? err : new Error('Unknown error')

        if (attemptsLeft > 0) {
          // Exponential backoff
          const delay = 1000 * (retry - attemptsLeft + 1)
          setTimeout(() => fetchData(attemptsLeft - 1), delay)
        } else {
          setState({
            data: null,
            error,
            isLoading: false,
          })
        }
      }
    },
    [url, fetchFn, retry, cacheTime]
  )

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const refetch = useCallback(() => {
    if (url) {
      cache.delete(url)
      fetchData()
    }
  }, [url, fetchData])

  return { ...state, refetch }
}

// Clear cache manually
export function clearFetchCache(url?: string) {
  if (url) {
    cache.delete(url)
  } else {
    cache.clear()
  }
}
