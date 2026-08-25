/** Server-only access to the internal Abundance research API. */

import 'server-only'

const BACKEND_URL = process.env.RESEARCH_BACKEND_URL || 'http://localhost:8000'

export async function backendRequest(
  path: string,
  init: RequestInit = {},
  options: { public?: boolean } = {},
): Promise<Response> {
  if (!path.startsWith('/api/v1/')) throw new Error('Invalid backend path')
  const token = process.env.RESEARCH_BACKEND_TOKEN
  if (process.env.NODE_ENV === 'production' && !options.public && !token) {
    throw new Error('RESEARCH_BACKEND_TOKEN is required in production')
  }
  const headers = new Headers(init.headers)
  headers.set('Accept', 'application/json')
  if (init.body) headers.set('Content-Type', 'application/json')
  if (!options.public && token) headers.set('Authorization', `Bearer ${token}`)
  return fetch(new URL(path, BACKEND_URL), {
    ...init,
    headers,
    cache: 'no-store',
    signal: init.signal || AbortSignal.timeout(15_000),
  })
}

export function safeUpstreamStatus(status: number): number {
  if (status === 400 || status === 401 || status === 403 || status === 404 || status === 422 || status === 429) {
    return status
  }
  return status >= 200 && status < 300 ? status : 502
}
