'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { X } from 'lucide-react'
import SafeMarkdown from '@/components/SafeMarkdown'
import type { ResearchArchiveEntry } from '@/lib/types'

function metric(value: number | undefined, suffix = ''): string {
  return value === undefined ? '–' : `${value.toLocaleString('de-DE')}${suffix}`
}

function ComparisonColumn({ entry }: { entry: ResearchArchiveEntry }) {
  const report = entry.structuredReport
  return (
    <section className="min-w-0 rounded-xl border p-4" style={{ borderColor: 'hsl(var(--border))' }}>
      <h3 className="text-lg font-semibold">{report?.title || entry.query}</h3>
      <dl className="my-4 grid grid-cols-2 gap-2 text-sm">
        <div><dt className="opacity-60">Konfidenz</dt><dd>{report?.confidence || '–'}</dd></div>
        <div><dt className="opacity-60">Quellen</dt><dd>{metric(report?.evidence.length)}</dd></div>
        <div><dt className="opacity-60">Gegenbeleg-Quote</dt><dd>{metric(entry.evaluation ? Math.round(entry.evaluation.challenged_claim_ratio * 100) : undefined, ' %')}</dd></div>
        <div><dt className="opacity-60">Dauer</dt><dd>{metric(entry.metrics ? Math.round(entry.metrics.duration_ms / 1000) : undefined, ' s')}</dd></div>
        <div><dt className="opacity-60">Tokens</dt><dd>{metric(entry.metrics?.usage.total_tokens)}</dd></div>
        <div><dt className="opacity-60">Kosten</dt><dd>{entry.metrics?.usage.cost_usd == null ? '–' : `$${entry.metrics.usage.cost_usd.toFixed(4)}`}</dd></div>
      </dl>
      <div className="markdown-content max-h-[52vh] overflow-y-auto border-t pt-3" style={{ borderColor: 'hsl(var(--border))' }}>
        <SafeMarkdown>{entry.report}</SafeMarkdown>
      </div>
    </section>
  )
}

export default function ReportComparison({ entries, open, onClose }: {
  entries: ResearchArchiveEntry[]
  open: boolean
  onClose: () => void
}) {
  const dialogRef = useRef<HTMLDialogElement>(null)
  const eligible = useMemo(() => entries.filter(entry => entry.report), [entries])
  const [leftId, setLeftId] = useState('')
  const [rightId, setRightId] = useState('')

  useEffect(() => {
    const dialog = dialogRef.current
    if (!dialog) return
    if (open && !dialog.open) {
      setLeftId(current => current || eligible[0]?.id || '')
      setRightId(current => current || eligible[1]?.id || eligible[0]?.id || '')
      dialog.showModal()
    } else if (!open && dialog.open) {
      dialog.close()
    }
  }, [eligible, open])

  const left = eligible.find(entry => entry.id === leftId) || eligible[0]
  const right = eligible.find(entry => entry.id === rightId) || eligible[1] || eligible[0]
  const differentQuestions = left && right && left.query.trim() !== right.query.trim()

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby="comparison-title"
      onClose={onClose}
      onCancel={onClose}
      className="comparison-dialog w-[min(96vw,1280px)] max-w-none rounded-2xl border p-0 backdrop:bg-black/70"
      style={{ background: 'hsl(var(--card))', color: 'hsl(var(--foreground))', borderColor: 'hsl(var(--border))' }}
    >
      <div className="flex items-center justify-between border-b p-4" style={{ borderColor: 'hsl(var(--border))' }}>
        <div>
          <h2 id="comparison-title" className="text-xl font-semibold">Synthesen vergleichen</h2>
          <p className="text-sm opacity-60">Qualitätswerte und Berichte nebeneinander prüfen.</p>
        </div>
        <button type="button" onClick={onClose} className="action-button" aria-label="Vergleich schließen"><X className="h-5 w-5" /></button>
      </div>
      <div className="max-h-[88vh] overflow-y-auto p-4">
        <div className="mb-4 grid gap-3 md:grid-cols-2">
          {[{ value: leftId, set: setLeftId, label: 'Linker Bericht' }, { value: rightId, set: setRightId, label: 'Rechter Bericht' }].map(control => (
            <label key={control.label} className="text-sm font-medium">
              {control.label}
              <select value={control.value} onChange={event => control.set(event.target.value)} className="mt-1 w-full rounded-lg border bg-transparent p-2" style={{ borderColor: 'hsl(var(--border))' }}>
                {eligible.map(entry => <option key={entry.id} value={entry.id}>{entry.query}</option>)}
              </select>
            </label>
          ))}
        </div>
        {differentQuestions && (
          <p role="note" className="mb-4 rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm">
            Die Forschungsfragen unterscheiden sich. Kennzahlen sind deshalb nur eingeschränkt direkt vergleichbar.
          </p>
        )}
        {left && right && <div className="grid gap-4 lg:grid-cols-2"><ComparisonColumn entry={left} /><ComparisonColumn entry={right} /></div>}
      </div>
    </dialog>
  )
}
