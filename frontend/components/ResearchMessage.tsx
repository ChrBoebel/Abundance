/** Render an inquiry or a research report without trusting generated HTML. */
'use client'

import { isValidElement, type ReactNode } from 'react'
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { ResearchMessageRecord } from '@/lib/types'

interface ResearchMessageProps {
  message: ResearchMessageRecord
  isStreaming?: boolean
}

function safeMarkdownUrl(url: string): string {
  if (url.startsWith('#')) return url
  if (url.startsWith('https://') || url.startsWith('http://')) return url
  return ''
}

function textContent(node: ReactNode): string {
  if (typeof node === 'string' || typeof node === 'number') return String(node)
  if (Array.isArray(node)) return node.map(textContent).join('')
  if (isValidElement<{ children?: ReactNode }>(node)) {
    return textContent(node.props.children)
  }
  return ''
}

const markdownComponents: Components = {
  a({ href = '', children, ...props }) {
    const isExternal = href.startsWith('https://') || href.startsWith('http://')
    return (
      <a
        {...props}
        href={href}
        rel={isExternal ? 'noopener noreferrer nofollow' : undefined}
        target={isExternal ? '_blank' : undefined}
      >
        {children}
      </a>
    )
  },
  img() {
    // Reports may reference arbitrary remote images. Suppress them to avoid
    // tracking requests and keep the evidence surface text-first.
    return null
  },
  p({ children, ...props }) {
    const sourceNumber = textContent(children).match(/^\[(\d+)\]\s/)?.[1]
    return (
      <p {...props} id={sourceNumber ? `source-${sourceNumber}` : undefined}>
        {children}
      </p>
    )
  },
}

export default function ResearchMessage({ message, isStreaming = false }: ResearchMessageProps) {
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
        className={`markdown-content rounded-lg px-6 py-5 w-full report-content ${isStreaming ? 'streaming-cursor' : ''}`}
        style={{
          background: 'hsl(var(--card))',
          color: 'hsl(var(--foreground))',
          border: '1px solid hsl(var(--border))',
        }}
      >
        <ReactMarkdown
          components={markdownComponents}
          remarkPlugins={[remarkGfm]}
          skipHtml
          urlTransform={safeMarkdownUrl}
        >
          {message.content}
        </ReactMarkdown>
      </div>
    </div>
  )
}
