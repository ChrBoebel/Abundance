import type { SessionOptions } from 'iron-session'

function requireSessionSecret(): string {
  const value = process.env.SESSION_SECRET
  if (!value) {
    throw new Error('SESSION_SECRET environment variable is required')
  }
  return value
}

export const sessionOptions: SessionOptions = {
  password: requireSessionSecret(),
  cookieName: 'abundance_session',
  cookieOptions: {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    maxAge: 60 * 60 * 24 * 7,
  },
}
