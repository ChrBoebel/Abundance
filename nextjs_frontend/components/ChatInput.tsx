/**
 * Chat Input Component
 */
'use client'

import { Send, Loader2 } from 'lucide-react'

interface ChatInputProps {
  onSubmit: (message: string) => void
  isStreaming: boolean
}

export default function ChatInput({ onSubmit, isStreaming }: ChatInputProps) {
  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const formData = new FormData(e.currentTarget)
    const message = formData.get('message') as string

    if (message.trim() && !isStreaming) {
      onSubmit(message.trim())
      e.currentTarget.reset()
    }
  }

  return (
    <div className="border-t p-4 max-w-6xl mx-auto w-full" style={{ borderColor: 'hsl(var(--border))', background: 'hsl(var(--background))' }}>
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          name="message"
          placeholder="Frage nach Themen, Quellen, Analysen..."
          className="flex-1 px-4 py-2 rounded-lg border focus:outline-none focus:ring-2 transition"
          style={{ background: 'hsl(var(--card))', borderColor: 'hsl(var(--border))', color: 'hsl(var(--foreground))' }}
          disabled={isStreaming}
        />
        <button
          type="submit"
          className="px-6 py-2 rounded-lg font-medium transition hover:scale-105 active:scale-95 flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          style={{ background: 'hsl(var(--primary))', color: 'white' }}
          disabled={isStreaming}
        >
          {isStreaming ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span className="hidden sm:inline">Läuft...</span>
            </>
          ) : (
            <>
              <Send className="w-4 h-4" />
              <span className="hidden sm:inline">Senden</span>
            </>
          )}
        </button>
      </form>
    </div>
  )
}
