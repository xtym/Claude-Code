import { describe, expect, test, beforeEach, afterEach } from 'bun:test'
import { mkdir, readdir, readFile, rm } from 'fs/promises'
import { join } from 'path'
import { tmpdir } from 'os'
import { getAutoMemPath } from '../../memdir/paths.js'
import { write, parseTagsFromFile } from '../memory/MemoryStore.js'
import { parseFrontmatter } from '../../utils/frontmatterParser.js'

let tempMemoryDir: string

beforeEach(async () => {
  process.env.CLAUDE_CODE_COGNITIVE_LAYER = '1'
  process.env.CLAUDE_CODE_COGNITIVE_MEMORY_WRITE = '1'
  tempMemoryDir = join(
    tmpdir(),
    `cognitive-memory-write-${Date.now()}-${Math.random().toString(36).slice(2)}`,
  )
  await mkdir(tempMemoryDir, { recursive: true })
  process.env.CLAUDE_COWORK_MEMORY_PATH_OVERRIDE = tempMemoryDir
  getAutoMemPath.cache.clear()
})

afterEach(async () => {
  delete process.env.CLAUDE_CODE_COGNITIVE_LAYER
  delete process.env.CLAUDE_CODE_COGNITIVE_MEMORY_WRITE
  delete process.env.CLAUDE_COWORK_MEMORY_PATH_OVERRIDE
  getAutoMemPath.cache.clear()
  await rm(tempMemoryDir, { recursive: true, force: true })
})

describe('T3 memory write round-trip', () => {
  test('write creates file with correct frontmatter tags', async () => {
    const result = await write({
      scope: 'project',
      tags: ['database', 'postgresql'],
      content: 'The project uses PostgreSQL 15 as its primary database.',
    })

    expect(result.path).toBeDefined()
    expect(result.path).not.toBe('')
    expect(result.path).toContain(tempMemoryDir)

    // Verify file exists
    const files = await readdir(tempMemoryDir)
    expect(files).toHaveLength(1)
    expect(files[0]).toMatch(/\.md$/)

    // Verify frontmatter contains expected tags
    const raw = await readFile(result.path, 'utf8')
    const { frontmatter } = parseFrontmatter(raw, result.path)
    expect(frontmatter.tags).toBeDefined()
    const tags = Array.isArray(frontmatter.tags)
      ? frontmatter.tags
      : typeof frontmatter.tags === 'string'
        ? frontmatter.tags.split(',').map(t => t.trim())
        : []
    expect(tags).toContain('database')
    expect(tags).toContain('postgresql')

    // Verify content is preserved
    expect(raw).toContain('PostgreSQL 15')
  })

  test('dedup merges overlapping tags into one file', async () => {
    const result1 = await write({
      scope: 'project',
      tags: ['database', 'postgresql'],
      content: 'The project uses PostgreSQL 15 as its primary database.',
    })

    const result2 = await write({
      scope: 'project',
      tags: ['postgresql', 'migration'],
      content: 'The team is migrating from PostgreSQL 15 to 17.',
    })

    // Both writes should return the same file (dedup)
    expect(result2.path).toBe(result1.path)

    // Only 1 file should exist
    const files = await readdir(tempMemoryDir)
    expect(files).toHaveLength(1)

    // The merged file should contain ALL tags
    const mergedTags = await parseTagsFromFile(result2.path)
    expect(mergedTags).toContain('database')
    expect(mergedTags).toContain('postgresql')
    expect(mergedTags).toContain('migration')

    // The merged file should contain BOTH content entries
    const mergedRaw = await readFile(result2.path, 'utf8')
    expect(mergedRaw).toContain('PostgreSQL 15')
    expect(mergedRaw).toContain('migrating from PostgreSQL')
  })
})
