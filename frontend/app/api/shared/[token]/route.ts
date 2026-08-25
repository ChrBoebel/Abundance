/** Public capability endpoint for one explicitly shared research report. */

import { backendRequest, safeUpstreamStatus } from '@/lib/backend'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

const SHARE_TOKEN = /^[A-Za-z0-9_-]{32,100}$/

export async function GET(_request: Request, context: { params: Promise<{ token: string }> }) {
  const { token } = await context.params
  if (!SHARE_TOKEN.test(token)) return Response.json({ error: 'Shared research not found' }, { status: 404 })
  try {
    const upstream = await backendRequest(`/api/v1/shared/${token}`, {}, { public: true })
    if (!upstream.ok) {
      return Response.json({ error: 'Shared research not found' }, { status: safeUpstreamStatus(upstream.status) })
    }
    return Response.json(await upstream.json(), {
      headers: {
        'Cache-Control': 'private, no-store',
        'X-Robots-Tag': 'noindex, nofollow, noarchive',
      },
    })
  } catch {
    return Response.json({ error: 'Shared research is unavailable' }, { status: 502 })
  }
}
