/** Runtime-safe adapters for streamed and persisted research records. */

import type {
  PublicResearchReport,
  ReportEvaluation,
  ResearchArchiveEntry,
  RunMetrics,
  Source,
  StoredResearchRun,
} from './types'

type UnknownRecord = Record<string, unknown>

function isRecord(value: unknown): value is UnknownRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every(item => typeof item === 'string')
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value)
}

function sourceFromUnknown(value: unknown): Source | null {
  if (!isRecord(value) || typeof value.title !== 'string' || typeof value.url !== 'string') {
    return null
  }
  try {
    const parsed = new URL(value.url)
    if (!['http:', 'https:'].includes(parsed.protocol)) return null
  } catch {
    return null
  }
  const relations = ['supports', 'challenges', 'context'] as const
  const sourceKinds = ['primary', 'secondary', 'academic', 'news', 'other'] as const
  return {
    ...(typeof value.id === 'string' ? { id: value.id } : {}),
    title: value.title,
    url: value.url,
    ...(relations.includes(value.relation as typeof relations[number])
      ? { relation: value.relation as Source['relation'] }
      : {}),
    ...(sourceKinds.includes(value.source_kind as typeof sourceKinds[number])
      ? { source_kind: value.source_kind as Source['source_kind'] }
      : {}),
    ...(typeof value.is_primary === 'boolean' ? { is_primary: value.is_primary } : {}),
    ...(typeof value.published_at === 'string' || value.published_at === null
      ? { published_at: value.published_at }
      : {}),
  }
}

export function publicReportFromUnknown(value: unknown): PublicResearchReport | null {
  if (!isRecord(value)) return null
  if (
    typeof value.inquiry_id !== 'string' ||
    typeof value.title !== 'string' ||
    typeof value.summary !== 'string' ||
    typeof value.markdown !== 'string' ||
    typeof value.completed_at !== 'string' ||
    !['low', 'medium', 'high'].includes(String(value.confidence)) ||
    !Array.isArray(value.claims) ||
    !Array.isArray(value.evidence) ||
    !Array.isArray(value.open_questions)
  ) return null

  const claims = value.claims.flatMap(item => {
    if (
      !isRecord(item) ||
      typeof item.id !== 'string' ||
      typeof item.statement !== 'string' ||
      !isStringArray(item.evidence_ids) ||
      !Array.isArray(item.counter_evidence) ||
      !['low', 'medium', 'high'].includes(String(item.confidence)) ||
      !isStringArray(item.uncertainty_notes)
    ) return []
    const counterEvidence = item.counter_evidence.flatMap(counter => {
      if (
        !isRecord(counter) ||
        typeof counter.summary !== 'string' ||
        !isStringArray(counter.evidence_ids) ||
        !['low', 'medium', 'high'].includes(String(counter.impact))
      ) return []
      return [{
        summary: counter.summary,
        evidence_ids: counter.evidence_ids,
        impact: counter.impact as 'low' | 'medium' | 'high',
      }]
    })
    return [{
      id: item.id,
      statement: item.statement,
      evidence_ids: item.evidence_ids,
      counter_evidence: counterEvidence,
      confidence: item.confidence as 'low' | 'medium' | 'high',
      uncertainty_notes: item.uncertainty_notes,
    }]
  })

  const evidence = value.evidence.flatMap(item => {
    const source = sourceFromUnknown(item)
    if (!source?.id || !source.relation || !source.source_kind || source.is_primary === undefined) {
      return []
    }
    return [{
      id: source.id,
      title: source.title,
      url: source.url,
      relation: source.relation,
      source_kind: source.source_kind,
      is_primary: source.is_primary,
      published_at: source.published_at,
    }]
  })

  const openQuestions = value.open_questions.flatMap(item => {
    if (
      !isRecord(item) ||
      typeof item.question !== 'string' ||
      typeof item.why_it_matters !== 'string'
    ) return []
    return [{
      question: item.question,
      why_it_matters: item.why_it_matters,
      ...(typeof item.suggested_next_step === 'string' || item.suggested_next_step === null
        ? { suggested_next_step: item.suggested_next_step }
        : {}),
    }]
  })

  return {
    inquiry_id: value.inquiry_id,
    title: value.title,
    summary: value.summary,
    confidence: value.confidence as 'low' | 'medium' | 'high',
    claims,
    evidence,
    open_questions: openQuestions,
    markdown: value.markdown,
    completed_at: value.completed_at,
  }
}

export function evaluationFromUnknown(value: unknown): ReportEvaluation | undefined {
  if (!isRecord(value)) return undefined
  const keys: (keyof ReportEvaluation)[] = [
    'total_claims',
    'total_sources',
    'claim_evidence_coverage',
    'challenged_claim_ratio',
    'primary_source_ratio',
    'broken_evidence_links',
    'open_question_count',
  ]
  if (!keys.every(key => isFiniteNumber(value[key]))) return undefined
  return Object.fromEntries(keys.map(key => [key, value[key]])) as unknown as ReportEvaluation
}

export function metricsFromUnknown(value: unknown): RunMetrics | undefined {
  if (
    !isRecord(value) ||
    !isFiniteNumber(value.duration_ms) ||
    !isRecord(value.stage_duration_ms) ||
    !isFiniteNumber(value.event_count) ||
    !isFiniteNumber(value.evidence_count) ||
    !isFiniteNumber(value.claim_count) ||
    typeof value.model !== 'string' ||
    typeof value.mode !== 'string' ||
    !isRecord(value.usage)
  ) return undefined
  const usage = value.usage
  if (
    !isFiniteNumber(usage.input_tokens) ||
    !isFiniteNumber(usage.output_tokens) ||
    !isFiniteNumber(usage.total_tokens) ||
    !(usage.cost_usd === null || usage.cost_usd === undefined || isFiniteNumber(usage.cost_usd))
  ) return undefined
  const stageDuration = Object.fromEntries(
    Object.entries(value.stage_duration_ms).filter((entry): entry is [string, number] => isFiniteNumber(entry[1])),
  )
  return {
    duration_ms: value.duration_ms,
    stage_duration_ms: stageDuration,
    event_count: value.event_count,
    evidence_count: value.evidence_count,
    claim_count: value.claim_count,
    model: value.model,
    mode: value.mode,
    usage: {
      input_tokens: usage.input_tokens,
      output_tokens: usage.output_tokens,
      total_tokens: usage.total_tokens,
      cost_usd: usage.cost_usd as number | null | undefined,
    },
  }
}

export function archiveEntryFromStoredRun(value: unknown): ResearchArchiveEntry | null {
  if (!isRecord(value) || value.status !== 'completed' || typeof value.id !== 'string') return null
  const inquiry = isRecord(value.inquiry) ? value.inquiry : null
  const report = publicReportFromUnknown(value.report)
  if (!inquiry || typeof inquiry.question !== 'string' || !report) return null
  return {
    id: value.id,
    runId: value.id,
    query: inquiry.question,
    report: report.markdown,
    sources: report.evidence,
    model: typeof value.model === 'string' ? value.model : 'unknown',
    createdAt: typeof value.created_at === 'string' ? value.created_at : report.completed_at,
    structuredReport: report,
    evaluation: evaluationFromUnknown(value.evaluation),
    metrics: metricsFromUnknown(value.metrics),
  }
}

export function mergeArchiveEntries(
  localEntries: ResearchArchiveEntry[],
  remoteEntries: ResearchArchiveEntry[],
): ResearchArchiveEntry[] {
  const merged = new Map<string, ResearchArchiveEntry>()
  for (const item of [...remoteEntries, ...localEntries]) {
    const key = item.runId || item.id
    const existing = merged.get(key)
    merged.set(key, existing ? { ...item, ...existing } : item)
  }
  return [...merged.values()]
    .sort((left, right) => Date.parse(right.createdAt) - Date.parse(left.createdAt))
    .slice(0, 50)
}

export type SourceFilter = 'all' | 'supports' | 'challenges' | 'primary'

export function filterSources(sources: Source[], filter: SourceFilter): Source[] {
  if (filter === 'all') return sources
  if (filter === 'primary') return sources.filter(source => source.is_primary)
  return sources.filter(source => source.relation === filter)
}

export function isStoredRunList(value: unknown): value is { items: StoredResearchRun[] } {
  return isRecord(value) && Array.isArray(value.items)
}
