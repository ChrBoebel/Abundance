import { describe, expect, it, vi } from 'vitest'

import { consumeServerSentStream, parseServerSentFrame } from './sse'

describe('parseServerSentFrame', () => {
  it('parses identifiers and joins multi-line data', () => {
    expect(parseServerSentFrame('id: 42\ndata: first\ndata: second')).toEqual({
      id: '42',
      data: 'first\nsecond',
    })
  })

  it('ignores heartbeat comments and fields without data', () => {
    expect(parseServerSentFrame(': heartbeat')).toBeNull()
    expect(parseServerSentFrame('id: 12\nretry: 1000')).toBeNull()
  })
})

describe('consumeServerSentStream', () => {
  it('preserves frames split across transport chunks', async () => {
    const encoder = new TextEncoder()
    const chunks = [
      'id: 1\ndata: {"type":"run.',
      'accepted"}\n\n: heartbeat\n\nid: 2\ndata: done\n\n',
    ]
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        for (const chunk of chunks) controller.enqueue(encoder.encode(chunk))
        controller.close()
      },
    })
    const onMessage = vi.fn()

    await consumeServerSentStream(stream, onMessage)

    expect(onMessage).toHaveBeenNthCalledWith(1, {
      id: '1',
      data: '{"type":"run.accepted"}',
    })
    expect(onMessage).toHaveBeenNthCalledWith(2, { id: '2', data: 'done' })
    expect(onMessage).toHaveBeenCalledTimes(2)
  })
})
