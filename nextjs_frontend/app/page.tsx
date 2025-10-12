/**
 * Main Chat Page
 */
'use client'

import { useState, useEffect, useRef } from 'react'
import { useTheme } from 'next-themes'
import { Sun, Moon } from 'lucide-react'
import Image from 'next/image'
import ChatMessage from '@/components/ChatMessage'
import ResearchStatus from '@/components/ResearchStatus'
import ChatInput from '@/components/ChatInput'
import type { Message, ResearchPhase, Source, SSEEvent } from '@/lib/types'

const INITIAL_PHASES: ResearchPhase[] = [
  { id: 1, name: 'Strategie planen', icon: 'clipboard', status: 'pending' },
  { id: 2, name: 'Führe Recherche durch', icon: 'search', status: 'pending' },
  { id: 3, name: 'Synthese der Erkenntnisse', icon: 'lightbulb', status: 'pending' },
  { id: 4, name: 'Erstelle Bericht', icon: 'file-text', status: 'pending' },
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
  const [currentActivity, setCurrentActivity] = useState('')
  const [isCompleted, setIsCompleted] = useState(false)
  const [sessionId] = useState(`s-${Date.now().toString(36)}`)
  const [currentJobId, setCurrentJobId] = useState<string | null>(null)
  const [eventSource, setEventSource] = useState<EventSource | null>(null)
  const [streamingReport, setStreamingReport] = useState('')

  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setMounted(true)
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
    setCurrentActivity('')
    setIsCompleted(false)
    setShowResearchStatus(false)
    setStreamingReport('')
  }

  const updatePhase = (phaseId: number, status: 'pending' | 'running' | 'completed') => {
    setPhases(prev => prev.map(p => p.id === phaseId ? { ...p, status } : p))
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
    setMessages(prev => [...prev, { role: 'user', content: message }])
    resetResearchState()
    setIsStreaming(true)

    const url = `/api/chat/stream?thread_id=${sessionId}&message=${encodeURIComponent(message)}`
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
    <>
      {/* Header */}
      <header className="border-b" style={{ borderColor: 'hsl(var(--border))', background: 'hsl(var(--card))' }}>
        <div className="flex items-center justify-between p-4 max-w-6xl mx-auto">
          <div className="flex items-center gap-3">
            <div
              className="w-12 h-12 rounded-xl flex items-center justify-center p-0 overflow-visible"
              style={{ background: 'linear-gradient(135deg, hsl(var(--primary)) 0%, hsl(var(--primary) / 0.8) 100%)', boxShadow: '0 4px 20px hsl(var(--primary) / 0.4), 0 0 40px hsl(var(--primary) / 0.2)' }}
            >
              <Image src="/bergbild2.svg" alt="Abundance Logo" width={60} height={60} className="w-[180%] h-[180%]" style={{ filter: 'drop-shadow(0 2px 4px rgba(0,0,0,0.3))' }} />
            </div>
            <h1 className="text-2xl font-bold abundance-title">Abundance</h1>
          </div>
          <div className="flex items-center space-x-2">
            <div className="w-2 h-2 bg-green-500 rounded-full" title="Verbunden"></div>
            {mounted && (
              <button
                onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
                className="p-2 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition"
              >
                {theme === 'dark' ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Main Chat Area */}
      <div className="flex-1 overflow-hidden max-w-6xl mx-auto w-full">
        <div className="h-full overflow-y-auto p-4 space-y-4">
          {messages.length === 0 ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-center space-y-4 max-w-md">
                <div
                  className="w-16 h-16 rounded-2xl mx-auto flex items-center justify-center p-0 overflow-visible"
                  style={{ background: 'linear-gradient(135deg, hsl(var(--primary)) 0%, hsl(var(--primary) / 0.8) 100%)', boxShadow: '0 8px 32px hsl(var(--primary) / 0.4), 0 0 60px hsl(var(--primary) / 0.2)' }}
                >
                  <Image src="/bergbild2.svg" alt="Abundance Logo" width={80} height={80} className="w-[180%] h-[180%]" style={{ filter: 'drop-shadow(0 4px 8px rgba(0,0,0,0.3))' }} />
                </div>
                <h2 className="text-xl font-semibold abundance-title">Abundance</h2>
                <p className="text-sm" style={{ color: 'hsl(var(--foreground) / 0.7)' }}>
                  Erkunde die Fülle des Wissens: Stelle eine Frage und erhalte fundierte Antworten aus vielfältigen Perspektiven.
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
    </>
  )
}
