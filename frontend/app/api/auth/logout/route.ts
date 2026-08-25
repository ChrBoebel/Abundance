/**
 * Logout API Route
 */
import { NextRequest, NextResponse } from 'next/server'
import { logout } from '@/lib/auth'
import { isSameOriginRequest } from '@/lib/request-security'

export async function POST(request: NextRequest) {
  try {
    if (!isSameOriginRequest(request)) {
      return NextResponse.json({ error: 'Cross-site request rejected' }, { status: 403 })
    }
    await logout()
    return NextResponse.json({ success: true })
  } catch {
    console.error('Logout request failed')
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}
