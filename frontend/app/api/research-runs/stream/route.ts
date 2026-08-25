/** Browser-facing SSE route for Abundance research runs. */
import { NextRequest } from 'next/server'
import { isAuthenticated } from '@/lib/auth'
import { createResearchRun, getResearchRun, startResearch } from '@/lib/research'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

export async function GET(request: NextRequest) {
  try {
    // Check authentication
    if (!(await isAuthenticated())) {
      return new Response(
        JSON.stringify({ error: 'Unauthorized' }),
        { status: 401, headers: { 'Content-Type': 'application/json' } }
      )
    }

    const searchParams = request.nextUrl.searchParams
    const inquiry = searchParams.get('inquiry')
    const sessionId = searchParams.get('session_id') || 'default'
    const model = searchParams.get('model') || 'mercury'
    const mode = searchParams.get('mode') as 'quick' | 'balanced' | 'thorough' | null
    let runId = searchParams.get('run_id')

    if (!runId) {
      if (!inquiry) {
        return new Response(
          JSON.stringify({ error: 'No inquiry provided' }),
          { status: 400, headers: { 'Content-Type': 'application/json' } }
        )
      }

      runId = `${sessionId}-${Date.now()}`
      createResearchRun(runId)
      void startResearch(runId, inquiry, sessionId, model, mode || 'balanced')
    }

    const run = getResearchRun(runId)
    if (!run) {
      return new Response(
        JSON.stringify({ error: 'Research run not found' }),
        { status: 404, headers: { 'Content-Type': 'application/json' } }
      )
    }

    // Create SSE stream
    const encoder = new TextEncoder()
    let eventIndex = 0
    let heartbeatInterval: NodeJS.Timeout | null = null

    const stream = new ReadableStream({
      start(controller) {
        const acceptedEvent = `data: ${JSON.stringify({ type: 'run.accepted', data: { run_id: runId } })}\n\n`
        controller.enqueue(encoder.encode(acceptedEvent))

        // Setup heartbeat
        heartbeatInterval = setInterval(() => {
          try {
            controller.enqueue(encoder.encode(': heartbeat\n\n'))
          } catch (e) {
            // Stream closed
            if (heartbeatInterval) clearInterval(heartbeatInterval)
          }
        }, 15000) // Every 15 seconds

        // Stream events
        const streamInterval = setInterval(() => {
          if (!run) {
            clearInterval(streamInterval)
            if (heartbeatInterval) clearInterval(heartbeatInterval)
            controller.close()
            return
          }

          // Send new events
          while (eventIndex < run.events.length) {
            const event = run.events[eventIndex]
            controller.enqueue(encoder.encode(event))
            eventIndex++
          }

          // Check if job is done
          if (run.status === 'completed' || run.status === 'failed') {
            clearInterval(streamInterval)
            if (heartbeatInterval) clearInterval(heartbeatInterval)
            controller.close()
          }
        }, 100) // Check every 100ms
      },
      cancel() {
        if (heartbeatInterval) clearInterval(heartbeatInterval)
      },
    })

    return new Response(stream, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache, no-transform',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no',
      },
    })
  } catch (error) {
    console.error('Stream error:', error)
    return new Response(
      JSON.stringify({ error: 'Internal server error' }),
      { status: 500, headers: { 'Content-Type': 'application/json' } }
    )
  }
}
