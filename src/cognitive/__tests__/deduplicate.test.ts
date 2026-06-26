import { describe, expect, test, beforeEach, afterEach } from 'bun:test'
import { mkdir, rm, writeFile } from 'fs/promises'
import { join } from 'path'
import { tmpdir } from 'os'
import {
  mergeMemoryContent,
  findExistingMemoryByTags,
} from '../memory/deduplicate.js'

describe('mergeMemoryContent', () => {
  test('merges content with frontmatter', () => {
    const existing = `---
created: 2026-01-01T00:00:00.000Z
tags:
  - database
  - postgresql
description: Database preferences
---

Prefer PostgreSQL for persistence.`

    const merged = mergeMemoryContent(
      existing,
      'Use connection pooling with PgBouncer.',
      1735689600000,
    )

    // Frontmatter should be preserved and updated
    expect(merged.startsWith('---\n')).toBe(true)
    expect(merged).toContain('created:')
    expect(merged).toContain('updatedAt:')
    expect(merged).toContain('database')
    expect(merged).toContain('postgresql')
    expect(merged).toContain('PgBouncer')

    // Original content should be preserved
    expect(merged).toContain('Prefer PostgreSQL')
  })

  test('matches mergedTags parameter', () => {
    const existing = `---
created: 2026-01-01T00:00:00.000Z
tags:
  - database
description: Database
---

Existing body text.`

    const merged = mergeMemoryContent(
      existing,
      'New content.',
      1735689600000,
      ['database', 'postgresql', 'migration'],
    )

    expect(merged).toContain('database')
    expect(merged).toContain('postgresql')
    expect(merged).toContain('migration')
    expect(merged).toContain('Existing body text')
    expect(merged).toContain('New content.')
  })

  test('preserves existing content while appending new sections', () => {
    const existing = `---
created: 2026-01-01T00:00:00.000Z
tags:
  - linting
description: Lint configuration
---

Existing linting notes.`

    const merged = mergeMemoryContent(
      existing,
      '## Formatting\nUse Prettier for formatting.',
      1735689600000,
    )

    expect(merged).toContain('Existing linting notes')
    expect(merged).toContain('## Formatting')
    expect(merged).toContain('Use Prettier')
  })

  test('does not duplicate existing sections', () => {
    const existing = `---
created: 2026-01-01T00:00:00.000Z
tags:
  - linting
description: Lint configuration
---

## Formatting
Use Prettier for formatting.`

    const merged = mergeMemoryContent(
      existing,
      '## Formatting\nAlso use ESLint.',
      1735689600000,
    )

    // Should not duplicate the Formatting section heading
    const headingCount = (merged.match(/## Formatting/g) || []).length
    expect(headingCount).toBe(1)
    // Original content should be preserved
    expect(merged).toContain('Use Prettier')
  })

  test('handles content without existing frontmatter', () => {
    const merged = mergeMemoryContent(
      'Just a plain markdown body.',
      'New appended content.',
      1735689600000,
    )

    expect(merged.startsWith('---\n')).toBe(true)
    expect(merged).toContain('created:')
    expect(merged).toContain('Just a plain markdown body')
    expect(merged).toContain('New appended content')
  })
})

describe('findExistingMemoryByTags', () => {
  let tempDir: string

  beforeEach(async () => {
    tempDir = join(
      tmpdir(),
      `cognitive-dedup-test-${Date.now()}-${Math.random().toString(36).slice(2)}`,
    )
    await mkdir(tempDir, { recursive: true })
  })

  afterEach(async () => {
    await rm(tempDir, { recursive: true, force: true })
  })

  async function writeMemory(
    relativePath: string,
    tags: string[],
    body: string,
  ): Promise<void> {
    const tagsYaml = tags.map(t => `  - ${t}`).join('\n')
    const content = `---
created: 2026-01-01T00:00:00.000Z
tags:
${tagsYaml}
description: ${tags[0] || 'test'}
---

${body}
`
    await writeFile(join(tempDir, relativePath), content)
  }

  test('finds existing file by tag overlap > 40%', async () => {
    await writeMemory('database.md', ['database', 'postgresql', 'sql'], 'DB content')
    await writeMemory('linting.md', ['linting', 'eslint'], 'Lint content')

    const signal = new AbortController().signal
    const result = await findExistingMemoryByTags(
      ['database', 'postgresql', 'migration'],
      tempDir,
      signal,
    )

    expect(result).not.toBeNull()
    expect(result!.path).toContain('database.md')
  })

  test('returns null when no tag overlap', async () => {
    await writeMemory('database.md', ['database', 'postgresql'], 'DB content')

    const signal = new AbortController().signal
    const result = await findExistingMemoryByTags(
      ['linting', 'eslint'],
      tempDir,
      signal,
    )

    expect(result).toBeNull()
  })

  test('returns most-recently-modified match', async () => {
    await writeMemory('older.md', ['database'], 'Older content')
    // Wait to ensure different mtime
    await new Promise(r => setTimeout(r, 50))
    await writeMemory('newer.md', ['database', 'postgresql'], 'Newer content')

    const signal = new AbortController().signal
    const result = await findExistingMemoryByTags(
      ['database', 'migration'],
      tempDir,
      signal,
    )

    expect(result).not.toBeNull()
    expect(result!.path).toContain('newer.md')
  })

  test('returns null for empty tags array', async () => {
    await writeMemory('test.md', ['database'], 'Content')

    const signal = new AbortController().signal
    const result = await findExistingMemoryByTags([], tempDir, signal)
    expect(result).toBeNull()
  })
})
