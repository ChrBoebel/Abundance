import { describe, expect, it } from 'vitest'
import {
  archiveEntryFromStoredRun,
  filterSources,
  mergeArchiveEntries,
  publicReportFromUnknown,
} from './research-records'
import type { Source } from './types'

const report = {
  inquiry_id: 'inq-1',
  title: 'Evidence review',
  summary: 'The result remains conditional.',
  confidence: 'medium',
  claims: [{
    id: 'claim-1',
    statement: 'The proposition is supported.',
    evidence_ids: ['ev-1'],
    counter_evidence: [],
    confidence: 'medium',
    uncertainty_notes: [],
  }],
  evidence: [{
    id: 'ev-1',
    title: 'Official source',
    url: 'https://example.org/source',
    relation: 'supports',
    source_kind: 'primary',
    is_primary: true,
    published_at: null,
  }],
  open_questions: [],
  markdown: '# Evidence review',
  completed_at: '2026-08-25T10:00:00Z',
} as const

describe('research record adapters', () => {
  it('accepts the public report contract and rejects unsafe evidence URLs', () => {
    expect(publicReportFromUnknown(report)?.evidence).toHaveLength(1)
    expect(publicReportFromUnknown({
      ...report,
      evidence: [{ ...report.evidence[0], url: 'javascript:alert(1)' }],
    })?.evidence).toEqual([])
  })

  it('maps completed stored runs into canonical archive entries', () => {
    const entry = archiveEntryFromStoredRun({
      id: 'run-123',
      inquiry: { question: 'What does the evidence show?' },
      model: 'mercury',
      mode: 'balanced',
      status: 'completed',
      report,
      created_at: '2026-08-25T09:00:00Z',
    })

    expect(entry?.runId).toBe('run-123')
    expect(entry?.report).toBe('# Evidence review')
    expect(entry?.sources[0].is_primary).toBe(true)
  })

  it('filters source relations and merges by stable run ID', () => {
    const sources: Source[] = [
      report.evidence[0],
      { ...report.evidence[0], id: 'ev-2', relation: 'challenges' as const, is_primary: false },
    ]
    expect(filterSources(sources, 'primary')).toHaveLength(1)
    expect(filterSources(sources, 'challenges')[0].id).toBe('ev-2')

    const local = [{ id: 'local', runId: 'run-1', query: 'Q', report: 'local', sources: [], model: 'mercury', createdAt: '2026-08-25T10:00:00Z' }]
    const remote = [{ ...local[0], id: 'run-1', report: 'remote' }]
    expect(mergeArchiveEntries(local, remote)).toHaveLength(1)
    expect(mergeArchiveEntries(local, remote)[0].report).toBe('remote')
  })
})
