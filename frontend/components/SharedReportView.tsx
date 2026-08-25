'use client'

import { useEffect, useState } from 'react'
import Image from 'next/image'
import SafeMarkdown from '@/components/SafeMarkdown'
import { publicReportFromUnknown } from '@/lib/research-records'
import type { PublicResearchReport } from '@/lib/types'

export default function SharedReportView({ token }: { token: string }) {
  const [report, setReport] = useState<PublicResearchReport | null>(null)
  const [status, setStatus] = useState('Lade geteilte Recherche…')

  useEffect(() => {
    const controller = new AbortController()
    const load = async () => {
      try {
        const response = await fetch(`/api/shared/${encodeURIComponent(token)}`, {
          cache: 'no-store',
          signal: controller.signal,
        })
        const payload = await response.json() as { report?: unknown }
        const parsed = publicReportFromUnknown(payload.report)
        if (!response.ok || !parsed) throw new Error('not found')
        setReport(parsed)
        setStatus('')
      } catch (error) {
        if (error instanceof Error && error.name === 'AbortError') return
        setStatus('Diese Freigabe ist ungültig, nicht mehr verfügbar oder der Dienst ist offline.')
      }
    }
    void load()
    return () => controller.abort()
  }, [token])

  return (
    <main className="min-h-full px-4 py-8 md:py-12">
      <div className="mx-auto max-w-5xl">
        <header className="mb-6 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl" style={{ background: 'hsl(var(--primary))' }}>
            <Image src="/abundance-mark.svg" alt="" width={60} height={60} loading="eager" />
          </div>
          <div>
            <div className="abundance-title text-xl">Abundance</div>
            <div className="text-xs" style={{ color: 'hsl(var(--foreground) / 0.55)' }}>Geteilte, schreibgeschützte Recherche</div>
          </div>
        </header>
        {status && (
          <div role="status" className="rounded-xl border p-6" style={{ borderColor: 'hsl(var(--border))', background: 'hsl(var(--card))' }}>
            {status}
          </div>
        )}
        {report && (
          <article className="markdown-content report-content rounded-xl border px-5 py-6 md:px-8" style={{ borderColor: 'hsl(var(--border))', background: 'hsl(var(--card))' }}>
            <SafeMarkdown>{report.markdown}</SafeMarkdown>
          </article>
        )}
      </div>
    </main>
  )
}
