/**
 * History sidebar component with branding, model selector, and theme toggle.
 */

'use client'

import { useState } from 'react'
import { Plus, Trash2, Clock, X, Sun, Moon, ChevronUp, PanelLeftClose, Check, Sparkles } from 'lucide-react'
import Image from 'next/image'
import type { ResearchArchiveEntry, ResearchMode } from '@/lib/types'
import { MODEL_DISPLAY_NAMES } from '@/lib/types'

const MODEL_OPTIONS: { key: string; name: string; desc: string; icon: string }[] = [
  { key: 'mercury', name: 'Mercury 2', desc: 'Ultraschnell & kosteneffizient', icon: '/model-icons/inception.svg' },
  { key: 'gemini', name: 'Gemini 2.5 Flash Lite', desc: 'Schnell & effizient', icon: '/model-icons/gemini.svg' },
  { key: 'deepseek', name: 'DeepSeek V3.2', desc: 'Leistungsstark & präzise', icon: '/model-icons/deepseek.svg' },
  { key: 'glm', name: 'GLM-4.5-Air', desc: 'Free & Reasoning-fähig', icon: '/model-icons/glm.svg' },
  { key: 'gemini-flash', name: 'Gemini 2.5 Flash', desc: 'Schnell & leistungsstark', icon: '/model-icons/gemini-flash.svg' },
]

const RESEARCH_MODE_OPTIONS: { key: ResearchMode; name: string; desc: string }[] = [
  { key: 'quick', name: 'Schnell', desc: 'Kompakte Evidenzprüfung' },
  { key: 'balanced', name: 'Ausgewogen', desc: 'Tiefe und Laufzeit im Gleichgewicht' },
  { key: 'thorough', name: 'Gründlich', desc: 'Mehr Gegenbelege und Recherchepfade' },
]

interface ResearchLibraryProps {
  isOpen: boolean
  entries: ResearchArchiveEntry[]
  activeEntryId: string | null
  onSelectEntry: (entry: ResearchArchiveEntry) => void
  onDeleteEntry: (id: string) => void
  onNewResearch: () => void
  onClose: () => void
  mounted: boolean
  theme: string | undefined
  onToggleTheme: () => void
  selectedModel: string
  onSelectModel: (model: string) => void
  selectedMode: ResearchMode
  onSelectMode: (mode: ResearchMode) => void
  backendConnected: boolean | null
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

export default function ResearchLibrary({
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
  selectedMode,
  onSelectMode,
  backendConnected,
}: ResearchLibraryProps) {
  const [showModelMenu, setShowModelMenu] = useState(false)

  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && (
        <button
          type="button"
          aria-label="Verlauf schließen"
          className="fixed inset-0 bg-black/50 z-30 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <aside
        aria-label="Rechercheverlauf und Einstellungen"
        aria-hidden={!isOpen}
        inert={!isOpen}
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
                <Image src="/abundance-mark.svg" alt="" width={65} height={65} style={{ width: '180%', height: '180%', maxWidth: 'none', filter: 'drop-shadow(0 1px 2px rgba(0,0,0,0.3))' }} />
              </div>
              <h1 className="text-lg font-bold abundance-title">Abundance</h1>
            </div>
            <button
              onClick={onClose}
              aria-label="Verlauf schließen"
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
                  className="group relative rounded-lg px-3 py-2.5 transition-all"
                  style={{
                    background: activeEntryId === entry.id ? 'hsl(var(--primary) / 0.12)' : 'transparent',
                    borderLeft: activeEntryId === entry.id ? '3px solid hsl(var(--primary))' : '3px solid transparent',
                  }}
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
                  <button
                    type="button"
                    className="block w-full text-left pr-6"
                    aria-current={activeEntryId === entry.id ? 'page' : undefined}
                    onClick={() => onSelectEntry(entry)}
                  >
                    <span className="block text-sm font-medium truncate" style={{ color: 'hsl(var(--foreground) / 0.9)' }}>
                      {truncateQuery(entry.query)}
                    </span>
                    <span className="flex items-center gap-2 mt-1">
                      <span className="text-xs" style={{ color: 'hsl(var(--foreground) / 0.4)' }}>
                        {formatDate(entry.createdAt)}
                      </span>
                      <span className="text-xs px-1.5 py-0.5 rounded" style={{ background: 'hsl(var(--primary) / 0.1)', color: 'hsl(var(--primary) / 0.8)' }}>
                        {MODEL_DISPLAY_NAMES[entry.model] || entry.model}
                      </span>
                    </span>
                  </button>
                  <button
                    onClick={e => {
                      e.stopPropagation()
                      onDeleteEntry(entry.id)
                    }}
                    className="absolute right-2 top-2.5 p-1 rounded-md opacity-0 group-hover:opacity-100 group-focus-within:opacity-100 focus:opacity-100 transition-opacity hover:bg-red-500/20"
                    aria-label={`Recherche „${truncateQuery(entry.query)}“ löschen`}
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
        <div className="border-t p-3 space-y-3" style={{ borderColor: 'hsl(var(--border))' }}>
          <div>
            <div className="px-1 pb-2 text-xs font-semibold tracking-wider" style={{ color: 'hsl(var(--foreground) / 0.45)' }}>
              RECHERCHEMODUS
            </div>
            <div className="grid grid-cols-3 gap-1 rounded-xl p-1" style={{ background: 'hsl(var(--foreground) / 0.04)' }}>
              {RESEARCH_MODE_OPTIONS.map(mode => (
                <button
                  key={mode.key}
                  type="button"
                  onClick={() => onSelectMode(mode.key)}
                  className="rounded-lg px-2 py-2 text-xs font-medium transition"
                  style={{
                    background: selectedMode === mode.key ? 'hsl(var(--primary) / 0.18)' : 'transparent',
                    color: selectedMode === mode.key ? 'hsl(var(--primary))' : 'hsl(var(--foreground) / 0.55)',
                  }}
                  title={mode.desc}
                  aria-pressed={selectedMode === mode.key}
                >
                  {mode.name}
                </button>
              ))}
            </div>
          </div>

          {/* Model Selector */}
          <div className="relative">
            {/* Model menu (expands upward) */}
            {showModelMenu && (
              <div
                className="absolute bottom-full left-0 right-0 mb-2 rounded-xl border shadow-2xl z-50 overflow-hidden"
                style={{
                  background: 'hsl(var(--card))',
                  borderColor: 'hsl(var(--border))',
                  boxShadow: '0 -4px 24px rgba(0, 0, 0, 0.3), 0 -1px 6px rgba(0, 0, 0, 0.15)'
                }}
              >
                <div className="p-1.5">
                  <div className="flex items-center gap-1.5 px-2.5 pt-1.5 pb-2">
                    <Sparkles className="w-3 h-3" style={{ color: 'hsl(var(--primary))' }} />
                    <span className="text-xs font-semibold tracking-wider" style={{ color: 'hsl(var(--foreground) / 0.45)' }}>
                      KI-MODELL
                    </span>
                  </div>
                  {MODEL_OPTIONS.map(m => {
                    const isSelected = selectedModel === m.key
                    return (
                      <button
                        key={m.key}
                        onClick={() => {
                          onSelectModel(m.key)
                          setTimeout(() => setShowModelMenu(false), 150)
                        }}
                        className="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-lg transition-all duration-150 mb-0.5"
                        style={{
                          background: isSelected
                            ? 'linear-gradient(135deg, hsl(var(--primary) / 0.15) 0%, hsl(var(--primary) / 0.08) 100%)'
                            : 'transparent',
                        }}
                        onMouseEnter={e => {
                          if (!isSelected) (e.currentTarget as HTMLElement).style.background = 'hsl(var(--foreground) / 0.05)'
                        }}
                        onMouseLeave={e => {
                          if (!isSelected) (e.currentTarget as HTMLElement).style.background = 'transparent'
                        }}
                      >
                        <div
                          className="w-7 h-7 rounded-md flex items-center justify-center flex-shrink-0"
                          style={{
                            background: isSelected ? 'hsl(var(--primary) / 0.2)' : 'hsl(var(--foreground) / 0.06)',
                          }}
                        >
                          <Image src={m.icon} alt={m.name} width={18} height={18} className="w-[18px] h-[18px]" />
                        </div>
                        <div className="flex-1 text-left min-w-0">
                          <div className="text-sm font-medium" style={{ color: isSelected ? 'hsl(var(--primary))' : 'hsl(var(--foreground) / 0.9)' }}>
                            {m.name}
                          </div>
                          <div className="text-xs" style={{ color: 'hsl(var(--foreground) / 0.4)' }}>
                            {m.desc}
                          </div>
                        </div>
                        {isSelected && (
                          <Check className="w-4 h-4 flex-shrink-0" style={{ color: 'hsl(var(--primary))' }} />
                        )}
                      </button>
                    )
                  })}
                </div>
              </div>
            )}

            {/* Current model trigger button */}
            <button
              onClick={() => setShowModelMenu(!showModelMenu)}
              aria-expanded={showModelMenu}
              aria-haspopup="menu"
              className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-xl transition-all duration-200"
              style={{
                background: showModelMenu
                  ? 'hsl(var(--primary) / 0.1)'
                  : 'hsl(var(--foreground) / 0.04)',
                border: '1px solid',
                borderColor: showModelMenu
                  ? 'hsl(var(--primary) / 0.3)'
                  : 'hsl(var(--border) / 0.5)',
              }}
              onMouseEnter={e => {
                if (!showModelMenu) {
                  (e.currentTarget as HTMLElement).style.background = 'hsl(var(--foreground) / 0.07)'
                  ;(e.currentTarget as HTMLElement).style.borderColor = 'hsl(var(--border))'
                }
              }}
              onMouseLeave={e => {
                if (!showModelMenu) {
                  (e.currentTarget as HTMLElement).style.background = 'hsl(var(--foreground) / 0.04)'
                  ;(e.currentTarget as HTMLElement).style.borderColor = 'hsl(var(--border) / 0.5)'
                }
              }}
            >
              <div
                className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                style={{ background: 'hsl(var(--primary) / 0.12)' }}
              >
                <Image
                  src={MODEL_OPTIONS.find(m => m.key === selectedModel)?.icon || '/model-icons/inception.svg'}
                  alt=""
                  width={20}
                  height={20}
                  className="w-5 h-5"
                />
              </div>
              <div className="flex-1 text-left min-w-0">
                <div className="text-xs" style={{ color: 'hsl(var(--foreground) / 0.4)' }}>Erweitertes Modell</div>
                <div className="text-sm font-medium truncate">
                  {MODEL_DISPLAY_NAMES[selectedModel] || selectedModel}
                </div>
              </div>
              <ChevronUp
                className="w-4 h-4 flex-shrink-0 transition-transform duration-200"
                style={{
                  color: 'hsl(var(--foreground) / 0.35)',
                  transform: showModelMenu ? 'rotate(0deg)' : 'rotate(180deg)',
                }}
              />
            </button>
          </div>

          {/* Bottom row: Theme toggle + Connection indicator */}
          <div className="flex items-center justify-between px-1">
            {mounted && (
              <button
                onClick={onToggleTheme}
                aria-label={theme === 'dark' ? 'Helles Farbschema aktivieren' : 'Dunkles Farbschema aktivieren'}
                className="p-2 rounded-lg transition"
                style={{ color: 'hsl(var(--foreground) / 0.5)' }}
                onMouseEnter={e => (e.currentTarget as HTMLElement).style.background = 'hsl(var(--foreground) / 0.07)'}
                onMouseLeave={e => (e.currentTarget as HTMLElement).style.background = 'transparent'}
                title={theme === 'dark' ? 'Light Mode' : 'Dark Mode'}
              >
                {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
              </button>
            )}
            <div className="flex items-center gap-1.5" role="status" aria-live="polite">
              <div
                className={`w-2 h-2 rounded-full ${backendConnected ? 'bg-green-500' : backendConnected === false ? 'bg-amber-500' : 'bg-zinc-500'}`}
                title={backendConnected ? 'Backend verbunden' : 'Backend nicht erreichbar'}
              />
              <span className="text-xs" style={{ color: 'hsl(var(--foreground) / 0.35)' }}>
                {backendConnected ? 'Bereit' : backendConnected === false ? 'Offline' : 'Prüfe…'}
              </span>
            </div>
          </div>
        </div>
      </aside>
    </>
  )
}
