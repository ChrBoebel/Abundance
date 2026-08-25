/** Health check for the frontend and its research backend dependency. */
import { NextResponse } from 'next/server'

const BACKEND_URL = process.env.RESEARCH_BACKEND_URL || 'http://localhost:8000'

export async function GET() {
  try {
    const response = await fetch(`${BACKEND_URL}/ready`, {
      cache: 'no-store',
      signal: AbortSignal.timeout(3000),
    })
    if (!response.ok) throw new Error(`Backend returned ${response.status}`)
    const backend = await response.json()
    return NextResponse.json({
      status: 'healthy',
      backend: backend.status,
      backendVersion: backend.version,
      timestamp: new Date().toISOString(),
    })
  } catch {
    return NextResponse.json(
      {
        status: 'degraded',
        backend: 'unavailable',
        timestamp: new Date().toISOString(),
      },
      { status: 503 },
    )
  }
}
