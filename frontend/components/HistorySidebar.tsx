/**
 * History sidebar component with branding, model selector, and theme toggle.
 */

'use client'

import { useState } from 'react'
import { Plus, Trash2, Clock, X, Sun, Moon, ChevronUp, PanelLeftClose } from 'lucide-react'
import Image from 'next/image'
import type { HistoryEntry } from '@/lib/types'
import { MODEL_DISPLAY_NAMES } from '@/lib/types'

const MODEL_OPTIONS: { key: string; name: string; desc: string }[] = [
  { key: 'mercury', name: 'Mercury 2', desc: 'Ultraschnell & kosteneffizient' },
  { key: 'gemini', name: 'Gemini 2.5 Flash Lite', desc: 'Schnell & effizient' },
  { key: 'deepseek', name: 'DeepSeek V3.2', desc: 'Leistungsstark & präzise' },
  { key: 'glm', name: 'GLM-4.5-Air', desc: 'Free & Reasoning-fähig' },
  { key: 'gemini-flash', name: 'Gemini 2.5 Flash', desc: 'Schnell & leistungsstark' },
]

interface HistorySidebarProps {
  isOpen: boolean
  entries: HistoryEntry[]
  activeEntryId: string | null
  onSelectEntry: (entry: HistoryEntry) => void
  onDeleteEntry: (id: string) => void
  onNewResearch: () => void
  onClose: () => void
  mounted: boolean
  theme: string | undefined
  onToggleTheme: () => void
  selectedModel: string
  onSelectModel: (model: string) => void
}

function formatDate(iso: string): string {
  try {
    const d = new Date(iso)
    const now = new Date()
    const diff = now.getTime() - d.getTime()
    const mins = Math.floor(diff / 60000)
    if (mins < 1) return 'Gerade eben'
    if (mins < 60) return `vor ${mins} Min.`
    const hours = Math.floor(mins / 60)
    if (hours < 24) return `vor ${hours} Std.`
    const days = Math.floor(hours / 24)
    if (days < 7) return `vor ${days} Tag${days > 1 ? 'en' : ''}`
    return d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: '2-digit' })
  } catch {
    return ''
  }
}

function truncateQuery(query: string, max = 50): string {
  if (query.length <= max) return query
  return query.substring(0, max) + '...'
}

export default function HistorySidebar({
  isOpen,
  entries,
  activeEntryId,
  onSelectEntry,
  onDeleteEntry,
  onNewResearch,
  onClose,
  mounted,
  theme,
  onToggleTheme,
  selectedModel,
  onSelectModel,
}: HistorySidebarProps) {
  const [showModelMenu, setShowModelMenu] = useState(false)

  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-30 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
          fixed lg:relative z-40 top-0 left-0 h-full
          w-72 flex-shrink-0 flex flex-col
          border-r transition-transform duration-300 ease-in-out
          lg:transition-[margin] lg:duration-300
          ${isOpen ? 'translate-x-0 lg:ml-0' : '-translate-x-full lg:-ml-72'}
        `}
        style={{
          background: 'hsl(var(--card))',
          borderColor: 'hsl(var(--border))',
        }}
      >
        {/* Logo + Brand Header */}
        <div className="p-4 border-b" style={{ borderColor: 'hsl(var(--border))' }}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div
                className="w-9 h-9 rounded-lg flex items-center justify-center overflow-visible flex-shrink-0"
                style={{ background: 'linear-gradient(135deg, hsl(var(--primary)) 0%, hsl(var(--primary) / 0.8) 100%)', boxShadow: '0 2px 12px hsl(var(--primary) / 0.4)' }}
              >
                <Image src="/bergbild2.svg" alt="Abundance Logo" width={40} height={40} className="w-[180%] h-[180%]" style={{ filter: 'drop-shadow(0 1px 2px rgba(0,0,0,0.3))' }} />
              </div>
              <h1 className="text-lg font-bold abundance-title">Abundance</h1>
            </div>
            <button
              onClick={onClose}
              className="p-1.5 rounded-md hover:bg-white/10 transition"
              title="Sidebar schließen"
            >
              <PanelLeftClose className="w-4 h-4 hidden lg:block" style={{ color: 'hsl(var(--foreground) / 0.5)' }} />
              <X className="w-4 h-4 lg:hidden" style={{ color: 'hsl(var(--foreground) / 0.5)' }} />
            </button>
          </div>
          <div className="mt-2">
            <span className="text-xs font-semibold tracking-wider" style={{ color: 'hsl(var(--foreground) / 0.4)' }}>
              VERLAUF
            </span>
          </div>
        </div>

        {/* New Research Button */}
        <div className="p-3">
          <button
            onClick={onNewResearch}
            className="w-full flex items-center gap-2 px-3 py-2.5 rounded-lg border border-dashed transition-all hover:border-solid"
            style={{
              borderColor: 'hsl(var(--primary) / 0.5)',
              color: 'hsl(var(--primary))',
            }}
          >
            <Plus className="w-4 h-4" />
            <span className="text-sm font-medium">Neue Recherche</span>
          </button>
        </div>

        {/* Entries List */}
        <div className="flex-1 overflow-y-auto px-2 pb-2">
          {entries.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-48 gap-3" style={{ color: 'hsl(var(--foreground) / 0.3)' }}>
              <Clock className="w-8 h-8" />
              <span className="text-sm">Noch keine Recherchen</span>
            </div>
          ) : (
            <div className="space-y-1">
              {entries.map(entry => (
                <div
                  key={entry.id}
                  className="group relative rounded-lg px-3 py-2.5 cursor-pointer transition-all"
                  style={{
                    background: activeEntryId === entry.id ? 'hsl(var(--primary) / 0.12)' : 'transparent',
                    borderLeft: activeEntryId === entry.id ? '3px solid hsl(var(--primary))' : '3px solid transparent',
                  }}
                  onClick={() => onSelectEntry(entry)}
                  onMouseEnter={e => {
                    if (activeEntryId !== entry.id) {
                      (e.currentTarget as HTMLElement).style.background = 'hsl(var(--foreground) / 0.05)'
                    }
                  }}
                  onMouseLeave={e => {
                    if (activeEntryId !== entry.id) {
                      (e.currentTarget as HTMLElement).style.background = 'transparent'
                    }
                  }}
                >
                  <div className="text-sm font-medium truncate pr-6" style={{ color: 'hsl(var(--foreground) / 0.9)' }}>
                    {truncateQuery(entry.query)}
                  </div>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-xs" style={{ color: 'hsl(var(--foreground) / 0.4)' }}>
                      {formatDate(entry.createdAt)}
                    </span>
                    <span className="text-xs px-1.5 py-0.5 rounded" style={{ background: 'hsl(var(--primary) / 0.1)', color: 'hsl(var(--primary) / 0.8)' }}>
                      {MODEL_DISPLAY_NAMES[entry.model] || entry.model}
                    </span>
                  </div>
                  <button
                    onClick={e => {
                      e.stopPropagation()
                      onDeleteEntry(entry.id)
                    }}
                    className="absolute right-2 top-2.5 p-1 rounded-md opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-500/20"
                    style={{ color: 'hsl(var(--foreground) / 0.4)' }}
                    title="Löschen"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer: Model Selector + Theme Toggle */}
        <div className="border-t p-3 space-y-2" style={{ borderColor: 'hsl(var(--border))' }}>
          {/* Model Selector */}
          <div className="relative">
            {/* Model menu (expands upward) */}
            {showModelMenu && (
              <div
                className="absolute bottom-full left-0 right-0 mb-1 rounded-xl border backdrop-blur-sm shadow-xl z-50 overflow-hidden"
                style={{
                  background: 'hsl(var(--card) / 0.98)',
                  borderColor: 'hsl(var(--border))',
                  boxShadow: '0 -8px 32px rgba(0, 0, 0, 0.4)'
                }}
              >
                <div className="p-2">
                  <div className="text-xs font-semibold mb-1.5 px-2" style={{ color: 'hsl(var(--foreground) / 0.5)' }}>
                    KI-MODELL
                  </div>
                  {MODEL_OPTIONS.map(m => (
                    <button
                      key={m.key}
                      onClick={() => {
                        onSelectModel(m.key)
                        setTimeout(() => setShowModelMenu(false), 150)
                      }}
                      className={`w-full text-left px-3 py-2 rounded-lg transition-all duration-200 mb-0.5 ${
                        selectedModel === m.key ? 'shadow-md' : 'hover:bg-opacity-50'
                      }`}
                      style={selectedModel === m.key ? {
                        background: 'linear-gradient(135deg, hsl(var(--primary) / 0.9) 0%, hsl(var(--primary) / 0.7) 100%)',
                        boxShadow: '0 2px 8px hsl(var(--primary) / 0.3)'
                      } : {
                        background: 'transparent'
                      }}
                    >
                      <div className="text-sm font-medium">{m.name}</div>
                      <div className="text-xs mt-0.5" style={{ color: 'hsl(var(--foreground) / 0.5)' }}>
                        {m.desc}
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Current model button */}
            <button
              onClick={() => setShowModelMenu(!showModelMenu)}
              className="w-full flex items-center justify-between px-3 py-2 rounded-lg transition-all"
              style={{
                background: 'hsl(var(--foreground) / 0.05)',
              }}
            >
              <div className="flex items-center gap-2 min-w-0">
                <span className="text-sm font-medium truncate">
                  {MODEL_DISPLAY_NAMES[selectedModel] || selectedModel}
                </span>
              </div>
              <ChevronUp
                className="w-4 h-4 flex-shrink-0 transition-transform duration-200"
                style={{
                  color: 'hsl(var(--foreground) / 0.4)',
                  transform: showModelMenu ? 'rotate(180deg)' : 'rotate(0deg)',
                }}
              />
            </button>
          </div>

          {/* Bottom row: Theme toggle + Connection indicator */}
          <div className="flex items-center justify-between px-1">
            {mounted && (
              <button
                onClick={onToggleTheme}
                className="p-2 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition"
                title={theme === 'dark' ? 'Light Mode' : 'Dark Mode'}
              >
                {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
              </button>
            )}
            <div className="flex items-center gap-1.5">
              <div className="w-2 h-2 bg-green-500 rounded-full" title="Verbunden"></div>
              <span className="text-xs" style={{ color: 'hsl(var(--foreground) / 0.4)' }}>Verbunden</span>
            </div>
          </div>
        </div>
      </aside>
    </>
  )
}
