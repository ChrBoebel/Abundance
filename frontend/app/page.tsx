/** Main Abundance research workspace. */
'use client'

import { useState, useEffect, useRef, useCallback, useId } from 'react'
import { useTheme } from 'next-themes'
import { Menu } from 'lucide-react'
import Image from 'next/image'
import ResearchMessage from '@/components/ResearchMessage'
import ResearchTrail from '@/components/ResearchTrail'
import InquiryComposer from '@/components/InquiryComposer'
import ResearchLibrary from '@/components/ResearchLibrary'
import { getHistory, saveEntry, deleteEntry } from '@/lib/history'
import type {
  ResearchArchiveEntry,
  ResearchEvent,
  ResearchMessageRecord,
  ResearchMode,
  ResearchPhase,
  ResearchStage,
  Source,
} from '@/lib/types'

const INITIAL_PHASES: ResearchPhase[] = [
  { id: 1, stage: 'inquiry', name: 'Frage schärfen', icon: 'clipboard', status: 'pending' },
  { id: 2, stage: 'planning', name: 'Rechercheplan entwickeln', icon: 'lightbulb', status: 'pending' },
  { id: 3, stage: 'evidence', name: 'Evidenz sammeln', icon: 'search', status: 'pending' },
  { id: 4, stage: 'review', name: 'Gegenbelege prüfen', icon: 'lightbulb', status: 'pending' },
  { id: 5, stage: 'synthesis', name: 'Synthese erstellen', icon: 'file-text', status: 'pending' },
]

const STAGE_TO_PHASE: Record<ResearchStage, number> = {
  inquiry: 1,
  planning: 2,
  evidence: 3,
  review: 4,
  synthesis: 5,
}

export default function ResearchWorkspace() {
  const stableSessionId = useId()
  const { theme, setTheme } = useTheme()
  const [mounted, setMounted] = useState(false)
  const [messages, setMessages] = useState<ResearchMessageRecord[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [showResearchTrail, setShowResearchTrail] = useState(false)
  const [phases, setPhases] = useState<ResearchPhase[]>(INITIAL_PHASES)
  const [sourceCount, setSourceCount] = useState(0)
  const [sources, setSources] = useState<Source[]>([])
  const [currentActivity, setCurrentActivity] = useState('')
  const [isCompleted, setIsCompleted] = useState(false)
  const [sessionId, setSessionId] = useState(`s-${stableSessionId.replaceAll(':', '')}`)
  const [streamingReport, setStreamingReport] = useState('')
  const [selectedModel, setSelectedModel] = useState<string>('mercury')
  const [selectedMode, setSelectedMode] = useState<ResearchMode>('balanced')
  const [backendConnected, setBackendConnected] = useState<boolean | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [historyEntries, setHistoryEntries] = useState<ResearchArchiveEntry[]>([])
  const [activeEntryId, setActiveEntryId] = useState<string | null>(null)

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const eventSourceRef = useRef<EventSource | null>(null)
  const pendingInquiryRef = useRef('')
  const sourcesRef = useRef<Source[]>([])

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      setMounted(true)
      const savedModel = localStorage.getItem('selectedModel')
      if (savedModel) {
        setSelectedModel(savedModel)
      }
      const savedMode = localStorage.getItem('selectedResearchMode') as ResearchMode | null
      if (savedMode && ['quick', 'balanced', 'thorough'].includes(savedMode)) {
        setSelectedMode(savedMode)
      }
      setHistoryEntries(getHistory())
      setSidebarOpen(window.innerWidth >= 1024)
    })
    return () => window.cancelAnimationFrame(frame)
  }, [])

  useEffect(() => () => eventSourceRef.current?.close(), [])

  useEffect(() => {
    let active = true
    const checkBackend = async () => {
      try {
        const response = await fetch('/api/health', { cache: 'no-store' })
        const health = await response.json()
        if (active) setBackendConnected(health.backend === 'healthy')
      } catch {
        if (active) setBackendConnected(false)
      }
    }
    void checkBackend()
    const interval = window.setInterval(checkBackend, 30000)
    return () => {
      active = false
      window.clearInterval(interval)
    }
  }, [])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const resetResearchState = () => {
    setPhases(INITIAL_PHASES)
    setSourceCount(0)
    setSources([])
    sourcesRef.current = []
    setCurrentActivity('')
    setIsCompleted(false)
    setShowResearchTrail(false)
    setStreamingReport('')
  }

  const activateStage = (stage: ResearchStage) => {
    const activePhase = STAGE_TO_PHASE[stage]
    setPhases(prev => prev.map(phase => ({
      ...phase,
      status: phase.id < activePhase
        ? 'completed'
        : phase.id === activePhase
          ? 'running'
          : phase.status,
    })))
  }

  const handleSelectEntry = useCallback((entry: ResearchArchiveEntry) => {
    if (isStreaming) return
    setActiveEntryId(entry.id)
    setMessages([
      { role: 'user', content: entry.query },
      { role: 'agent', content: entry.report },
    ])
    setSources(entry.sources)
    sourcesRef.current = entry.sources
    setSourceCount(entry.sources.length)
    setIsCompleted(true)
    setShowResearchTrail(false)
    setStreamingReport('')
    setPhases(INITIAL_PHASES.map(p => ({ ...p, status: 'completed' as const })))
    setCurrentActivity('')
    // Close sidebar on mobile
    if (window.innerWidth < 1024) {
      setSidebarOpen(false)
    }
  }, [isStreaming])

  const handleDeleteEntry = useCallback((id: string) => {
    deleteEntry(id)
    setHistoryEntries(getHistory())
    if (activeEntryId === id) {
      setActiveEntryId(null)
      setMessages([])
      resetResearchState()
    }
  }, [activeEntryId])

  const handleNewResearch = useCallback(() => {
    if (isStreaming) return
    setActiveEntryId(null)
    setMessages([])
    resetResearchState()
    setSessionId(`s-${crypto.randomUUID()}`)
    // Close sidebar on mobile
    if (window.innerWidth < 1024) {
      setSidebarOpen(false)
    }
  }, [isStreaming])

  const extractCitedSources = (reportContent: string, allSources: Source[]): Source[] => {
    try {
      // Extract the Sources section from the report
      const sourcesMatch = reportContent.match(/###\s+(Sources|Quellen)\s*\n([\s\S]+?)(\n###|$)/i)
      if (!sourcesMatch) return []

      const sourcesSection = sourcesMatch[2]

      // Extract citation lines like "[1] Title: URL" or "[1] Title - URL"
      const citationRegex = /\[(\d+)\]\s*(.+?)(?::\s*|\s+-\s*)(https?:\/\/[^\s\n]+)/g
      const citedSourcesMap = new Map<string, Source>()

      let match
      while ((match = citationRegex.exec(sourcesSection)) !== null) {
        const url = match[3].trim()
        const title = match[2].trim()

        // Try to find matching source from allSources based on URL
        const matchingSource = allSources.find(s => s.url === url)
        if (matchingSource) {
          citedSourcesMap.set(url, matchingSource)
        } else {
          // If not found in allSources, create a new entry
          citedSourcesMap.set(url, { title, url })
        }
      }

      return Array.from(citedSourcesMap.values())
    } catch (error) {
      console.error('Error extracting cited sources:', error)
      return []
    }
  }

  const handleSSEMessage = (event: MessageEvent) => {
    try {
      const data: ResearchEvent = JSON.parse(event.data)

      if (data.type === 'run.accepted') {
        setShowResearchTrail(true)
      } else if (data.stage) {
        setShowResearchTrail(true)
        activateStage(data.stage)
        if (data.message) setCurrentActivity(data.message)
      }

      if (data.type === 'evidence.search.started') {
        const queryPayload = data.data?.query
        if (queryPayload && typeof queryPayload === 'object') {
          const queryObject = queryPayload as { queries?: unknown[]; query?: unknown }
          const query = Array.isArray(queryObject.queries)
            ? queryObject.queries[0]
            : queryObject.query
          if (typeof query === 'string') {
            const shortQuery = query.length > 60 ? `${query.substring(0, 60)}...` : query
            setCurrentActivity(`Suche nach „${shortQuery}“`)
          }
        }
      } else if (data.type === 'evidence.discovered') {
        const result = data.data?.result
        if (typeof result === 'string') {
            const sourceMatches = result.match(/--- SOURCE \d+:/g)
            if (sourceMatches && sourceMatches.length > 0) {
              const newSourceCount = sourceMatches.length
              setSourceCount(prev => prev + newSourceCount)

              const titleRegex = /--- SOURCE \d+: (.+?) ---/g
              const urlRegex = /URL: (.+?)$/gm
              const titles: string[] = []
              const urls: string[] = []

              let match
              while ((match = titleRegex.exec(result)) !== null) {
                titles.push(match[1].trim())
              }
              while ((match = urlRegex.exec(result)) !== null) {
                urls.push(match[1].trim())
              }

              const newSources: Source[] = []
              for (let i = 0; i < Math.min(titles.length, urls.length); i++) {
                const title = titles[i]
                const url = urls[i]
                const shortTitle = title.length > 80 ? title.substring(0, 80) + '...' : title
                newSources.push({ title: shortTitle, url })
              }
              setSources(prev => {
                const next = [...prev, ...newSources]
                sourcesRef.current = next
                return next
              })
            } else {
              setSourceCount(prev => prev + 1)
              setSources(prev => {
                const next = [...prev, { title: 'Unbekannte Quelle', url: '#' }]
                sourcesRef.current = next
                return next
              })
            }
        }
      } else if (data.type === 'report.delta' && data.data?.chunk) {
        setStreamingReport(prev => prev + data.data!.chunk)
      } else if (data.type === 'report.completed' && data.data?.content) {
        const report = data.data.content
        setMessages(prev => [...prev, { role: 'agent', content: report }])
        setStreamingReport('')
        setIsCompleted(true)
        setPhases(prev => prev.map(phase => ({ ...phase, status: 'completed' })))

        const cited = extractCitedSources(report, sourcesRef.current)

        if (pendingInquiryRef.current) {
          const entry: ResearchArchiveEntry = {
            id: `h-${crypto.randomUUID()}`,
            query: pendingInquiryRef.current,
            report,
            sources: cited.length > 0 ? cited : sourcesRef.current,
            model: selectedModel,
            createdAt: new Date().toISOString(),
          }
          saveEntry(entry)
          setActiveEntryId(entry.id)
          setHistoryEntries(getHistory())
        }
      } else if (data.type === 'run.completed') {
        setIsCompleted(true)
        setIsStreaming(false)
        eventSourceRef.current?.close()
      } else if (data.type === 'run.failed') {
        const error = data.data?.error || data.message || 'Unbekannter Fehler'
        setMessages(prev => [...prev, { role: 'agent', content: `❌ Fehler: ${error}` }])
        setIsStreaming(false)
        eventSourceRef.current?.close()
      }
    } catch (err) {
      console.error('Parse error:', err)
    }
  }

  const handleSendMessage = async (message: string) => {
    pendingInquiryRef.current = message
    setActiveEntryId(null)
    setMessages(prev => [...prev, { role: 'user', content: message }])
    resetResearchState()
    setIsStreaming(true)

    const url = `/api/research-runs/stream?session_id=${sessionId}&inquiry=${encodeURIComponent(message)}&model=${selectedModel}&mode=${selectedMode}`
    const es = new EventSource(url)

    es.onmessage = handleSSEMessage
    es.onerror = () => {
      console.error('EventSource error')
      setIsStreaming(false)
      es.close()
    }

    eventSourceRef.current = es
  }

  return (
    <div className="flex h-full overflow-hidden">
      <ResearchLibrary
        isOpen={sidebarOpen}
        entries={historyEntries}
        activeEntryId={activeEntryId}
        onSelectEntry={handleSelectEntry}
        onDeleteEntry={handleDeleteEntry}
        onNewResearch={handleNewResearch}
        onClose={() => setSidebarOpen(false)}
        mounted={mounted}
        theme={theme}
        onToggleTheme={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
        selectedModel={selectedModel}
        onSelectModel={(model) => {
          setSelectedModel(model)
          localStorage.setItem('selectedModel', model)
        }}
        selectedMode={selectedMode}
        onSelectMode={(mode) => {
          setSelectedMode(mode)
          localStorage.setItem('selectedResearchMode', mode)
        }}
        backendConnected={backendConnected}
      />

      <div className="flex flex-col flex-1 min-w-0 relative">
      {/* Sidebar toggle (visible when sidebar is closed) */}
      {!sidebarOpen && (
        <button
          onClick={() => setSidebarOpen(true)}
          className="absolute top-3 left-3 z-10 p-2 rounded-lg transition"
          style={{ background: 'hsl(var(--card) / 0.8)', color: 'hsl(var(--foreground) / 0.7)' }}
          title="Verlauf öffnen"
        >
          <Menu className="w-5 h-5" />
        </button>
      )}

      {/* Research workspace */}
      <div className="flex-1 overflow-hidden max-w-6xl mx-auto w-full">
        <div className="h-full overflow-y-auto p-4 space-y-4">
          {messages.length === 0 ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-center space-y-4 max-w-md">
                <div
                  className="w-20 h-20 rounded-2xl mx-auto flex items-center justify-center p-0 overflow-visible"
                  style={{ background: 'linear-gradient(135deg, hsl(var(--primary)) 0%, hsl(var(--primary) / 0.8) 100%)', boxShadow: '0 8px 32px hsl(var(--primary) / 0.4), 0 0 60px hsl(var(--primary) / 0.2)' }}
                >
                  <Image src="/abundance-mark.svg" alt="Abundance Logo" width={80} height={80} className="w-[180%] h-[180%]" style={{ filter: 'drop-shadow(0 4px 8px rgba(0,0,0,0.3))' }} />
                </div>
                <h2 className="text-3xl md:text-4xl lg:text-5xl font-semibold abundance-title">Abundance</h2>
                <p className="text-base md:text-lg" style={{ color: 'hsl(var(--foreground) / 0.7)' }}>
                  Verwandle komplexe Fragen in prüfbare Erkenntnisse – mit Evidenz, Gegenargumenten und nachvollziehbaren Quellen.
                </p>
                <div className="grid grid-cols-2 gap-2 pt-2 text-xs" style={{ color: 'hsl(var(--foreground) / 0.55)' }}>
                  {['Frage schärfen', 'Evidenz sammeln', 'Gegenbelege prüfen', 'Synthese erstellen'].map(step => (
                    <div key={step} className="rounded-lg border px-3 py-2" style={{ borderColor: 'hsl(var(--border))', background: 'hsl(var(--card) / 0.7)' }}>
                      {step}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <>
              {messages.map((msg, idx) => {
                // Show user messages and agent messages before research status
                if (msg.role === 'user') {
                  return <ResearchMessage key={idx} message={msg} />
                }
                // Don't show agent message yet if research is still showing
                return null
              })}
              {showResearchTrail && (
                <ResearchTrail
                  phases={phases}
                  sourceCount={sourceCount}
                  sources={sources}
                  currentActivity={currentActivity}
                  isCompleted={isCompleted}
                />
              )}
              {streamingReport && (
                <ResearchMessage message={{ role: 'agent', content: streamingReport }} />
              )}
              {messages.map((msg, idx) => {
                // Show agent messages after research status
                if (msg.role === 'agent') {
                  return <ResearchMessage key={`agent-${idx}`} message={msg} />
                }
                return null
              })}
              <div ref={messagesEndRef} />
            </>
          )}
        </div>
      </div>

      {/* Input Area */}
      <InquiryComposer onSubmit={handleSendMessage} isStreaming={isStreaming} />
      </div>
    </div>
  )
}
