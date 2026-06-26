import { describe, expect, test, beforeEach, afterEach } from 'bun:test'
import { readFileSync } from 'fs'
import { mkdir, rm, writeFile } from 'fs/promises'
import { dirname, join } from 'path'
import { tmpdir } from 'os'
import { getAutoMemPath } from '../../memdir/paths.js'
import type { MemoryHeader } from '../../memdir/memoryScan.js'
import { surfaceOnSessionStart } from '../memory/MemoryStore.js'
import { rankMemoryHeaders } from '../memory/rankMemories.js'
import {
  isFirstUserTurnInSession,
  maybeAppendSessionMemorySurface,
} from '../memory/sessionSurface.js'

const fixture = JSON.parse(
  readFileSync(
    join(import.meta.dir, 'fixtures/session-b-memory-query.json'),
    'utf8',
  ),
) as {
  query: string
  memories: Array<{
    relativePath: string
    description?: string
    body: string
  }>
  expectedSnippet: string
}

const env = process.env
let tempMemoryDir: string

beforeEach(async () => {
  process.env = {
    ...env,
    CLAUDE_CODE_COGNITIVE_LAYER: '1',
    CLAUDE_CODE_COGNITIVE_MEMORY_SURFACE: '1',
  }
  tempMemoryDir = join(
    tmpdir(),
    `cognitive-memory-integration-${Date.now()}-${Math.random().toString(36).slice(2)}`,
  )
  await mkdir(tempMemoryDir, { recursive: true })
  process.env.CLAUDE_COWORK_MEMORY_PATH_OVERRIDE = tempMemoryDir
  getAutoMemPath.cache.clear()

  for (const memory of fixture.memories) {
    const filePath = join(tempMemoryDir, memory.relativePath)
    await mkdir(dirname(filePath), { recursive: true })
    const frontmatter = memory.description
      ? `---\ndescription: ${memory.description}\n---\n`
      : ''
    await writeFile(filePath, `${frontmatter}${memory.body}\n`)
  }
})

afterEach(async () => {
  process.env = env
  getAutoMemPath.cache.clear()
  await rm(tempMemoryDir, { recursive: true, force: true })
})

function headersFromFixture(): MemoryHeader[] {
  return fixture.memories.map((memory, index) => ({
    filePath: join(tempMemoryDir, memory.relativePath),
    filename: memory.relativePath,
    description: memory.description,
    mtimeMs: Date.now() - index * 1000,
    type: undefined,
  }))
}

describe('T3a session B memory surfacing', () => {
  test('rankMemoryHeaders prefers Bun preference for query', () => {
    const ranked = rankMemoryHeaders(headersFromFixture(), fixture.query, 5)
    expect(ranked[0]?.filename).toBe('package-manager-prefs.md')
  })

  test('isFirstUserTurnInSession detects opening turn', () => {
    expect(isFirstUserTurnInSession(undefined)).toBe(true)
    expect(isFirstUserTurnInSession([])).toBe(true)
    expect(
      isFirstUserTurnInSession([
        { type: 'user', uuid: 'u1', message: { role: 'user', content: 'hi' } },
      ]),
    ).toBe(true)
    expect(
      isFirstUserTurnInSession([
        { type: 'user', uuid: 'u1', message: { role: 'user', content: 'hi' } },
        {
          type: 'assistant',
          uuid: 'a1',
          message: { role: 'assistant', content: [{ type: 'text', text: 'ok' }] },
        },
      ]),
    ).toBe(false)
  })

  test('surfaceOnSessionStart returns attachment when flag on', async () => {
    const messages = await surfaceOnSessionStart(fixture.query, {
      querySource: 'repl_main_thread',
      agentId: undefined,
    })

    expect(messages).toHaveLength(1)
    expect(messages[0]?.attachment.type).toBe('session_memory_surface')
    const text = JSON.stringify(messages[0]?.attachment)
    expect(text).toContain(fixture.expectedSnippet)
  })

  test('maybeAppendSessionMemorySurface appends on first turn only', async () => {
    const attachmentMessages: Parameters<
      typeof maybeAppendSessionMemorySurface
    >[0]['attachmentMessages'] = []

    await maybeAppendSessionMemorySurface({
      inputString: fixture.query,
      messages: [],
      querySource: 'repl_main_thread',
      agentId: undefined,
      attachmentMessages,
    })
    expect(attachmentMessages).toHaveLength(1)
    expect(attachmentMessages[0]?.attachment.type).toBe('session_memory_surface')

    await maybeAppendSessionMemorySurface({
      inputString: fixture.query,
      messages: [
        { type: 'user', uuid: 'u1', message: { role: 'user', content: 'hi' } },
        {
          type: 'assistant',
          uuid: 'a1',
          message: { role: 'assistant', content: [{ type: 'text', text: 'ok' }] },
        },
      ],
      querySource: 'repl_main_thread',
      attachmentMessages,
    })
    expect(attachmentMessages).toHaveLength(1)
  })

  test('maybeAppendSessionMemorySurface skips slash commands', async () => {
    const attachmentMessages: Parameters<
      typeof maybeAppendSessionMemorySurface
    >[0]['attachmentMessages'] = []

    await maybeAppendSessionMemorySurface({
      inputString: '/help',
      messages: [],
      querySource: 'repl_main_thread',
      attachmentMessages,
    })
    expect(attachmentMessages).toHaveLength(0)
  })

  test('surfaceOnSessionStart returns empty when memory surface flag off', async () => {
    process.env.CLAUDE_CODE_COGNITIVE_MEMORY_SURFACE = '0'
    const messages = await surfaceOnSessionStart(fixture.query, {
      querySource: 'repl_main_thread',
    })
    expect(messages).toEqual([])
  })
})
