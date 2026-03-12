/**
 * Chat Message Component
 */
'use client'

import { useLayoutEffect, useRef } from 'react'
import { marked } from 'marked'
import hljs from 'highlight.js'
import type { Message } from '@/lib/types'

interface ChatMessageProps {
  message: Message
  isStreaming?: boolean
}

export default function ChatMessage({ message, isStreaming = false }: ChatMessageProps) {
  const contentRef = useRef<HTMLDivElement>(null)
  const parsedContent = marked.parse(message.content, { async: false }) as string

  useLayoutEffect(() => {
    // Skip heavy DOM processing during streaming for smooth rendering
    if (isStreaming) return

    if (message.role === 'agent' && contentRef.current) {
      // Highlight code blocks
      contentRef.current.querySelectorAll('pre code').forEach((block) => {
        hljs.highlightElement(block as HTMLElement)
      })

      // Make all links open in new tab
      contentRef.current.querySelectorAll('a').forEach(link => {
        link.setAttribute('target', '_blank')
        link.setAttribute('rel', 'noopener noreferrer')
      })

      // Make citation numbers clickable
      const walker = document.createTreeWalker(contentRef.current, NodeFilter.SHOW_TEXT)
      const nodesToReplace: Array<{ node: Node; text: string }> = []
      let node: Node | null

      while ((node = walker.nextNode())) {
        if (node.textContent && /\[\d+\]/.test(node.textContent)) {
          nodesToReplace.push({ node, text: node.textContent })
        }
      }

      nodesToReplace.forEach(({ node, text }) => {
        const regex = /\[(\d+)\]/g
        const fragment = document.createDocumentFragment()
        let lastIndex = 0
        let match: RegExpExecArray | null

        while ((match = regex.exec(text)) !== null) {
          if (match.index > lastIndex) {
            fragment.appendChild(document.createTextNode(text.substring(lastIndex, match.index)))
          }

          const citation = document.createElement('a')
          const sourceNumber = match[1]
          citation.href = `#source-${sourceNumber}`
          citation.textContent = match[0]
          citation.className = 'citation-link'
          citation.style.cssText = 'color: hsl(var(--primary)); font-weight: 500; cursor: pointer; text-decoration: none;'
          citation.onclick = (e) => {
            e.preventDefault()
            const sourceEl = contentRef.current?.querySelector(`#source-${sourceNumber}`)
            if (sourceEl) {
              sourceEl.scrollIntoView({ behavior: 'smooth', block: 'center' })
              sourceEl.classList.add('highlight-source')
              setTimeout(() => {
                sourceEl.classList.remove('highlight-source')
              }, 2000)
            }
          }
          fragment.appendChild(citation)
          lastIndex = regex.lastIndex
        }

        if (lastIndex < text.length) {
          fragment.appendChild(document.createTextNode(text.substring(lastIndex)))
        }

        node.parentNode?.replaceChild(fragment, node)
      })

      // Format sources section
      const sourcesHeading = Array.from(contentRef.current.querySelectorAll('h3')).find(h3 =>
        h3.textContent?.toLowerCase().includes('quellen') || h3.textContent?.toLowerCase().includes('sources')
      )

      if (sourcesHeading) {
        const sourcesContainer = sourcesHeading.nextElementSibling
        if (sourcesContainer && sourcesContainer.tagName === 'P') {
          const sourcesText = sourcesContainer.textContent || ''
          const sourcesArray = sourcesText.split(/\[(\d+)\]/).filter(s => s.trim())

          const sourcesList = document.createElement('div')
          sourcesList.className = 'sources-list'
          sourcesList.style.cssText = 'display: flex; flex-direction: column; gap: 1rem; margin-top: 1rem;'

          for (let i = 0; i < sourcesArray.length; i += 2) {
            if (sourcesArray[i] && sourcesArray[i + 1]) {
              const sourceNumber = sourcesArray[i]
              const sourceText = sourcesArray[i + 1].trim()

              const sourceItem = document.createElement('div')
              sourceItem.id = `source-${sourceNumber}`
              sourceItem.className = 'source-item'
              sourceItem.style.cssText = 'padding: 0.75rem; background: hsl(var(--muted) / 0.3); border-radius: 0.25rem; transition: background 0.3s;'

              const sourceNumberEl = document.createElement('span')
              sourceNumberEl.style.cssText = 'font-weight: 600; color: hsl(var(--primary)); margin-right: 0.5rem;'
              sourceNumberEl.textContent = `[${sourceNumber}]`

              const sourceContent = document.createElement('span')
              const urlRegex = /(https?:\/\/[^\s]+)/g
              const textWithLinks = sourceText.replace(urlRegex, '<a href="$1" target="_blank" rel="noopener noreferrer" style="color: hsl(var(--primary)); text-decoration: underline; cursor: pointer;">$1</a>')
              sourceContent.innerHTML = textWithLinks

              sourceItem.appendChild(sourceNumberEl)
              sourceItem.appendChild(sourceContent)
              sourcesList.appendChild(sourceItem)
            }
          }

          sourcesContainer.replaceWith(sourcesList)
        }
      }
    }
  }, [message.content, message.role, isStreaming])

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
        ref={contentRef}
        className={`markdown-content rounded-lg px-6 py-5 w-full report-content ${isStreaming ? 'streaming-cursor' : ''}`}
        style={{ background: 'hsl(var(--card))', color: 'hsl(var(--foreground))', border: '1px solid hsl(var(--border))' }}
        dangerouslySetInnerHTML={{ __html: parsedContent }}
      />
    </div>
  )
}
