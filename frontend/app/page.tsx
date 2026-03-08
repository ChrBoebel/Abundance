/**
 * Main Chat Page
 */
'use client'

import { useState, useEffect, useRef, useCallback } from 'react'
import { useTheme } from 'next-themes'
import { Menu } from 'lucide-react'
import Image from 'next/image'
import ChatMessage from '@/components/ChatMessage'
import ResearchStatus from '@/components/ResearchStatus'
import ChatInput from '@/components/ChatInput'
import HistorySidebar from '@/components/HistorySidebar'
import { getHistory, saveEntry, deleteEntry } from '@/lib/history'
import type { Message, ResearchPhase, Source, SSEEvent, HistoryEntry } from '@/lib/types'

const INITIAL_PHASES: ResearchPhase[] = [
  { id: 1, name: 'Recherche vorbereiten', icon: 'clipboard', status: 'pending' },
  { id: 2, name: 'Quellen durchsuchen', icon: 'search', status: 'pending' },
  { id: 3, name: 'Informationen zusammenführen', icon: 'lightbulb', status: 'pending' },
  { id: 4, name: 'Bericht schreiben', icon: 'file-text', status: 'pending' },
]

const STEP_TO_PHASE: Record<string, number> = {
  'clarify_with_user': 1,
  'write_research_brief': 1,
  'research_supervisor': 2,
  'supervisor': 2,
  'supervisor_tools': 2,
  'researcher': 2,
  'researcher_tools': 2,
  'compress_research': 3,
  'final_report_generation': 4,
}

export default function ChatPage() {
  const { theme, setTheme } = useTheme()
  const [mounted, setMounted] = useState(false)
  const [messages, setMessages] = useState<Message[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [showResearchStatus, setShowResearchStatus] = useState(false)
  const [phases, setPhases] = useState<ResearchPhase[]>(INITIAL_PHASES)
  const [sourceCount, setSourceCount] = useState(0)
  const [sources, setSources] = useState<Source[]>([])
  const [citedSources, setCitedSources] = useState<Source[]>([])
  const [currentActivity, setCurrentActivity] = useState('')
  const [isCompleted, setIsCompleted] = useState(false)
  const [sessionId, setSessionId] = useState(`s-${Date.now().toString(36)}`)
  const [currentJobId, setCurrentJobId] = useState<string | null>(null)
  const [eventSource, setEventSource] = useState<EventSource | null>(null)
  const [streamingReport, setStreamingReport] = useState('')
  const [selectedModel, setSelectedModel] = useState<string>('mercury')
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [historyEntries, setHistoryEntries] = useState<HistoryEntry[]>([])
  const [activeEntryId, setActiveEntryId] = useState<string | null>(null)

  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setMounted(true)
    const savedModel = localStorage.getItem('selectedModel')
    if (savedModel) {
      setSelectedModel(savedModel)
    }
    setHistoryEntries(getHistory())
    // Open sidebar by default on desktop
    if (window.innerWidth >= 1024) {
      setSidebarOpen(true)
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
    setCitedSources([])
    setCurrentActivity('')
    setIsCompleted(false)
    setShowResearchStatus(false)
    setStreamingReport('')
  }

  const updatePhase = (phaseId: number, status: 'pending' | 'running' | 'completed') => {
    setPhases(prev => prev.map(p => p.id === phaseId ? { ...p, status } : p))
  }

  // Auto-save completed research to history
  useEffect(() => {
    if (isCompleted && !isStreaming && !activeEntryId) {
      const agentMsg = messages.find(m => m.role === 'agent')
      const userMsg = messages.find(m => m.role === 'user')
      if (agentMsg && userMsg) {
        const entry: HistoryEntry = {
          id: `h-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`,
          query: userMsg.content,
          report: agentMsg.content,
          sources: citedSources.length > 0 ? citedSources : sources,
          model: selectedModel,
          createdAt: new Date().toISOString(),
        }
        saveEntry(entry)
        setActiveEntryId(entry.id)
        setHistoryEntries(getHistory())
      }
    }
  }, [isCompleted, isStreaming]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleSelectEntry = useCallback((entry: HistoryEntry) => {
    if (isStreaming) return
    setActiveEntryId(entry.id)
    setMessages([
      { role: 'user', content: entry.query },
      { role: 'agent', content: entry.report },
    ])
    setSources(entry.sources)
    setCitedSources(entry.sources)
    setSourceCount(entry.sources.length)
    setIsCompleted(true)
    setShowResearchStatus(false)
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
    setSessionId(`s-${Date.now().toString(36)}`)
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
      const data: SSEEvent = JSON.parse(event.data)

      if (data.type === 'job_started') {
        setCurrentJobId(data.job_id)
      } else if (data.type === 'thinking') {
        setShowResearchStatus(true)
      } else if (data.type === 'step_start') {
        setShowResearchStatus(true)
        const stepName = data.step_name || data.name
        const phaseId = STEP_TO_PHASE[stepName]
        if (phaseId) {
          updatePhase(phaseId, 'running')
        }
      } else if (data.type === 'step_complete') {
        const stepName = data.step_name || data.name
        const phaseId = STEP_TO_PHASE[stepName]
        if (phaseId) {
          updatePhase(phaseId, 'completed')
        }
      } else if (data.type === 'tool_call_start') {
        setShowResearchStatus(true)
        if (['tavily_search', 'web_search', 'tavily_search_results_json'].includes(data.name)) {
          let query = ''
          if (data.args && typeof data.args === 'object') {
            if (Array.isArray(data.args.queries) && data.args.queries.length > 0) {
              query = data.args.queries[0]
            } else if (data.args.query) {
              query = data.args.query
            }
          }
          if (query) {
            const shortQuery = query.length > 60 ? query.substring(0, 60) + '...' : query
            setCurrentActivity(`"${shortQuery}"`)
          }
        }
      } else if (data.type === 'tool_call_complete') {
        if (['tavily_search', 'web_search', 'tavily_search_results_json'].includes(data.name)) {
          if (data.result && typeof data.result === 'string') {
            const sourceMatches = data.result.match(/--- SOURCE \d+:/g)
            if (sourceMatches && sourceMatches.length > 0) {
              const newSourceCount = sourceMatches.length
              setSourceCount(prev => prev + newSourceCount)

              const titleRegex = /--- SOURCE \d+: (.+?) ---/g
              const urlRegex = /URL: (.+?)$/gm
              const titles: string[] = []
              const urls: string[] = []

              let match
              while ((match = titleRegex.exec(data.result)) !== null) {
                titles.push(match[1].trim())
              }
              while ((match = urlRegex.exec(data.result)) !== null) {
                urls.push(match[1].trim())
              }

              const newSources: Source[] = []
              for (let i = 0; i < Math.min(titles.length, urls.length); i++) {
                const title = titles[i]
                const url = urls[i]
                const shortTitle = title.length > 80 ? title.substring(0, 80) + '...' : title
                newSources.push({ title: shortTitle, url })
              }
              setSources(prev => [...prev, ...newSources])
            } else {
              setSourceCount(prev => prev + 1)
              setSources(prev => [...prev, { title: 'Unbekannte Quelle', url: '#' }])
            }
          }
        }
      } else if (data.type === 'report_stream') {
        setStreamingReport(prev => prev + data.chunk)
      } else if (data.type === 'agent_message') {
        setMessages(prev => [...prev, { role: 'agent', content: data.content }])
        setStreamingReport('')
        setIsCompleted(true)
        phases.forEach(phase => updatePhase(phase.id, 'completed'))

        // Extract cited sources from the final report
        const cited = extractCitedSources(data.content, sources)
        setCitedSources(cited)
      } else if (data.type === 'done') {
        setIsCompleted(true)
        setIsStreaming(false)
        setCurrentJobId(null)
        eventSource?.close()
      } else if (data.type === 'error') {
        setMessages(prev => [...prev, { role: 'agent', content: `❌ Fehler: ${data.error}` }])
        setIsStreaming(false)
        setCurrentJobId(null)
        eventSource?.close()
      }
    } catch (err) {
      console.error('Parse error:', err)
    }
  }

  const handleSendMessage = async (message: string) => {
    setActiveEntryId(null)
    setMessages(prev => [...prev, { role: 'user', content: message }])
    resetResearchState()
    setIsStreaming(true)

    const url = `/api/chat/stream?thread_id=${sessionId}&message=${encodeURIComponent(message)}&model=${selectedModel}`
    const es = new EventSource(url)

    es.onmessage = handleSSEMessage
    es.onerror = () => {
      console.error('EventSource error')
      setIsStreaming(false)
      es.close()
    }

    setEventSource(es)
  }

  return (
    <div className="flex h-full overflow-hidden">
      <HistorySidebar
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

      {/* Main Chat Area */}
      <div className="flex-1 overflow-hidden max-w-6xl mx-auto w-full">
        <div className="h-full overflow-y-auto p-4 space-y-4">
          {messages.length === 0 ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-center space-y-4 max-w-md">
                <div
                  className="w-20 h-20 rounded-2xl mx-auto flex items-center justify-center p-0 overflow-visible"
                  style={{ background: 'linear-gradient(135deg, hsl(var(--primary)) 0%, hsl(var(--primary) / 0.8) 100%)', boxShadow: '0 8px 32px hsl(var(--primary) / 0.4), 0 0 60px hsl(var(--primary) / 0.2)' }}
                >
                  <Image src="/bergbild2.svg" alt="Abundance Logo" width={80} height={80} className="w-[180%] h-[180%]" style={{ filter: 'drop-shadow(0 4px 8px rgba(0,0,0,0.3))' }} />
                </div>
                <h2 className="text-3xl md:text-4xl lg:text-5xl font-semibold abundance-title">Abundance</h2>
                <p className="text-base md:text-lg" style={{ color: 'hsl(var(--foreground) / 0.7)' }}>
                  Deine KI-Tiefenrecherche: Stell eine komplexe Frage und erhalte einen fundierten Bericht mit verifizierten Quellen.
                </p>
              </div>
            </div>
          ) : (
            <>
              {messages.map((msg, idx) => {
                // Show user messages and agent messages before research status
                if (msg.role === 'user') {
                  return <ChatMessage key={idx} message={msg} />
                }
                // Don't show agent message yet if research is still showing
                return null
              })}
              {showResearchStatus && (
                <ResearchStatus
                  phases={phases}
                  sourceCount={sourceCount}
                  sources={sources}
                  citedSources={citedSources}
                  currentActivity={currentActivity}
                  isCompleted={isCompleted}
                />
              )}
              {streamingReport && (
                <ChatMessage message={{ role: 'agent', content: streamingReport }} />
              )}
              {messages.map((msg, idx) => {
                // Show agent messages after research status
                if (msg.role === 'agent') {
                  return <ChatMessage key={`agent-${idx}`} message={msg} />
                }
                return null
              })}
              <div ref={messagesEndRef} />
            </>
          )}
        </div>
      </div>

      {/* Input Area */}
      <ChatInput onSubmit={handleSendMessage} isStreaming={isStreaming} />
      </div>
    </div>
  )
}
