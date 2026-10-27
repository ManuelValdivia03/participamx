import { useEffect, useState } from 'react'

export function useTerritorialResource<T>(key: string | null, loader: (signal: AbortSignal) => Promise<T>) {
  const [attempt, setAttempt] = useState(0)
  const [result, setResult] = useState<{ key: string; status: 'ready'; data: T } | { key: string; status: 'error' } | null>(null)
  useEffect(() => {
    if (!key) return
    const controller = new AbortController()
    setResult(null)
    loader(controller.signal).then(data => {
      if (!controller.signal.aborted) setResult({ key, status: 'ready', data })
    }).catch(() => {
      if (!controller.signal.aborted) setResult({ key, status: 'error' })
    })
    return () => controller.abort()
  }, [key, loader, attempt])
  const active = result?.key === key ? result : null
  return { active, retry: () => setAttempt(value => value + 1) }
}
