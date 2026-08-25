/** Shared Abundance research-domain types. */

export interface ResearchMessageRecord {
  role: 'user' | 'agent'
  content: string
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

export interface DiscoveredEvidence {
  id: string
  title: string
  url: string
  relation: 'supports' | 'challenges' | 'context'
  source_kind: 'primary' | 'secondary' | 'academic' | 'news' | 'other'
  is_primary: boolean
  published_at?: string | null
}

export interface ResearchEventData {
  run_id?: string
  query?: string
  evidence?: DiscoveredEvidence
  content?: string
  code?: string
  correlation_id?: string
  evidence_count?: number
  claim_count?: number
  unit_count?: number
  plan?: unknown
  report?: unknown
  evaluation?: unknown
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
    | 'evidence.search.failed'
    | 'evidence.review.started'
    | 'synthesis.started'
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
