import type { SessionOptions } from 'iron-session'

function requireSessionSecret(): string {
  const value = process.env.SESSION_SECRET
  if (!value || value.length < 32) {
    throw new Error('SESSION_SECRET must contain at least 32 characters')
  }
  return value
}

export function getSessionOptions(): SessionOptions {
  return {
    password: requireSessionSecret(),
    cookieName: 'abundance_session',
    cookieOptions: {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'strict',
      maxAge: 60 * 60 * 12,
    },
  }
}
