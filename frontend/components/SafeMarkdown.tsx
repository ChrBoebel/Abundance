/** Shared generated-Markdown renderer with a narrow URL and HTML policy. */

import { isValidElement, type ReactNode } from 'react'
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'

function safeMarkdownUrl(url: string): string {
  if (url.startsWith('#')) return url
  if (url.startsWith('https://') || url.startsWith('http://')) return url
  return ''
}

function textContent(node: ReactNode): string {
  if (typeof node === 'string' || typeof node === 'number') return String(node)
  if (Array.isArray(node)) return node.map(textContent).join('')
  if (isValidElement<{ children?: ReactNode }>(node)) return textContent(node.props.children)
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
        {isExternal && <span className="sr-only"> (öffnet in einem neuen Tab)</span>}
      </a>
    )
  },
  img() {
    return null
  },
  p({ children, ...props }) {
    const sourceNumber = textContent(children).match(/^\[(\d+)\]\s/)?.[1]
    return <p {...props} id={sourceNumber ? `source-${sourceNumber}` : undefined}>{children}</p>
  },
}

export default function SafeMarkdown({ children }: { children: string }) {
  return (
    <ReactMarkdown
      components={markdownComponents}
      remarkPlugins={[remarkGfm]}
      skipHtml
      urlTransform={safeMarkdownUrl}
    >
      {children}
    </ReactMarkdown>
  )
}
