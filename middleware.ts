1/**
 * Route protection middleware
 */
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
import { getIronSession } from 'iron-session'
import type { SessionData } from './lib/types'

const sessionOptions = {
  password: process.env.SESSION_SECRET || 'complex_password_at_least_32_characters_long_for_security',
  cookieName: 'abundance_session',
  cookieOptions: {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax' as const,
    maxAge: 60 * 60 * 24 * 7,
  },
}

export async function middleware(request: NextRequest) {
  const response = NextResponse.next()

  // Public routes
  const publicPaths = ['/login', '/api/auth/login', '/api/health']
  const isPublicPath = publicPaths.some(path => request.nextUrl.pathname.startsWith(path))

  if (isPublicPath) {
    return response
  }

  // Check authentication
  const session = await getIronSession<SessionData>(request, response, sessionOptions)

  if (!session.authenticated) {
    return NextResponse.redirect(new URL('/login', request.url))
  }

  return response
}

export const config = {
  matcher: [
    '/((?!_next/static|_next/image|favicon.ico|bergbild2.svg).*)',
  ],
}
