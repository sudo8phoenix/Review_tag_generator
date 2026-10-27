export type Connection = { apiPort: number; webPort: number }
export const defaultConnection: Connection = { apiPort: 8000, webPort: 5173 }

export class LocalServiceError extends Error {
  constructor(public status: number, message: string) { super(message); this.name = 'LocalServiceError' }
}

export function validConnection(value: unknown): value is Connection {
  if (!value || typeof value !== 'object') return false
  const record = value as Connection
  return [record.apiPort, record.webPort].every(port => Number.isInteger(port) && port >= 1 && port <= 65535)
}

export async function localRequest<T>(connection: Connection, path: string, body?: unknown, key?: string, signal?: AbortSignal): Promise<T> {
  if (!validConnection(connection) || !path.startsWith('/api/')) throw new Error('Invalid local service configuration.')
  const controller = new AbortController()
  const abort = () => controller.abort()
  if (signal?.aborted) controller.abort()
  signal?.addEventListener('abort', abort, { once: true })
  const timeout = window.setTimeout(abort, 15000)
  try {
    const response = await fetch(`http://127.0.0.1:${connection.apiPort}${path}`, {
      signal: controller.signal,
      ...(body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json', ...(key ? { 'Idempotency-Key': key } : {}) }, body: JSON.stringify(body) }),
    })
    const value = await response.json().catch(() => ({}))
    if (!response.ok) throw new LocalServiceError(response.status, typeof value.detail === 'string' ? value.detail : `Local service returned ${response.status}. Check the captured text and try again.`)
    return value as T
  } finally {
    window.clearTimeout(timeout)
    signal?.removeEventListener('abort', abort)
  }
}
