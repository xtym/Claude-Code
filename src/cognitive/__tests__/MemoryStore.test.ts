import { describe, expect, test, beforeEach, afterEach } from 'bun:test'
import { mkdir, rm, writeFile } from 'fs/promises'
import { dirname, join } from 'path'
import { tmpdir } from 'os'
import { getAutoMemPath } from '../../memdir/paths.js'
import { recall, surfaceOnSessionStart } from '../memory/MemoryStore.js'

const env = process.env
let tempMemoryDir: string

beforeEach(async () => {
  process.env = { ...env }
  tempMemoryDir = join(
    tmpdir(),
    `cognitive-memory-test-${Date.now()}-${Math.random().toString(36).slice(2)}`,
  )
  await mkdir(tempMemoryDir, { recursive: true })
  process.env.CLAUDE_COWORK_MEMORY_PATH_OVERRIDE = tempMemoryDir
  getAutoMemPath.cache.clear()
})

afterEach(async () => {
  process.env = env
  getAutoMemPath.cache.clear()
  await rm(tempMemoryDir, { recursive: true, force: true })
})

async function writeMemory(
  relativePath: string,
  body: string,
  description?: string,
): Promise<void> {
  const filePath = join(tempMemoryDir, relativePath)
  await mkdir(dirname(filePath), { recursive: true })
  const frontmatter = description
    ? `---\ndescription: ${description}\n---\n`
    : ''
  await writeFile(filePath, `${frontmatter}${body}\n`)
}

describe('MemoryStore.recall', () => {
  test('returns ranked project memories from auto mem path', async () => {
    await writeMemory(
      'postgres-prefs.md',
      'Prefer PostgreSQL for persistence.',
      'Database preference',
    )
    await writeMemory('lint-notes.md', 'Lint passed on utils folder.')

    const entries = await recall('postgres database', 'project', 1)
    expect(entries).toHaveLength(1)
    expect(entries[0]?.path).toContain('postgres-prefs.md')
    expect(entries[0]?.content).toContain('PostgreSQL')
    expect(entries[0]?.tags).toContain('postgres')
    expect(entries[0]?.tags).toContain('Database preference')
  })

  test('non-project scope returns empty', async () => {
    await writeMemory('session-note.md', 'Session-only note.')
    expect(await recall('session', 'session')).toEqual([])
    expect(await recall('user', 'user')).toEqual([])
  })
})

describe('MemoryStore.surfaceOnSessionStart', () => {
  test('returns attachment when flags and scope allow', async () => {
    process.env.CLAUDE_CODE_COGNITIVE_LAYER = '1'
    process.env.CLAUDE_CODE_COGNITIVE_MEMORY_SURFACE = '1'
    await writeMemory(
      'typescript-style.md',
      'Use single quotes in TypeScript files.',
      'TypeScript style preference',
    )

    const messages = await surfaceOnSessionStart('typescript style preference', {
      querySource: 'repl_main_thread',
      agentId: undefined,
    })

    expect(messages).toHaveLength(1)
    expect(messages[0]?.type).toBe('attachment')
    expect(messages[0]?.attachment.type).toBe('session_memory_surface')
    if (messages[0]?.attachment.type === 'session_memory_surface') {
      expect(messages[0].attachment.memories[0]?.content).toContain('single quotes')
    }
  })

  test('returns empty when memory surface flag is off', async () => {
    process.env.CLAUDE_CODE_COGNITIVE_LAYER = '1'
    process.env.CLAUDE_CODE_COGNITIVE_MEMORY_SURFACE = '0'
    await writeMemory('prefs.md', 'Always use bun.')

    const messages = await surfaceOnSessionStart('bun', {
      querySource: 'repl_main_thread',
    })
    expect(messages).toEqual([])
  })

  test('returns empty for subagent scope', async () => {
    process.env.CLAUDE_CODE_COGNITIVE_LAYER = '1'
    process.env.CLAUDE_CODE_COGNITIVE_MEMORY_SURFACE = '1'
    await writeMemory('prefs.md', 'Always use bun.')

    const messages = await surfaceOnSessionStart('bun', {
      querySource: 'repl_main_thread',
      agentId: '00000000-0000-4000-8000-000000000001',
    })
    expect(messages).toEqual([])
  })
})
