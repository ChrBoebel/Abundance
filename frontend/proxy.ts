/** Apply an optimistic session check before protected routes are rendered. */
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
import { getIronSession } from 'iron-session'
import type { SessionData } from './lib/types'
import { getSessionOptions } from './lib/session'

function buildContentSecurityPolicy(nonce: string): string {
  const isDevelopment = process.env.NODE_ENV === 'development'
  return [
    "default-src 'self'",
    `script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${isDevelopment ? " 'unsafe-eval'" : ''}`,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self' data:",
    "connect-src 'self'",
    "worker-src 'self' blob:",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    ...(isDevelopment ? [] : ['upgrade-insecure-requests']),
  ].join('; ')
}

function secureResponse(response: NextResponse, policy: string): NextResponse {
  response.headers.set('Content-Security-Policy', policy)
  return response
}

export async function proxy(request: NextRequest) {
  const nonce = Buffer.from(crypto.randomUUID()).toString('base64')
  const policy = buildContentSecurityPolicy(nonce)
  const requestHeaders = new Headers(request.headers)
  requestHeaders.set('x-nonce', nonce)
  requestHeaders.set('Content-Security-Policy', policy)

  const response = NextResponse.next({
    request: { headers: requestHeaders },
  })

  const publicPaths = new Set(['/login', '/api/auth/login', '/api/health'])
  const isPublicPath = publicPaths.has(request.nextUrl.pathname)

  if (isPublicPath) {
    return secureResponse(response, policy)
  }

  const session = await getIronSession<SessionData>(request, response, getSessionOptions())

  if (!session.authenticated) {
    if (request.nextUrl.pathname.startsWith('/api/')) {
      return secureResponse(
        NextResponse.json({ error: 'Unauthorized' }, { status: 401 }),
        policy,
      )
    }
    return secureResponse(NextResponse.redirect(new URL('/login', request.url)), policy)
  }

  return secureResponse(response, policy)
}

export const config = {
  matcher: [
    '/((?!_next/static|_next/image|favicon.ico|abundance-mark.svg).*)',
  ],
}
