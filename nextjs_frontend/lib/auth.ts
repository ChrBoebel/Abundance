/**
 * Authentication utilities using iron-session
 */
import { getIronSession } from 'iron-session'
import { cookies } from 'next/headers'
import type { SessionData } from './types'

const sessionOptions = {
  password: process.env.SESSION_SECRET || 'complex_password_at_least_32_characters_long_for_security',
  cookieName: 'abundance_session',
  cookieOptions: {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax' as const,
    maxAge: 60 * 60 * 24 * 7, // 1 week
  },
}

export async function getSession() {
  const cookieStore = await cookies()
  return getIronSession<SessionData>(cookieStore, sessionOptions)
}

export async function isAuthenticated(): Promise<boolean> {
  const session = await getSession()
  return session.authenticated === true
}

export async function authenticate(password: string): Promise<boolean> {
  const correctPassword = process.env.APP_PASSWORD || 'changeme'

  if (password === correctPassword) {
    const session = await getSession()
    session.authenticated = true
    await session.save()
    return true
  }

  return false
}

export async function logout(): Promise<void> {
  const session = await getSession()
  session.destroy()
}
