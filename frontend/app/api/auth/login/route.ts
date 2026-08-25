/** Password login with origin, size, and distributed rate-limit checks. */
import { NextRequest, NextResponse } from 'next/server'
import { authenticate } from '@/lib/auth'
import { checkRateLimit, resetRateLimit } from '@/lib/rate-limit'
import { clientRateLimitKey, isSameOriginRequest } from '@/lib/request-security'

export async function POST(request: NextRequest) {
  try {
    if (!isSameOriginRequest(request)) {
      return NextResponse.json({ error: 'Cross-site request rejected' }, { status: 403 })
    }
    const contentLength = Number(request.headers.get('content-length') || '0')
    if (contentLength > 4_096) {
      return NextResponse.json({ error: 'Request body is too large' }, { status: 413 })
    }
    const identifier = clientRateLimitKey(request)
    const limit = await checkRateLimit('login', identifier)
    if (limit.reason === 'configuration') {
      return NextResponse.json({ error: 'Authentication service unavailable' }, { status: 503 })
    }
    if (!limit.success) {
      const retryAfterSeconds = Math.max(1, Math.ceil((limit.reset - Date.now()) / 1_000))
      return NextResponse.json(
        { error: 'Zu viele Versuche. Bitte später erneut versuchen.' },
        {
          status: 429,
          headers: { 'Retry-After': String(retryAfterSeconds) },
        },
      )
    }

    const body = await request.json() as Record<string, unknown>
    const password = body.password
    if (typeof password !== 'string' || password.length < 1 || password.length > 1_024) {
      return NextResponse.json(
        { error: 'Invalid credentials' },
        { status: 400 },
      )
    }

    const success = await authenticate(password)
    if (success) {
      await resetRateLimit('login', identifier)
      return NextResponse.json({ success: true })
    }
    return NextResponse.json({ error: 'Invalid credentials' }, { status: 401 })
  } catch {
    console.error('Login request failed')
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 },
    )
  }
}
