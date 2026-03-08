/**
 * History sidebar component with research entry list.
 */

'use client'

import { Plus, Trash2, Clock, X } from 'lucide-react'
import type { HistoryEntry } from '@/lib/types'
import { MODEL_DISPLAY_NAMES } from '@/lib/types'

interface HistorySidebarProps {
  isOpen: boolean
  entries: HistoryEntry[]
  activeEntryId: string | null
  onSelectEntry: (entry: HistoryEntry) => void
  onDeleteEntry: (id: string) => void
  onNewResearch: () => void
  onClose: () => void
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
}: HistorySidebarProps) {
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
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b" style={{ borderColor: 'hsl(var(--border))' }}>
          <span className="text-xs font-semibold tracking-wider" style={{ color: 'hsl(var(--foreground) / 0.5)' }}>
            VERLAUF
          </span>
          <button
            onClick={onClose}
            className="p-1 rounded-md hover:bg-white/10 transition lg:hidden"
          >
            <X className="w-4 h-4" style={{ color: 'hsl(var(--foreground) / 0.5)' }} />
          </button>
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
        <div className="flex-1 overflow-y-auto px-2 pb-4">
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
      </aside>
    </>
  )
}
