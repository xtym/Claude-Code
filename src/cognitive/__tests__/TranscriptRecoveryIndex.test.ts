import { describe, expect, test, beforeEach, afterEach } from 'bun:test'
import {
  startTranscriptRecoveryPrefetch,
  recoverySlicesToAttachments,
} from '../context/TranscriptRecoveryIndex.js'

const env = process.env

beforeEach(() => {
  process.env = { ...env, CLAUDE_CODE_COGNITIVE_LAYER: '1', CLAUDE_CODE_COGNITIVE_CONTEXT: '1' }
})
afterEach(() => { process.env = env })

describe('TranscriptRecoveryIndex', () => {
  test('prefetch returns undefined when flag off', () => {
    process.env.CLAUDE_CODE_COGNITIVE_LAYER = '0'
    const result = startTranscriptRecoveryPrefetch([], {
      querySource: 'repl_main_thread',
      agentId: undefined,
      abortController: new AbortController(),
    } as never)
    expect(result).toBeUndefined()
  })

  test('recoverySlicesToAttachments maps slices', () => {
    const attachments = recoverySlicesToAttachments([
      {
        sliceId: '1',
        source: 'transcript',
        content: 'Use PostgreSQL',
        relevanceScore: 0.9,
        tokenEstimate: 10,
      },
    ])
    expect(attachments[0]?.type).toBe('recovered_context')
  })
})
