/** Server-side research-run management and Abundance API integration. */

import {
  ResearchRunStatus,
  type ResearchEvent,
  type ResearchMessageRecord,
  type ResearchRunJob,
  type ResearchSession,
} from './types'

type ActiveResearchRun = ResearchRunJob & {
  events: string[]
  controller?: AbortController
}

const researchRuns = new Map<string, ActiveResearchRun>()
const researchSessions = new Map<string, ResearchSession>()
const BACKEND_URL = process.env.RESEARCH_BACKEND_URL || 'http://localhost:8000'

setInterval(() => {
  const oneHourAgo = Date.now() - 60 * 60 * 1000
  for (const [id, run] of researchRuns.entries()) {
    const updatedTime = new Date(run.updated_at).getTime()
    if (updatedTime < oneHourAgo && run.status !== ResearchRunStatus.RUNNING) {
      researchRuns.delete(id)
    }
  }
}, 60 * 60 * 1000)

export function createResearchRun(runId: string): ResearchRunJob {
  const run: ActiveResearchRun = {
    id: runId,
    status: ResearchRunStatus.PENDING,
    result: null,
    error: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    events: [],
  }
  researchRuns.set(runId, run)
  return run
}

export function getResearchRun(runId: string): ActiveResearchRun | undefined {
  return researchRuns.get(runId)
}

export function updateResearchRunStatus(
  runId: string,
  status: ResearchRunStatus,
  error?: string,
) {
  const run = researchRuns.get(runId)
  if (!run) return
  run.status = status
  run.updated_at = new Date().toISOString()
  if (error) run.error = error
}

export function pushResearchRunEvent(runId: string, event: ResearchEvent) {
  const run = researchRuns.get(runId)
  if (!run) return
  run.events.push(`data: ${JSON.stringify(event)}\n\n`)
  run.updated_at = new Date().toISOString()
}

export function getResearchSession(sessionId: string): ResearchSession {
  if (!researchSessions.has(sessionId)) {
    researchSessions.set(sessionId, {
      id: sessionId,
      messages: [],
      created_at: new Date().toISOString(),
    })
  }
  return researchSessions.get(sessionId)!
}

export function clearResearchSession(sessionId: string) {
  const session = researchSessions.get(sessionId)
  if (session) session.messages = []
}

export function addResearchMessage(sessionId: string, message: ResearchMessageRecord) {
  getResearchSession(sessionId).messages.push(message)
}

export async function startResearch(
  runId: string,
  inquiry: string,
  sessionId: string,
  model: string = 'mercury',
  mode: 'quick' | 'balanced' | 'thorough' = 'balanced',
): Promise<void> {
  const run = getResearchRun(runId)
  if (!run) throw new Error('Research run not found')

  updateResearchRunStatus(runId, ResearchRunStatus.RUNNING)
  addResearchMessage(sessionId, { role: 'user', content: inquiry })

  const controller = new AbortController()
  run.controller = controller

  try {
    const response = await fetch(`${BACKEND_URL}/api/v1/research-runs/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ inquiry, model, mode }),
      signal: controller.signal,
    })

    if (!response.ok) {
      throw new Error(`Backend error: ${response.status} ${response.statusText}`)
    }
    if (!response.body) throw new Error('Research stream has no response body')

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          const event = JSON.parse(line.slice(6)) as ResearchEvent
          pushResearchRunEvent(runId, event)
          if (event.type === 'run.completed') {
            updateResearchRunStatus(runId, ResearchRunStatus.COMPLETED)
          } else if (event.type === 'run.failed') {
            const error = event.data?.error || event.message || 'Research failed'
            updateResearchRunStatus(runId, ResearchRunStatus.FAILED, error)
          }
        } catch {
          // Ignore malformed or incomplete event lines; the SSE reader keeps its buffer.
        }
      }
    }
  } catch (error) {
    if (error instanceof Error && error.name === 'AbortError') return
    const message = error instanceof Error ? error.message : 'Unknown research error'
    updateResearchRunStatus(runId, ResearchRunStatus.FAILED, message)
    pushResearchRunEvent(runId, {
      type: 'run.failed',
      message: 'Recherche fehlgeschlagen',
      data: { error: message },
    })
  }
}
