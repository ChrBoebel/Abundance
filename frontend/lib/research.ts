/**
 * Research Job Management and HTTP Backend Integration
 */
import { JobStatus, type Job, type Thread, type Message } from './types'

// In-memory storage
const jobs = new Map<string, Job & { events: string[], controller?: AbortController }>()
const threads = new Map<string, Thread>()

// Backend URL from environment
const BACKEND_URL = process.env.RESEARCH_BACKEND_URL || 'http://localhost:8000'

// Cleanup old jobs (every hour)
setInterval(() => {
  const oneHourAgo = Date.now() - 60 * 60 * 1000
  for (const [id, job] of jobs.entries()) {
    const updatedTime = new Date(job.updated_at).getTime()
    if (updatedTime < oneHourAgo && job.status !== JobStatus.RUNNING) {
      jobs.delete(id)
    }
  }
}, 60 * 60 * 1000)

export function createJob(jobId: string): Job {
  const job: Job & { events: string[], controller?: AbortController } = {
    id: jobId,
    status: JobStatus.PENDING,
    result: null,
    error: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    events: [],
  }
  jobs.set(jobId, job)
  return job
}

export function getJob(jobId: string): (Job & { events: string[] }) | undefined {
  return jobs.get(jobId)
}

export function updateJobStatus(jobId: string, status: JobStatus, error?: string) {
  const job = jobs.get(jobId)
  if (job) {
    job.status = status
    job.updated_at = new Date().toISOString()
    if (error) {
      job.error = error
    }
  }
}

export function pushJobEvent(jobId: string, event: string) {
  const job = jobs.get(jobId)
  if (job) {
    job.events.push(event)
  }
}

export function getThread(threadId: string): Thread {
  if (!threads.has(threadId)) {
    threads.set(threadId, {
      id: threadId,
      messages: [],
      created_at: new Date().toISOString(),
    })
  }
  return threads.get(threadId)!
}

export function clearThread(threadId: string) {
  const thread = threads.get(threadId)
  if (thread) {
    thread.messages = []
  }
}

export function addMessage(threadId: string, message: Message) {
  const thread = getThread(threadId)
  thread.messages.push(message)
}

/**
 * Start research job in background using HTTP backend
 */
export async function startResearch(
  jobId: string,
  message: string,
  threadId: string,
  model: string = 'mercury'
): Promise<void> {
  const job = getJob(jobId)
  if (!job) {
    throw new Error('Job not found')
  }

  updateJobStatus(jobId, JobStatus.RUNNING)

  // Add user message to thread
  addMessage(threadId, { role: 'user', content: message })

  // Create abort controller for cancellation
  const controller = new AbortController()
  job.controller = controller

  // Track if we've already sent the final report
  let finalReportSent = false

  // Track if we're streaming the final report
  let isStreamingReport = false

  // Helper function to map LangGraph events to frontend events
  function mapEventToFrontend(event: any) {
    const mapped: any[] = []

    // Map LangGraph events to frontend-compatible events
    if (event.event === 'on_chain_start') {
      const name = event.name || event.data?.name
      const nodeName = event.metadata?.langgraph_node || event.data?.metadata?.langgraph_node
      if (name) {
        mapped.push({ type: 'step_start', step_name: name, name })
        // Start streaming when final report generation begins
        if (nodeName === 'final_report_generation') {
          isStreamingReport = true
        }
      }

      // Map node names to user-friendly status messages
      if (nodeName) {
        let activityMessage = ''

        if (nodeName === 'clarify_with_user') {
          activityMessage = 'Kläre Recherchefrage...'
        } else if (nodeName === 'write_research_brief') {
          activityMessage = 'Erstelle Recherchestrategie...'
        } else if (nodeName === 'supervisor' || nodeName === 'research_supervisor') {
          activityMessage = 'Plane Recherche-Aufgaben...'
        } else if (nodeName === 'researcher') {
          // Try to extract research topic from input
          const input = event.data?.input
          if (input?.researcher_messages?.[0]?.content) {
            const topic = input.researcher_messages[0].content
            const shortTopic = topic.length > 60 ? topic.substring(0, 60) + '...' : topic
            activityMessage = `Recherchiere zu: ${shortTopic}`
          } else {
            activityMessage = 'Recherchiere...'
          }
        } else if (nodeName === 'compress_research') {
          activityMessage = 'Komprimiere Ergebnisse...'
        } else if (nodeName === 'final_report_generation') {
          activityMessage = 'Generiere finalen Bericht...'
        }

        if (activityMessage) {
          mapped.push({ type: 'current_activity', activity: activityMessage })
        }
      }
    } else if (event.event === 'on_chain_end') {
      const name = event.name || event.data?.name
      const nodeName = event.metadata?.langgraph_node || event.data?.metadata?.langgraph_node
      if (name) {
        mapped.push({ type: 'step_complete', step_name: name, name })
      }

      // Stop streaming when final report node ends
      if (nodeName === 'final_report_generation') {
        isStreamingReport = false
      }

      // Check for final report (only send once)
      if (event.data?.output?.final_report && !finalReportSent) {
        const finalReport = event.data.output.final_report
        mapped.push({ type: 'agent_message', content: finalReport })
        finalReportSent = true
      }
    } else if (event.event === 'on_tool_start') {
      const name = event.name || event.data?.name
      const args = event.data?.input
      if (name) {
        mapped.push({ type: 'tool_call_start', name, args })
      }
    } else if (event.event === 'on_chat_model_stream') {
      // Stream final report chunks
      if (isStreamingReport && event.data?.chunk) {
        // chunk is now directly the string content (cleaned by Python bridge)
        const content = typeof event.data.chunk === 'string'
          ? event.data.chunk
          : event.data.chunk?.content || ''
        if (content) {
          mapped.push({ type: 'report_stream', chunk: content })
        }
      }
    } else if (event.event === 'on_tool_end') {
      const name = event.name || event.data?.name
      const result = event.data?.output
      if (name) {
        mapped.push({ type: 'tool_call_complete', name, result })
      }
    } else if (event.event === 'done') {
      mapped.push({ type: 'done' })
      updateJobStatus(jobId, JobStatus.COMPLETED)
    } else if (event.event === 'error') {
      mapped.push({ type: 'error', error: event.error })
      updateJobStatus(jobId, JobStatus.FAILED, event.error)
    }

    return mapped
  }

  try {
    // Make HTTP request to backend
    const response = await fetch(`${BACKEND_URL}/research/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message,
        model,
      }),
      signal: controller.signal,
    })

    if (!response.ok) {
      throw new Error(`Backend error: ${response.status} ${response.statusText}`)
    }

    if (!response.body) {
      throw new Error('No response body')
    }

    // Read SSE stream
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()

      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')

      // Keep the last incomplete line in buffer
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.trim() || line.startsWith(':')) continue

        // Parse SSE data
        if (line.startsWith('data: ')) {
          const data = line.slice(6)

          try {
            const event = JSON.parse(data)

            // Map to frontend events
            const frontendEvents = mapEventToFrontend(event)

            // Send each mapped event
            for (const fe of frontendEvents) {
              const sseEvent = `data: ${JSON.stringify(fe)}\n\n`
              pushJobEvent(jobId, sseEvent)
            }
          } catch (parseError) {
            // Silently ignore parse errors for incomplete chunks
          }
        }
      }
    }

    // Signal completion
    pushJobEvent(jobId, `data: ${JSON.stringify({ type: 'done' })}\n\n`)

  } catch (error: any) {
    if (error.name === 'AbortError') {
      console.log('Research request aborted')
    } else {
      console.error('Research error:', error)
      updateJobStatus(jobId, JobStatus.FAILED, error.message)
      pushJobEvent(jobId, `data: ${JSON.stringify({ type: 'error', error: error.message })}\n\n`)
    }
  }
}
