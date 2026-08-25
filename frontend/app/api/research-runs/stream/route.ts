/** Authenticated, cancellation-aware research stream proxy. */
import { NextRequest } from 'next/server'
import { isAuthenticated } from '@/lib/auth'
import { checkRateLimit } from '@/lib/rate-limit'
import { clientRateLimitKey, isSameOriginRequest } from '@/lib/request-security'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

const BACKEND_URL = process.env.RESEARCH_BACKEND_URL || 'http://localhost:8000'
const ALLOWED_MODELS = new Set(['mercury', 'gemini-flash', 'gemini', 'deepseek', 'glm'])
const ALLOWED_MODES = new Set(['quick', 'balanced', 'thorough'])

export async function POST(request: NextRequest) {
  try {
    if (!(await isAuthenticated())) {
      return Response.json({ error: 'Unauthorized' }, { status: 401 })
    }
    if (!isSameOriginRequest(request)) {
      return Response.json({ error: 'Cross-site request rejected' }, { status: 403 })
    }

    const contentLength = Number(request.headers.get('content-length') || '0')
    if (contentLength > 12_000) {
      return Response.json({ error: 'Request body is too large' }, { status: 413 })
    }

    const payload = await request.json() as Record<string, unknown>
    const inquiry = typeof payload.inquiry === 'string' ? payload.inquiry.trim() : ''
    const model = typeof payload.model === 'string' ? payload.model : 'mercury'
    const mode = typeof payload.mode === 'string' ? payload.mode : 'balanced'
    if (inquiry.length < 3 || inquiry.length > 8_000) {
      return Response.json({ error: 'Invalid inquiry' }, { status: 422 })
    }
    if (!ALLOWED_MODELS.has(model) || !ALLOWED_MODES.has(mode)) {
      return Response.json({ error: 'Unsupported research configuration' }, { status: 422 })
    }
    const limit = await checkRateLimit('research', clientRateLimitKey(request))
    if (limit.reason === 'configuration') {
      return Response.json({ error: 'Research service is not configured' }, { status: 503 })
    }
    if (!limit.success) {
      const retryAfter = Math.max(1, Math.ceil((limit.reset - Date.now()) / 1_000))
      return Response.json(
        { error: 'Too many research requests' },
        { status: 429, headers: { 'Retry-After': String(retryAfter) } },
      )
    }

    const backendToken = process.env.RESEARCH_BACKEND_TOKEN
    if (process.env.NODE_ENV === 'production' && !backendToken) {
      return Response.json({ error: 'Research service is not configured' }, { status: 503 })
    }

    const upstream = await fetch(`${BACKEND_URL}/api/v1/research-runs/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(backendToken ? { Authorization: `Bearer ${backendToken}` } : {}),
      },
      body: JSON.stringify({ inquiry, model, mode }),
      cache: 'no-store',
      signal: request.signal,
    })
    if (!upstream.ok || !upstream.body) {
      return Response.json(
        { error: 'Research service is unavailable' },
        { status: upstream.status >= 400 && upstream.status < 500 ? upstream.status : 502 },
      )
    }

    const headers = new Headers({
      'Content-Type': 'text/event-stream; charset=utf-8',
      'Cache-Control': 'no-cache, no-transform',
      'Connection': 'keep-alive',
      'X-Accel-Buffering': 'no',
    })
    for (const name of ['x-request-id', 'x-run-id']) {
      const value = upstream.headers.get(name)
      if (value) headers.set(name, value)
    }
    return new Response(upstream.body, {
      status: 200,
      headers: {
        ...Object.fromEntries(headers.entries()),
      },
    })
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') {
      return new Response(null, { status: 499 })
    }
    console.error('Research stream proxy failed')
    return Response.json({ error: 'Research service is unavailable' }, { status: 502 })
  }
}
