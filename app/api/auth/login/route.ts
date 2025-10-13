/**
 * Login API Route with Rate Limiting
 */
import { NextRequest, NextResponse } from 'next/server'
import { authenticate } from '@/lib/auth'
import { loginRateLimiter } from '@/lib/rate-limit'

function getClientIdentifier(request: NextRequest): string {
  // Try to get real IP from various headers (Railway/proxy headers)
  const forwardedFor = request.headers.get('x-forwarded-for')
  const realIp = request.headers.get('x-real-ip')
  const railwayIp = request.headers.get('x-railway-client-ip')

  // Use the first available IP
  const ip = railwayIp || realIp || forwardedFor?.split(',')[0] || 'unknown'

  return ip.trim()
}

export async function POST(request: NextRequest) {
  try {
    const identifier = getClientIdentifier(request)

    // Check rate limit
    if (loginRateLimiter.isLimited(identifier)) {
      const blockedUntil = loginRateLimiter.getBlockedUntil(identifier)
      const remainingMs = blockedUntil || 0
      const remainingMinutes = Math.ceil(remainingMs / 60000)

      return NextResponse.json(
        {
          error: `Zu viele Versuche. Bitte versuchen Sie es in ${remainingMinutes} Minute(n) erneut.`,
          retryAfter: remainingMs
        },
        {
          status: 429,
          headers: {
            'Retry-After': String(Math.ceil(remainingMs / 1000))
          }
        }
      )
    }

    const { password } = await request.json()

    if (!password) {
      return NextResponse.json(
        { error: 'Password required' },
        { status: 400 }
      )
    }

    const success = await authenticate(password)

    if (success) {
      // Reset rate limit on successful login
      loginRateLimiter.reset(identifier)
      return NextResponse.json({ success: true })
    } else {
      // Record failed attempt
      loginRateLimiter.recordAttempt(identifier)

      const remaining = loginRateLimiter.getRemainingAttempts(identifier)
      const errorMsg = remaining > 0
        ? `Falsches Passwort. Noch ${remaining} Versuch(e) übrig.`
        : 'Zu viele fehlgeschlagene Versuche.'

      return NextResponse.json(
        {
          error: errorMsg,
          remainingAttempts: remaining
        },
        { status: 401 }
      )
    }
  } catch (error) {
    console.error('Login error:', error)
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}
