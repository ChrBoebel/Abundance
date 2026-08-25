/** Small standards-oriented SSE decoder for fetch response streams. */

export interface ServerSentMessage {
  id?: string
  data: string
}

export function parseServerSentFrame(frame: string): ServerSentMessage | null {
  let id: string | undefined
  const data: string[] = []

  for (const rawLine of frame.split(/\r?\n/)) {
    if (!rawLine || rawLine.startsWith(':')) continue
    const separator = rawLine.indexOf(':')
    const field = separator === -1 ? rawLine : rawLine.slice(0, separator)
    let value = separator === -1 ? '' : rawLine.slice(separator + 1)
    if (value.startsWith(' ')) value = value.slice(1)
    if (field === 'id') id = value
    if (field === 'data') data.push(value)
  }

  return data.length > 0 ? { id, data: data.join('\n') } : null
}

export async function consumeServerSentStream(
  stream: ReadableStream<Uint8Array>,
  onMessage: (message: ServerSentMessage) => void,
): Promise<void> {
  const reader = stream.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      buffer += decoder.decode(value, { stream: !done })
      const frames = buffer.split(/\r?\n\r?\n/)
      buffer = frames.pop() ?? ''
      for (const frame of frames) {
        const message = parseServerSentFrame(frame)
        if (message) onMessage(message)
      }
      if (done) break
    }

    const finalMessage = parseServerSentFrame(buffer)
    if (finalMessage) onMessage(finalMessage)
  } finally {
    reader.releaseLock()
  }
}
