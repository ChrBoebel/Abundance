import { NextRequest } from 'next/server'
import { afterEach, describe, expect, it } from 'vitest'

import { clientRateLimitKey, isSameOriginRequest } from './request-security'

const originalSecret = process.env.SESSION_SECRET

afterEach(() => {
  process.env.SESSION_SECRET = originalSecret
})

describe('isSameOriginRequest', () => {
  it('accepts same-origin browser requests', () => {
    const request = new NextRequest('https://abundance.example/api/action', {
      headers: {
        origin: 'https://abundance.example',
        'sec-fetch-site': 'same-origin',
      },
    })

    expect(isSameOriginRequest(request)).toBe(true)
  })

  it('rejects cross-site requests', () => {
    const request = new NextRequest('https://abundance.example/api/action', {
      headers: {
        origin: 'https://attacker.example',
        'sec-fetch-site': 'cross-site',
      },
    })

    expect(isSameOriginRequest(request)).toBe(false)
  })
})

describe('clientRateLimitKey', () => {
  it('is stable without retaining the raw client address', () => {
    process.env.SESSION_SECRET = 'a-secure-test-session-secret-of-32-characters'
    const request = new NextRequest('https://abundance.example/api/action', {
      headers: { 'x-railway-client-ip': '203.0.113.42' },
    })

    const first = clientRateLimitKey(request)
    const second = clientRateLimitKey(request)

    expect(first).toBe(second)
    expect(first).toHaveLength(64)
    expect(first).not.toContain('203.0.113.42')
  })
})
