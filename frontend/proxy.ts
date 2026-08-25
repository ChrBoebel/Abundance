/** Apply an optimistic session check before protected routes are rendered. */
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
import { getIronSession } from 'iron-session'
import type { SessionData } from './lib/types'
import { getSessionOptions } from './lib/session'

export async function proxy(request: NextRequest) {
  const response = NextResponse.next()

  const publicPaths = ['/login', '/api/auth/login', '/api/health']
  const isPublicPath = publicPaths.some(path => request.nextUrl.pathname.startsWith(path))

  if (isPublicPath) {
    return response
  }

  const session = await getIronSession<SessionData>(request, response, getSessionOptions())

  if (!session.authenticated) {
    return NextResponse.redirect(new URL('/login', request.url))
  }

  return response
}

export const config = {
  matcher: [
    '/((?!_next/static|_next/image|favicon.ico|abundance-mark.svg).*)',
  ],
}
