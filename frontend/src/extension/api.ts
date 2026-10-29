export type ConnectionMode = 'vercel' | 'local'

export type Connection = {
  mode?: ConnectionMode
  baseUrl?: string
  apiPort?: number
  webPort?: number
}

export const defaultVercelUrl = 'https://review-tag-generator.vercel.app'

export const defaultConnection: Connection = {
  mode: 'vercel',
  baseUrl: defaultVercelUrl,
  apiPort: 8000,
  webPort: 5173,
}

export class LocalServiceError extends Error {
  constructor(public status: number, message: string) { super(message); this.name = 'LocalServiceError' }
}

export function isValidUrl(url: string): boolean {
  try {
    const parsed = new URL(url)
    return !parsed.username && !parsed.password && !parsed.search && !parsed.hash &&
      (parsed.pathname === '/' || parsed.pathname === '') &&
      (parsed.protocol === 'https:' && (parsed.hostname.endsWith('.vercel.app') || parsed.hostname.endsWith('.onrender.com')) ||
        parsed.protocol === 'http:' && parsed.hostname === '127.0.0.1')
  } catch {
    return false
  }
}

export function validConnection(value: unknown): value is Connection {
  if (!value || typeof value !== 'object') return false
  const record = value as Connection
  if (record.mode !== undefined && !['vercel', 'local'].includes(record.mode)) return false
  const portsValid = [record.apiPort ?? 8000, record.webPort ?? 5173].every(
    port => Number.isInteger(port) && port >= 1 && port <= 65535
  )
  if (!portsValid) return false
  if (record.mode === 'vercel' || (record.baseUrl && record.mode !== 'local')) {
    return !record.baseUrl || isValidUrl(record.baseUrl)
  }
  return true
}

export function getApiBaseUrl(connection: Connection): string {
  if (connection.mode === 'vercel' || (connection.baseUrl && connection.mode !== 'local')) {
    return (connection.baseUrl || defaultVercelUrl).trim().replace(/\/+$/, '')
  }
  return `http://127.0.0.1:${connection.apiPort ?? 8000}`
}

export function getWebUrl(connection: Connection): string {
  if (connection.mode === 'vercel' || (connection.baseUrl && connection.mode !== 'local')) {
    return (connection.baseUrl || defaultVercelUrl).trim().replace(/\/+$/, '')
  }
  return `http://127.0.0.1:${connection.webPort ?? 5173}`
}

export async function localRequest<T>(
  connection: Connection,
  path: string,
  body?: unknown,
  key?: string,
  signal?: AbortSignal
): Promise<T> {
  if (!validConnection(connection) || !path.startsWith('/api/')) throw new Error('Invalid service configuration.')
  const controller = new AbortController()
  const abort = () => controller.abort()
  if (signal?.aborted) controller.abort()
  signal?.addEventListener('abort', abort, { once: true })
  const timeout = window.setTimeout(abort, 30000)
  const base = getApiBaseUrl(connection)
  try {
    const response = await fetch(`${base}${path}`, {
      signal: controller.signal,
      ...(body === undefined
        ? {}
        : {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              ...(key ? { 'Idempotency-Key': key } : {}),
            },
            body: JSON.stringify(body),
          }),
    })
    const contentType = response.headers.get('content-type') ?? ''
    if (!contentType.includes('application/json')) {
      throw new LocalServiceError(response.status, 'The API is not ready or its URL is incorrect. Wait for the backend to wake up, then retry.')
    }
    const value = await response.json()
    if (!response.ok) {
      throw new LocalServiceError(
        response.status,
        typeof value.detail === 'string'
          ? value.detail
          : `Service returned ${response.status}. Check the captured text and try again.`
      )
    }
    return value as T
  } finally {
    window.clearTimeout(timeout)
    signal?.removeEventListener('abort', abort)
  }
}
