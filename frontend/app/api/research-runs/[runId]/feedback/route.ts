/** Authenticated, same-origin feedback forwarding. */

import type { NextRequest } from 'next/server'
import { isAuthenticated } from '@/lib/auth'
import { backendRequest, safeUpstreamStatus } from '@/lib/backend'
import { isSameOriginRequest } from '@/lib/request-security'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

const RUN_ID = /^run-[a-f0-9]{32}$/

export async function POST(request: NextRequest, context: { params: Promise<{ runId: string }> }) {
  if (!(await isAuthenticated())) return Response.json({ error: 'Unauthorized' }, { status: 401 })
  if (!isSameOriginRequest(request)) return Response.json({ error: 'Cross-site request rejected' }, { status: 403 })
  const { runId } = await context.params
  if (!RUN_ID.test(runId)) return Response.json({ error: 'Research run not found' }, { status: 404 })
  const contentLength = Number(request.headers.get('content-length') || '0')
  if (contentLength > 3_000) return Response.json({ error: 'Request body is too large' }, { status: 413 })
  try {
    const value = await request.json() as Record<string, unknown>
    const claimId = typeof value.claim_id === 'string' ? value.claim_id : null
    const note = typeof value.note === 'string' ? value.note.trim() : null
    if (
      (value.rating !== -1 && value.rating !== 0 && value.rating !== 1) ||
      (claimId !== null && (claimId.length < 1 || claimId.length > 100)) ||
      (note !== null && note.length > 2_000)
    ) return Response.json({ error: 'Invalid feedback' }, { status: 422 })
    const upstream = await backendRequest(`/api/v1/research-runs/${runId}/feedback`, {
      method: 'POST',
      body: JSON.stringify({ run_id: runId, claim_id: claimId, rating: value.rating, note }),
    })
    if (!upstream.ok) {
      return Response.json({ error: 'Feedback could not be saved' }, { status: safeUpstreamStatus(upstream.status) })
    }
    return Response.json(await upstream.json())
  } catch {
    return Response.json({ error: 'Feedback could not be saved' }, { status: 502 })
  }
}
