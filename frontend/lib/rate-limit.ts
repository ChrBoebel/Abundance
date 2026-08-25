/** Shared production rate limits with a bounded local development fallback. */

import { Ratelimit } from '@upstash/ratelimit'
import { Redis } from '@upstash/redis'

export type RateLimitKind = 'login' | 'research'

export interface RateLimitDecision {
  success: boolean
  limit: number
  remaining: number
  reset: number
  reason?: 'configuration' | 'local'
}

interface LocalEntry {
  count: number
  reset: number
}

export class LocalRateLimiter {
  private readonly entries = new Map<string, LocalEntry>()

  constructor(
    private readonly limit: number,
    private readonly windowMs: number,
    private readonly maxEntries = 5_000,
  ) {}

  consume(identifier: string, now = Date.now()): RateLimitDecision {
    this.prune(now)
    const current = this.entries.get(identifier)
    const entry = !current || current.reset <= now
      ? { count: 1, reset: now + this.windowMs }
      : { count: current.count + 1, reset: current.reset }
    this.entries.delete(identifier)
    this.entries.set(identifier, entry)
    while (this.entries.size > this.maxEntries) {
      const oldest = this.entries.keys().next().value
      if (oldest === undefined) break
      this.entries.delete(oldest)
    }
    return {
      success: entry.count <= this.limit,
      limit: this.limit,
      remaining: Math.max(0, this.limit - entry.count),
      reset: entry.reset,
      reason: 'local',
    }
  }

  reset(identifier: string): void {
    this.entries.delete(identifier)
  }

  private prune(now: number): void {
    for (const [identifier, entry] of this.entries) {
      if (entry.reset <= now) this.entries.delete(identifier)
    }
  }
}

const localLimiters = {
  login: new LocalRateLimiter(5, 15 * 60 * 1_000),
  research: new LocalRateLimiter(10, 60 * 1_000),
}

let sharedLimiters: Record<RateLimitKind, Ratelimit> | null | undefined

function getSharedLimiters(): Record<RateLimitKind, Ratelimit> | null {
  if (sharedLimiters !== undefined) return sharedLimiters
  if (!process.env.UPSTASH_REDIS_REST_URL || !process.env.UPSTASH_REDIS_REST_TOKEN) {
    sharedLimiters = null
    return null
  }
  const redis = Redis.fromEnv()
  sharedLimiters = {
    login: new Ratelimit({
      redis,
      limiter: Ratelimit.slidingWindow(5, '15 m'),
      prefix: 'abundance:login',
      analytics: true,
      timeout: 1_500,
    }),
    research: new Ratelimit({
      redis,
      limiter: Ratelimit.slidingWindow(10, '1 m'),
      prefix: 'abundance:research',
      analytics: true,
      timeout: 1_500,
    }),
  }
  return sharedLimiters
}

export async function checkRateLimit(
  kind: RateLimitKind,
  identifier: string,
): Promise<RateLimitDecision> {
  const shared = getSharedLimiters()
  if (shared) {
    const result = await shared[kind].limit(identifier)
    return {
      success: result.success,
      limit: result.limit,
      remaining: result.remaining,
      reset: result.reset,
    }
  }
  if (process.env.NODE_ENV === 'production') {
    return {
      success: false,
      limit: 0,
      remaining: 0,
      reset: Date.now() + 60_000,
      reason: 'configuration',
    }
  }
  return localLimiters[kind].consume(identifier)
}

export async function resetRateLimit(kind: RateLimitKind, identifier: string): Promise<void> {
  const shared = getSharedLimiters()
  if (shared) {
    await shared[kind].resetUsedTokens(identifier)
    return
  }
  localLimiters[kind].reset(identifier)
}
