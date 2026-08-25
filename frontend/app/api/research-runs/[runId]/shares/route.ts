/** Create an unguessable capability link for a completed report. */

import type { NextRequest } from 'next/server'
import { isAuthenticated } from '@/lib/auth'
import { backendRequest, safeUpstreamStatus } from '@/lib/backend'
import { isSameOriginRequest } from '@/lib/request-security'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

const RUN_ID = /^run-[a-f0-9]{32}$/
const SHARE_TOKEN = /^[A-Za-z0-9_-]{32,100}$/

export async function POST(request: NextRequest, context: { params: Promise<{ runId: string }> }) {
  if (!(await isAuthenticated())) return Response.json({ error: 'Unauthorized' }, { status: 401 })
  if (!isSameOriginRequest(request)) return Response.json({ error: 'Cross-site request rejected' }, { status: 403 })
  const { runId } = await context.params
  if (!RUN_ID.test(runId)) return Response.json({ error: 'Research run not found' }, { status: 404 })
  try {
    const upstream = await backendRequest(`/api/v1/research-runs/${runId}/shares`, { method: 'POST' })
    if (!upstream.ok) {
      return Response.json({ error: 'Share link could not be created' }, { status: safeUpstreamStatus(upstream.status) })
    }
    const payload = await upstream.json() as { token?: unknown }
    if (typeof payload.token !== 'string' || !SHARE_TOKEN.test(payload.token)) throw new Error('Invalid share response')
    return Response.json({ token: payload.token, url: `/shared/${payload.token}` })
  } catch {
    return Response.json({ error: 'Share link could not be created' }, { status: 502 })
  }
}
