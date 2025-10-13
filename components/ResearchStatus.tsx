/**
 * Research Status Component
 */
'use client'

import { useState } from 'react'
import { Loader2, CheckCircle, BookOpen, Clipboard, Search, Lightbulb, FileText, Circle, ExternalLink } from 'lucide-react'
import type { ResearchPhase, Source } from '@/lib/types'

interface ResearchStatusProps {
  phases: ResearchPhase[]
  sourceCount: number
  sources: Source[]
  citedSources: Source[]
  currentActivity: string
  isCompleted: boolean
}

export default function ResearchStatus({ phases, sourceCount, sources, citedSources, currentActivity, isCompleted }: ResearchStatusProps) {
  const [expanded, setExpanded] = useState(false)

  const currentPhase = phases.find(p => p.status === 'running')
  const phaseIcons = {
    'clipboard': Clipboard,
    'search': Search,
    'lightbulb': Lightbulb,
    'file-text': FileText,
  }

  const PhaseIcon = currentPhase ? phaseIcons[currentPhase.icon as keyof typeof phaseIcons] : Clipboard

  return (
    <div className="message-bubble flex justify-start mb-4">
      <div className="rounded-2xl px-4 py-3 max-w-5xl mr-4" style={{ background: 'hsl(var(--card))', border: '2px solid hsl(var(--border))' }}>
        <div className="flex items-center gap-3 mb-2">
          {isCompleted ? (
            <CheckCircle className="w-5 h-5" style={{ color: '#10b981' }} />
          ) : (
            <Loader2 className="w-5 h-5 animate-spin" style={{ color: 'hsl(var(--primary))' }} />
          )}
          <h3 className="text-lg font-semibold" style={{ color: isCompleted ? '#10b981' : 'hsl(var(--primary))' }}>
            {isCompleted ? 'Recherche abgeschlossen' : 'Recherchiere...'}
          </h3>
        </div>

        <div className="text-sm mb-1 flex items-center gap-2" style={{ color: 'hsl(var(--foreground) / 0.8)' }}>
          {PhaseIcon && <PhaseIcon className="w-4 h-4" />}
          <span>{currentPhase ? currentPhase.name : 'Plane Recherche-Strategie...'}</span>
        </div>

        <div className="text-sm font-semibold mb-2 flex items-center gap-2" style={{ color: 'hsl(var(--primary))' }}>
          <BookOpen className="w-4 h-4" />
          <span>{sourceCount} {sourceCount !== 1 ? 'Quellen' : 'Quelle'} {isCompleted ? 'analysiert' : 'gefunden'}</span>
        </div>

        {currentActivity && (
          <div className="text-xs mb-3" style={{ color: 'hsl(var(--foreground) / 0.6)' }}>
            ↳ Aktuell: {currentActivity}
          </div>
        )}

        <button
          onClick={() => setExpanded(!expanded)}
          className="text-xs px-3 py-1 rounded transition"
          style={{ background: 'hsl(var(--muted))', color: 'hsl(var(--foreground))' }}
        >
          Details {expanded ? 'verbergen ▲' : 'anzeigen ▼'}
        </button>

        {expanded && (
          <div className="mt-3 pt-3 space-y-3" style={{ borderTop: '1px solid hsl(var(--border))' }}>
            <div>
              <div className="text-sm font-semibold mb-2">Recherche-Fortschritt:</div>
              <div className="space-y-1">
                {phases.map((phase) => {
                  const Icon = phase.status === 'completed' ? CheckCircle :
                             phase.status === 'running' ? Loader2 : Circle
                  const color = phase.status === 'completed' ? '#10b981' :
                               phase.status === 'running' ? 'hsl(var(--primary))' : 'hsl(var(--foreground) / 0.4)'
                  const PhaseIconComponent = phaseIcons[phase.icon as keyof typeof phaseIcons]

                  return (
                    <div key={phase.id} className="flex items-center gap-2" style={{ color }}>
                      <Icon className={`w-4 h-4 ${phase.status === 'running' ? 'animate-spin' : ''}`} />
                      {PhaseIconComponent && <PhaseIconComponent className="w-4 h-4" />}
                      <span className="text-sm">{phase.name}</span>
                    </div>
                  )
                })}
              </div>
            </div>

            {sources.length > 0 && (
              <div className="space-y-3">
                {/* All Found Sources */}
                <div>
                  <div className="text-sm font-semibold mb-2">Gefundene Quellen ({sources.length}):</div>
                  <div className="space-y-1 text-xs max-h-48 overflow-y-auto">
                    {sources.map((source, idx) => (
                      <div key={idx} className="flex items-start gap-2" style={{ color: 'hsl(var(--foreground) / 0.7)' }}>
                        <ExternalLink className="w-4 h-4 mt-0.5 flex-shrink-0" />
                        <a
                          href={source.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="hover:underline transition-colors"
                          style={{ color: 'hsl(var(--primary))', wordBreak: 'break-word' }}
                        >
                          {source.title}
                        </a>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Cited Sources (only shown after research completion) */}
                {isCompleted && citedSources.length > 0 && (
                  <div>
                    <div className="text-sm font-semibold mb-2" style={{ color: 'hsl(var(--primary))' }}>
                      Zitierte Quellen ({citedSources.length}):
                    </div>
                    <div className="space-y-1 text-xs max-h-48 overflow-y-auto">
                      {citedSources.map((source, idx) => (
                        <div key={idx} className="flex items-start gap-2" style={{ color: 'hsl(var(--foreground) / 0.7)' }}>
                          <ExternalLink className="w-4 h-4 mt-0.5 flex-shrink-0" />
                          <a
                            href={source.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="hover:underline transition-colors"
                            style={{ color: 'hsl(var(--primary))', wordBreak: 'break-word' }}
                          >
                            {source.title}
                          </a>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
