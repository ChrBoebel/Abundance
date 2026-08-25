/** Shared Abundance research-domain types. */

export interface ResearchMessageRecord {
  role: 'user' | 'agent'
  content: string
}

export interface ResearchSession {
  id: string
  messages: ResearchMessageRecord[]
  created_at: string
}

export type ResearchStage = 'inquiry' | 'planning' | 'evidence' | 'review' | 'synthesis'
export type ResearchMode = 'quick' | 'balanced' | 'thorough'

export interface ResearchPhase {
  id: number
  stage: ResearchStage
  name: string
  icon: string
  status: 'pending' | 'running' | 'completed'
}

export interface Source {
  title: string
  url: string
}

export enum ResearchRunStatus {
  PENDING = 'pending',
  RUNNING = 'running',
  COMPLETED = 'completed',
  FAILED = 'failed',
}

export interface ResearchRunJob {
  id: string
  status: ResearchRunStatus
  result: unknown
  error: string | null
  created_at: string
  updated_at: string
  controller?: AbortController
}

export interface ResearchEventData {
  run_id?: string
  runtime_node?: string
  tool?: string
  query?: unknown
  result?: unknown
  chunk?: string
  content?: string
  error?: string
}

export interface ResearchEvent {
  type:
    | 'run.accepted'
    | 'run.completed'
    | 'run.failed'
    | 'inquiry.scoping'
    | 'plan.created'
    | 'evidence.collection.started'
    | 'evidence.search.started'
    | 'evidence.discovered'
    | 'evidence.review.started'
    | 'synthesis.started'
    | 'report.delta'
    | 'report.completed'
  stage?: ResearchStage
  message?: string
  data?: ResearchEventData
  timestamp?: string
}

export interface SessionData {
  authenticated: boolean
}

export interface ResearchArchiveEntry {
  id: string
  query: string
  report: string
  sources: Source[]
  model: string
  createdAt: string
}

export const MODEL_DISPLAY_NAMES: Record<string, string> = {
  mercury: 'Mercury 2',
  gemini: 'Gemini 2.5 Flash Lite',
  deepseek: 'DeepSeek V3.2',
  glm: 'GLM-4.5-Air',
  'gemini-flash': 'Gemini 2.5 Flash',
}
