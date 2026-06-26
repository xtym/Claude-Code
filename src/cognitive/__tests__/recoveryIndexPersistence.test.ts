import { describe, test, expect, beforeEach, afterEach } from 'bun:test'
import { mkdir, rm } from 'fs/promises'
import { join } from 'path'
import { tmpdir } from 'os'
import {
  persistSlices,
  loadPersistedSlices,
  type PersistedSlice,
} from '../context/recoveryIndexPersistence.js'
import { getAutoMemPath } from '../../memdir/paths.js'

let tempDir: string

beforeEach(async () => {
  process.env.CLAUDE_CODE_COGNITIVE_LAYER = '1'
  process.env.CLAUDE_CODE_COGNITIVE_CONTEXT = '1'
  tempDir = join(tmpdir(), `cognitive-persistence-${Date.now()}-${Math.random().toString(36).slice(2)}`)
  await mkdir(tempDir, { recursive: true })
  process.env.CLAUDE_COWORK_MEMORY_PATH_OVERRIDE = tempDir
  getAutoMemPath.cache.clear()
})

afterEach(async () => {
  delete process.env.CLAUDE_CODE_COGNITIVE_LAYER
  delete process.env.CLAUDE_CODE_COGNITIVE_CONTEXT
  delete process.env.CLAUDE_COWORK_MEMORY_PATH_OVERRIDE
  getAutoMemPath.cache.clear()
  await rm(tempDir, { recursive: true, force: true })
})

describe('recovery index persistence', () => {
  test('persistSlices writes to disk and loadPersistedSlices reads back', async () => {
    const slices: PersistedSlice[] = [
      {
        sliceId: 'a',
        source: 'transcript',
        content: 'User chose Bun over npm',
        tokenEstimate: 10,
        createdAt: Date.now(),
      },
      {
        sliceId: 'b',
        source: 'transcript',
        content: 'PostgreSQL 15 is the chosen DB',
        tokenEstimate: 8,
        createdAt: Date.now(),
      },
    ]
    await persistSlices(slices)
    const loaded = await loadPersistedSlices()
    expect(loaded).toHaveLength(2)
    const a = loaded.find(s => s.sliceId === 'a')
    expect(a).toBeDefined()
    expect(a!.content).toBe('User chose Bun over npm')
  })

  test('persistSlices merges new slices with existing ones', async () => {
    const first: PersistedSlice[] = [
      {
        sliceId: 'a',
        source: 'transcript',
        content: 'First decision',
        tokenEstimate: 5,
        createdAt: Date.now(),
      },
    ]
    await persistSlices(first)

    const second: PersistedSlice[] = [
      {
        sliceId: 'b',
        source: 'transcript',
        content: 'Second decision',
        tokenEstimate: 5,
        createdAt: Date.now(),
      },
    ]
    await persistSlices(second)

    const loaded = await loadPersistedSlices()
    expect(loaded).toHaveLength(2)
  })

  test('persistSlices updates existing sliceId', async () => {
    const now = Date.now()
    const first: PersistedSlice[] = [
      {
        sliceId: 'a',
        source: 'transcript',
        content: 'Old content',
        tokenEstimate: 5,
        createdAt: now,
      },
    ]
    await persistSlices(first)

    const second: PersistedSlice[] = [
      {
        sliceId: 'a',
        source: 'transcript',
        content: 'Updated content',
        tokenEstimate: 10,
        createdAt: now,
      },
    ]
    await persistSlices(second)

    const loaded = await loadPersistedSlices()
    expect(loaded).toHaveLength(1)
    expect(loaded[0].content).toBe('Updated content')
  })

  test('loadPersistedSlices returns empty when no file exists', async () => {
    const loaded = await loadPersistedSlices()
    expect(loaded).toEqual([])
  })

  test('persistSlices no-ops when CONTEXT flag is off', async () => {
    delete process.env.CLAUDE_CODE_COGNITIVE_CONTEXT
    const slices: PersistedSlice[] = [
      {
        sliceId: 'x',
        source: 'transcript',
        content: 'Should not persist',
        tokenEstimate: 5,
        createdAt: Date.now(),
      },
    ]
    await persistSlices(slices)
    const loaded = await loadPersistedSlices()
    expect(loaded).toEqual([])
  })
})
