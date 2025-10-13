/**
 * SSE Streaming API Route for Research
 */
import { NextRequest } from 'next/server'
import { isAuthenticated } from '@/lib/auth'
import { createJob, getJob, startResearch } from '@/lib/research'

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
    const message = searchParams.get('message')
    const threadId = searchParams.get('thread_id') || 'default'
    const modelName = searchParams.get('model') || 'deepseek'
    let jobId = searchParams.get('job_id')

    // If no job_id, create new job and start research
    if (!jobId) {
      if (!message) {
        return new Response(
          JSON.stringify({ error: 'No message provided' }),
          { status: 400, headers: { 'Content-Type': 'application/json' } }
        )
      }

      // Generate job ID
      jobId = `${threadId}-${Date.now()}`
      createJob(jobId)
      startResearch(jobId, message, threadId, modelName)
    }

    // Get job
    const job = getJob(jobId)
    if (!job) {
      return new Response(
        JSON.stringify({ error: 'Job not found' }),
        { status: 404, headers: { 'Content-Type': 'application/json' } }
      )
    }

    // Create SSE stream
    const encoder = new TextEncoder()
    let eventIndex = 0
    let heartbeatInterval: NodeJS.Timeout | null = null

    const stream = new ReadableStream({
      start(controller) {
        // Send job_id to client
        const jobStartEvent = `data: ${JSON.stringify({ type: 'job_started', job_id: jobId })}\n\n`
        controller.enqueue(encoder.encode(jobStartEvent))

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
          if (!job) {
            clearInterval(streamInterval)
            if (heartbeatInterval) clearInterval(heartbeatInterval)
            controller.close()
            return
          }

          // Send new events
          while (eventIndex < job.events.length) {
            const event = job.events[eventIndex]
            controller.enqueue(encoder.encode(event))
            eventIndex++
          }

          // Check if job is done
          if (job.status === 'completed' || job.status === 'failed') {
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
