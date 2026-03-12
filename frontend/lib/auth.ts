/**
 * Authentication utilities using iron-session
 */
import { getIronSession } from 'iron-session'
import { cookies } from 'next/headers'
import { timingSafeEqual } from 'crypto'
import type { SessionData } from './types'
import { sessionOptions } from './session'

function requireAppPassword(): string {
  const value = process.env.APP_PASSWORD
  if (!value) {
    throw new Error('APP_PASSWORD environment variable is required')
  }
  return value
}

export async function getSession() {
  const cookieStore = await cookies()
  return getIronSession<SessionData>(cookieStore, sessionOptions)
}

export async function isAuthenticated(): Promise<boolean> {
  const session = await getSession()
  return session.authenticated === true
}

/**
 * Timing-safe password comparison to prevent timing attacks
 */
function comparePasswords(provided: string, correct: string): boolean {
  // Convert strings to buffers with fixed encoding
  const providedBuffer = Buffer.from(provided, 'utf8')
  const correctBuffer = Buffer.from(correct, 'utf8')

  // If lengths differ, still compare to prevent timing attacks
  // Pad shorter buffer with zeros
  const maxLength = Math.max(providedBuffer.length, correctBuffer.length)
  const providedPadded = Buffer.alloc(maxLength)
  const correctPadded = Buffer.alloc(maxLength)

  providedBuffer.copy(providedPadded)
  correctBuffer.copy(correctPadded)

  try {
    // Use crypto.timingSafeEqual for constant-time comparison
    const matches = timingSafeEqual(providedPadded, correctPadded)
    // Also check lengths match to prevent length-based attacks
    return matches && providedBuffer.length === correctBuffer.length
  } catch {
    // timingSafeEqual throws if buffers have different lengths
    return false
  }
}

export async function authenticate(password: string): Promise<boolean> {
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
