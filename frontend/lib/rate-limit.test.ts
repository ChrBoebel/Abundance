import { describe, expect, it } from 'vitest'

import { LocalRateLimiter } from './rate-limit'

describe('LocalRateLimiter', () => {
  it('blocks after the configured budget and resets after the window', () => {
    const limiter = new LocalRateLimiter(2, 1_000)

    expect(limiter.consume('client', 10).success).toBe(true)
    expect(limiter.consume('client', 20).success).toBe(true)
    expect(limiter.consume('client', 30)).toMatchObject({
      success: false,
      remaining: 0,
    })
    expect(limiter.consume('client', 1_011)).toMatchObject({
      success: true,
      remaining: 1,
    })
  })

  it('bounds attacker-controlled identifier storage', () => {
    const limiter = new LocalRateLimiter(1, 60_000, 2)

    limiter.consume('one', 1)
    limiter.consume('two', 1)
    limiter.consume('three', 1)

    expect(limiter.consume('one', 2).success).toBe(true)
  })
})
