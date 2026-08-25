/** Request-origin and privacy-preserving client identity helpers. */

import { createHmac } from 'node:crypto'
import type { NextRequest } from 'next/server'

export function isSameOriginRequest(request: NextRequest): boolean {
  if (request.headers.get('sec-fetch-site') === 'cross-site') return false
  const origin = request.headers.get('origin')
  return !origin || origin === request.nextUrl.origin
}

export function clientRateLimitKey(request: NextRequest): string {
  const forwarded = request.headers.get('x-forwarded-for')?.split(',')[0]
  const candidate =
    request.headers.get('x-railway-client-ip') ||
    request.headers.get('x-real-ip') ||
    forwarded ||
    'unknown'
  const normalized = candidate.trim().slice(0, 100)
  const secret = process.env.RATE_LIMIT_KEY_SECRET || (
    process.env.NODE_ENV !== 'production' ? process.env.SESSION_SECRET : undefined
  )
  if (!secret) throw new Error('RATE_LIMIT_KEY_SECRET environment variable is required')
  return createHmac('sha256', secret).update(normalized).digest('hex')
}
