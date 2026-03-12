/**
 * Route protection middleware
 */
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
import { getIronSession } from 'iron-session'
import type { SessionData } from './lib/types'
import { getSessionOptions } from './lib/session'

export async function middleware(request: NextRequest) {
  const response = NextResponse.next()

  // Public routes
  const publicPaths = ['/login', '/api/auth/login', '/api/health']
  const isPublicPath = publicPaths.some(path => request.nextUrl.pathname.startsWith(path))

  if (isPublicPath) {
    return response
  }

  // Check authentication
  const session = await getIronSession<SessionData>(request, response, getSessionOptions())

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
