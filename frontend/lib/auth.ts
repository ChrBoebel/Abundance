/**
 * Authentication utilities using iron-session
 */
import { getIronSession } from 'iron-session'
import { cookies } from 'next/headers'
import { createHash, timingSafeEqual } from 'crypto'
import type { SessionData } from './types'
import { getSessionOptions } from './session'

function requireAppPassword(): string {
  const value = process.env.APP_PASSWORD
  if (!value || value.length < 12) {
    throw new Error('APP_PASSWORD must contain at least 12 characters')
  }
  return value
}

export async function getSession() {
  const cookieStore = await cookies()
  return getIronSession<SessionData>(cookieStore, getSessionOptions())
}

export async function isAuthenticated(): Promise<boolean> {
  const session = await getSession()
  return session.authenticated === true
}

/**
 * Timing-safe password comparison to prevent timing attacks
 */
function comparePasswords(provided: string, correct: string): boolean {
  const providedDigest = createHash('sha256').update(provided, 'utf8').digest()
  const correctDigest = createHash('sha256').update(correct, 'utf8').digest()
  return timingSafeEqual(providedDigest, correctDigest)
}

export async function authenticate(password: string): Promise<boolean> {
  if (Buffer.byteLength(password, 'utf8') > 4_096) return false
  const correctPassword = requireAppPassword()

  // Use timing-safe comparison
  if (comparePasswords(password, correctPassword)) {
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
