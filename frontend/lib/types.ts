/** Shared Abundance research-domain types. */

export interface ResearchMessageRecord {
  role: 'user' | 'agent'
  content: string
  runId?: string
  report?: PublicResearchReport
  evaluation?: ReportEvaluation
  metrics?: RunMetrics
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
  id?: string
  title: string
  url: string
  relation?: 'supports' | 'challenges' | 'context'
  source_kind?: 'primary' | 'secondary' | 'academic' | 'news' | 'other'
  is_primary?: boolean
  published_at?: string | null
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
  metrics?: unknown
}

export interface ResearchEvent {
  type:
    | 'run.accepted'
    | 'run.completed'
    | 'run.metrics'
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
  runId?: string
  query: string
  report: string
  sources: Source[]
  model: string
  createdAt: string
  structuredReport?: PublicResearchReport
  evaluation?: ReportEvaluation
  metrics?: RunMetrics
}

export type Confidence = 'low' | 'medium' | 'high'

export interface CounterEvidence {
  summary: string
  evidence_ids: string[]
  impact: Confidence
}

export interface PublicClaim {
  id: string
  statement: string
  evidence_ids: string[]
  counter_evidence: CounterEvidence[]
  confidence: Confidence
  uncertainty_notes: string[]
}

export interface OpenQuestion {
  question: string
  why_it_matters: string
  suggested_next_step?: string | null
}

export interface PublicResearchReport {
  inquiry_id: string
  title: string
  summary: string
  confidence: Confidence
  claims: PublicClaim[]
  evidence: DiscoveredEvidence[]
  open_questions: OpenQuestion[]
  markdown: string
  completed_at: string
}

export interface ReportEvaluation {
  total_claims: number
  total_sources: number
  claim_evidence_coverage: number
  challenged_claim_ratio: number
  primary_source_ratio: number
  broken_evidence_links: number
  open_question_count: number
}

export interface ModelUsage {
  input_tokens: number
  output_tokens: number
  total_tokens: number
  cost_usd?: number | null
}

export interface RunMetrics {
  duration_ms: number
  stage_duration_ms: Record<string, number>
  event_count: number
  evidence_count: number
  claim_count: number
  model: string
  mode: string
  usage: ModelUsage
}

export interface StoredResearchRun {
  id: string
  inquiry: { question?: string }
  model: string
  mode: string
  status: string
  report?: PublicResearchReport | null
  evaluation?: ReportEvaluation | null
  metrics?: RunMetrics | null
  created_at: string
  completed_at?: string | null
}

export const MODEL_DISPLAY_NAMES: Record<string, string> = {
  mercury: 'Mercury 2',
  gemini: 'Gemini 2.5 Flash Lite',
  deepseek: 'DeepSeek V3.2',
  glm: 'GLM-4.5-Air',
  'gemini-flash': 'Gemini 2.5 Flash',
}
