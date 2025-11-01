/**
 * Simple in-memory rate limiter for login attempts
 */

interface RateLimitEntry {
  attempts: number
  firstAttempt: number
  blockedUntil?: number
}

class RateLimiter {
  private attempts: Map<string, RateLimitEntry> = new Map()
  private readonly maxAttempts: number
  private readonly windowMs: number
  private readonly blockDurationMs: number

  constructor(
    maxAttempts: number = 5,
    windowMs: number = 15 * 60 * 1000, // 15 minutes
    blockDurationMs: number = 15 * 60 * 1000 // 15 minutes
  ) {
    this.maxAttempts = maxAttempts
    this.windowMs = windowMs
    this.blockDurationMs = blockDurationMs

    // Cleanup old entries every 5 minutes
    setInterval(() => this.cleanup(), 5 * 60 * 1000)
  }

  /**
   * Check if an identifier is rate limited
   */
  isLimited(identifier: string): boolean {
    const entry = this.attempts.get(identifier)

    if (!entry) return false

    const now = Date.now()

    // Check if currently blocked
    if (entry.blockedUntil && entry.blockedUntil > now) {
      return true
    }

    // Check if window has expired
    if (now - entry.firstAttempt > this.windowMs) {
      this.attempts.delete(identifier)
      return false
    }

    // Check if max attempts exceeded
    return entry.attempts >= this.maxAttempts
  }

  /**
   * Record a failed login attempt
   */
  recordAttempt(identifier: string): void {
    const now = Date.now()
    const entry = this.attempts.get(identifier)

    if (!entry) {
      // First attempt
      this.attempts.set(identifier, {
        attempts: 1,
        firstAttempt: now,
      })
      return
    }

    // Check if window has expired
    if (now - entry.firstAttempt > this.windowMs) {
      // Reset counter
      this.attempts.set(identifier, {
        attempts: 1,
        firstAttempt: now,
      })
      return
    }

    // Increment attempts
    entry.attempts++

    // Block if max attempts exceeded
    if (entry.attempts >= this.maxAttempts) {
      entry.blockedUntil = now + this.blockDurationMs
    }

    this.attempts.set(identifier, entry)
  }

  /**
   * Reset attempts for an identifier (e.g., after successful login)
   */
  reset(identifier: string): void {
    this.attempts.delete(identifier)
  }

  /**
   * Get remaining attempts for an identifier
   */
  getRemainingAttempts(identifier: string): number {
    const entry = this.attempts.get(identifier)

    if (!entry) return this.maxAttempts

    const now = Date.now()

    // Check if window has expired
    if (now - entry.firstAttempt > this.windowMs) {
      return this.maxAttempts
    }

    return Math.max(0, this.maxAttempts - entry.attempts)
  }

  /**
   * Get time until unblocked (in milliseconds)
   */
  getBlockedUntil(identifier: string): number | null {
    const entry = this.attempts.get(identifier)

    if (!entry || !entry.blockedUntil) return null

    const now = Date.now()
    const remaining = entry.blockedUntil - now

    return remaining > 0 ? remaining : null
  }

  /**
   * Cleanup old entries
   */
  private cleanup(): void {
    const now = Date.now()
    const toDelete: string[] = []

    this.attempts.forEach((entry, identifier) => {
      // Remove expired entries
      if (now - entry.firstAttempt > this.windowMs + this.blockDurationMs) {
        toDelete.push(identifier)
      }
    })

    toDelete.forEach(id => this.attempts.delete(id))
  }

  /**
   * Get stats for monitoring
   */
  getStats(): { totalEntries: number; blockedCount: number } {
    const now = Date.now()
    let blockedCount = 0

    this.attempts.forEach(entry => {
      if (entry.blockedUntil && entry.blockedUntil > now) {
        blockedCount++
      }
    })

    return {
      totalEntries: this.attempts.size,
      blockedCount,
    }
  }
}

// Singleton instance
export const loginRateLimiter = new RateLimiter()
