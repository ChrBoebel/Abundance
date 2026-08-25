/** Authenticated access to persisted research history. */

import { isAuthenticated } from '@/lib/auth'
import { backendRequest, safeUpstreamStatus } from '@/lib/backend'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

export async function GET() {
  if (!(await isAuthenticated())) {
    return Response.json({ error: 'Unauthorized' }, { status: 401 })
  }
  try {
    const upstream = await backendRequest('/api/v1/research-runs?limit=50')
    if (!upstream.ok) {
      return Response.json({ error: 'Research history is unavailable' }, { status: safeUpstreamStatus(upstream.status) })
    }
    return Response.json(await upstream.json())
  } catch {
    return Response.json({ error: 'Research history is unavailable' }, { status: 502 })
  }
}
