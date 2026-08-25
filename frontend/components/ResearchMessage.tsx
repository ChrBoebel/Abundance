/** Render an inquiry or a research report without trusting generated HTML. */
'use client'

import { useRef, useState } from 'react'
import { Check, Download, Printer, Share2, ThumbsDown, ThumbsUp } from 'lucide-react'
import SafeMarkdown from '@/components/SafeMarkdown'
import type { ResearchMessageRecord } from '@/lib/types'

interface ResearchMessageProps {
  message: ResearchMessageRecord
  isStreaming?: boolean
}

export default function ResearchMessage({ message, isStreaming = false }: ResearchMessageProps) {
  const reportRef = useRef<HTMLDivElement>(null)
  const [shareStatus, setShareStatus] = useState('')
  const [feedback, setFeedback] = useState<Record<string, number>>({})
  const [feedbackStatus, setFeedbackStatus] = useState('')

  const exportMarkdown = () => {
    const blob = new Blob([message.content], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    const baseName = message.report?.title || 'abundance-recherche'
    anchor.href = url
    anchor.download = `${baseName.toLowerCase().replace(/[^a-z0-9äöüß]+/gi, '-').replace(/^-|-$/g, '').slice(0, 80) || 'abundance-recherche'}.md`
    anchor.click()
    URL.revokeObjectURL(url)
  }

  const printReport = () => {
    reportRef.current?.classList.add('report-print-target')
    document.body.classList.add('printing-report')
    const cleanup = () => {
      document.body.classList.remove('printing-report')
      reportRef.current?.classList.remove('report-print-target')
      window.removeEventListener('afterprint', cleanup)
    }
    window.addEventListener('afterprint', cleanup)
    window.print()
  }

  const shareReport = async () => {
    if (!message.runId) return
    setShareStatus('Freigabelink wird erstellt…')
    try {
      const response = await fetch(`/api/research-runs/${message.runId}/shares`, { method: 'POST' })
      const payload = await response.json() as { url?: string }
      if (!response.ok || !payload.url) throw new Error('share failed')
      const url = new URL(payload.url, window.location.origin).toString()
      await navigator.clipboard.writeText(url)
      setShareStatus('Link kopiert. Jeder mit diesem Link kann den Bericht lesen.')
    } catch {
      setShareStatus('Der Freigabelink konnte nicht erstellt oder kopiert werden.')
    }
  }

  const rateClaim = async (claimId: string, rating: number) => {
    if (!message.runId) return
    const previous = feedback[claimId]
    setFeedback(current => ({ ...current, [claimId]: rating }))
    setFeedbackStatus('Feedback wird gespeichert…')
    try {
      const response = await fetch(`/api/research-runs/${message.runId}/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ claim_id: claimId, rating }),
      })
      if (!response.ok) throw new Error('feedback failed')
      setFeedbackStatus('Feedback gespeichert.')
    } catch {
      setFeedback(current => {
        const next = { ...current }
        if (previous === undefined) delete next[claimId]
        else next[claimId] = previous
        return next
      })
      setFeedbackStatus('Feedback konnte nicht gespeichert werden.')
    }
  }

  if (message.role === 'user') {
    return (
      <div className="message-bubble flex justify-end">
        <div
          className="rounded-2xl px-4 py-3 max-w-3xl ml-16"
          style={{ background: 'hsl(var(--primary))', color: 'white' }}
        >
          {message.content}
        </div>
      </div>
    )
  }

  return (
    <div className="message-bubble flex justify-start">
      <div
        ref={reportRef}
        className={`markdown-content rounded-lg px-6 py-5 w-full report-content ${isStreaming ? 'streaming-cursor' : ''}`}
        style={{
          background: 'hsl(var(--card))',
          color: 'hsl(var(--foreground))',
          border: '1px solid hsl(var(--border))',
        }}
      >
        {message.report && (
          <div className="report-actions no-print mb-5 flex flex-wrap items-center gap-2 border-b pb-4" style={{ borderColor: 'hsl(var(--border))' }}>
            <button type="button" onClick={exportMarkdown} className="action-button"><Download className="w-4 h-4" /> Markdown</button>
            <button type="button" onClick={printReport} className="action-button"><Printer className="w-4 h-4" /> Drucken / PDF</button>
            {message.runId && (
              <button type="button" onClick={shareReport} className="action-button"><Share2 className="w-4 h-4" /> Link teilen</button>
            )}
            <span className="text-xs" role="status" aria-live="polite" style={{ color: 'hsl(var(--foreground) / 0.6)' }}>{shareStatus}</span>
          </div>
        )}
        <SafeMarkdown>{message.content}</SafeMarkdown>
        {message.report && message.runId && message.report.claims.length > 0 && (
          <details className="no-print mt-6 rounded-xl border p-4" style={{ borderColor: 'hsl(var(--border))' }}>
            <summary className="cursor-pointer font-semibold">Aussagen bewerten</summary>
            <p className="mt-2 text-sm" style={{ color: 'hsl(var(--foreground) / 0.65)' }}>
              Dein Feedback hilft, die Qualität einzelner Schlussfolgerungen zu prüfen.
            </p>
            <div className="mt-4 space-y-4">
              {message.report.claims.map((claim, index) => (
                <div key={claim.id} className="rounded-lg p-3" style={{ background: 'hsl(var(--muted) / 0.55)' }}>
                  <p className="mb-2 text-sm"><strong>Aussage {index + 1}:</strong> {claim.statement}</p>
                  <div className="flex flex-wrap gap-2" role="group" aria-label={`Aussage ${index + 1} bewerten`}>
                    {[
                      { rating: 1, label: 'Hilfreich', Icon: ThumbsUp },
                      { rating: 0, label: 'Neutral', Icon: Check },
                      { rating: -1, label: 'Nicht hilfreich', Icon: ThumbsDown },
                    ].map(({ rating, label, Icon }) => (
                      <button
                        key={rating}
                        type="button"
                        onClick={() => void rateClaim(claim.id, rating)}
                        aria-pressed={feedback[claim.id] === rating}
                        className="action-button"
                        style={feedback[claim.id] === rating ? { borderColor: 'hsl(var(--primary))', color: 'hsl(var(--primary))' } : undefined}
                      >
                        <Icon className="w-4 h-4" /> {label}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-3 text-xs" role="status" aria-live="polite">{feedbackStatus}</div>
          </details>
        )}
      </div>
    </div>
  )
}
