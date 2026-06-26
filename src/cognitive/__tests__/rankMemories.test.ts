import { describe, expect, test } from 'bun:test'
import type { MemoryHeader } from '../../memdir/memoryScan.js'
import { rankMemoryHeaders } from '../memory/rankMemories.js'

function header(
  filename: string,
  description: string | null,
  mtimeMs: number,
): MemoryHeader {
  return {
    filename,
    filePath: `/mem/${filename}`,
    mtimeMs,
    description,
    type: undefined,
  }
}

describe('rankMemoryHeaders', () => {
  test('keyword match ranks above unrelated memories', () => {
    const headers = [
      header('lint-utils.md', 'Lint passed on utils folder', 1000),
      header('postgres-schema.md', 'Use PostgreSQL for persistence layer', 900),
    ]
    const ranked = rankMemoryHeaders(
      headers,
      'database postgres schema',
      5,
    )
    expect(ranked[0]?.filename).toBe('postgres-schema.md')
  })

  test('recency boosts score when keyword overlap is equal', () => {
    const headers = [
      header('architecture-old.md', 'Architecture event-driven modules', 1000),
      header('architecture-new.md', 'Architecture event-driven modules', 2000),
    ]
    const ranked = rankMemoryHeaders(headers, 'architecture modules', 5)
    expect(ranked[0]?.filename).toBe('architecture-new.md')
  })

  test('respects limit', () => {
    const headers = [
      header('a.md', 'alpha', 3000),
      header('b.md', 'beta', 2000),
      header('c.md', 'gamma', 1000),
    ]
    expect(rankMemoryHeaders(headers, 'alpha beta gamma', 2)).toHaveLength(2)
  })

  test('empty query falls back to recency ordering', () => {
    const headers = [
      header('old.md', 'Old note', 1000),
      header('new.md', 'New note', 3000),
    ]
    const ranked = rankMemoryHeaders(headers, '', 5)
    expect(ranked[0]?.filename).toBe('new.md')
  })
})
