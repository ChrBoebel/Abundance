/**
 * Research Job Management and Python Bridge Integration
 */
import { spawn, ChildProcessWithoutNullStreams } from 'child_process'
import { JobStatus, type Job, type Thread, type Message } from './types'
import path from 'path'
import fs from 'fs'

// In-memory storage
const jobs = new Map<string, Job & { process?: ChildProcessWithoutNullStreams, events: string[] }>()
const threads = new Map<string, Thread>()

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
  const job: Job & { process?: ChildProcessWithoutNullStreams, events: string[] } = {
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
 * Start research job in background using Python bridge
 */
export function startResearch(
  jobId: string,
  message: string,
  threadId: string,
  modelName: string = 'deepseek'
): void {
  const job = getJob(jobId)
  if (!job) {
    throw new Error('Job not found')
  }

  updateJobStatus(jobId, JobStatus.RUNNING)

  // Add user message to thread
  addMessage(threadId, { role: 'user', content: message })

  // Determine model based on selection
  const model = modelName === 'gemini'
    ? 'openrouter:google/gemini-2.5-flash-lite'
    : 'openrouter:deepseek/deepseek-v3.2-exp'

  // Prepare config
  const config = {
    configurable: {
      research_model: model,
      summarization_model: model,
      compression_model: model,
      final_report_model: model,
      search_api: 'tavily',
      allow_clarification: false,
      max_concurrent_research_units: 3,
    },
  }

  const input = JSON.stringify({ message, config })

  // Spawn Python process
  const scriptPath = path.join(process.cwd(), 'scripts', 'research_bridge.py')

  // Try to find Python in venv first, then fallback
  let pythonCmd = 'python3.11'  // Use python3.11 explicitly

  const venvPython = '/opt/venv/bin/python'
  if (fs.existsSync(venvPython)) {
    pythonCmd = venvPython
  } else if (process.env.PYTHON_CMD) {
    pythonCmd = process.env.PYTHON_CMD
  }

  console.log(`Starting Python process: ${pythonCmd} ${scriptPath}`)

  const pythonProcess = spawn(pythonCmd, [scriptPath], {
    env: { ...process.env }  // Pass all environment variables to Python
  })

  // Store process reference
  job.process = pythonProcess

  // Write input to stdin
  pythonProcess.stdin.write(input)
  pythonProcess.stdin.end()

  // Buffer for incomplete JSON
  let buffer = ''

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

  // Handle stdout (events)
  pythonProcess.stdout.on('data', (data: Buffer) => {
    buffer += data.toString()
    const lines = buffer.split('\n')

    // Keep the last incomplete line in buffer
    buffer = lines.pop() || ''

    for (const line of lines) {
      if (!line.trim()) continue

      try {
        const event = JSON.parse(line)

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
  })

  // Collect stderr for better error reporting
  let stderrBuffer = ''
  pythonProcess.stderr.on('data', (data: Buffer) => {
    const errorText = data.toString()
    stderrBuffer += errorText
    console.error('Python stderr:', errorText)
  })

  // Handle process exit
  pythonProcess.on('close', (code: number | null) => {
    if (code !== 0 && job.status === JobStatus.RUNNING) {
      const errorMsg = stderrBuffer || `Process exited with code ${code}`
      updateJobStatus(jobId, JobStatus.FAILED, errorMsg)
      pushJobEvent(jobId, `data: ${JSON.stringify({ type: 'error', error: errorMsg })}\n\n`)
    }
    // Signal done
    pushJobEvent(jobId, `data: ${JSON.stringify({ type: 'done' })}\n\n`)
  })

  // Handle errors
  pythonProcess.on('error', (error: Error) => {
    console.error('Python process error:', error)
    updateJobStatus(jobId, JobStatus.FAILED, error.message)
    pushJobEvent(jobId, `data: ${JSON.stringify({ type: 'error', error: error.message })}\n\n`)
  })
}
