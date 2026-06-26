import { describe, expect, test, beforeEach, afterEach } from 'bun:test'
import { readFileSync } from 'fs'
import { join } from 'path'
import {
  startTranscriptRecoveryPrefetch,
  toAttachmentMessages,
} from '../context/TranscriptRecoveryIndex.js'
import { collectSurfacedMemories } from '../../utils/attachments.js'

const fixture = JSON.parse(
  readFileSync(
    join(import.meta.dir, 'fixtures/compact-boundary-transcript.json'),
    'utf8',
  ),
)

const env = process.env

beforeEach(() => {
  process.env = {
    ...env,
    CLAUDE_CODE_COGNITIVE_LAYER: '1',
    CLAUDE_CODE_COGNITIVE_CONTEXT: '1',
  }
})
afterEach(() => { process.env = env })

describe('T1a compact boundary fixture', () => {
  test('recovery attachment contains pre-compact decision after boundary', async () => {
    const handle = startTranscriptRecoveryPrefetch(fixture.messages, {
      querySource: 'repl_main_thread',
      agentId: undefined,
      abortController: new AbortController(),
      memoryBytesAlreadyUsed: collectSurfacedMemories(fixture.messages).totalBytes,
    })
    expect(handle).toBeDefined()
    const slices = await handle!.promise
    const text = toAttachmentMessages(slices)
      .map(m => JSON.stringify(m.attachment))
      .join('\n')
    expect(text).toContain(fixture.expectedSnippet)
    handle![Symbol.dispose]()
  })
})

describe('T5 master flag off', () => {
  test('prefetch returns undefined when disabled', () => {
    process.env.CLAUDE_CODE_COGNITIVE_LAYER = '0'
    const handle = startTranscriptRecoveryPrefetch(fixture.messages, {
      querySource: 'repl_main_thread',
      agentId: undefined,
      abortController: new AbortController(),
    })
    expect(handle).toBeUndefined()
  })
})
