import { describe, expect, test } from 'bun:test'
import { readFileSync } from 'fs'
import { join } from 'path'
import { buildRecoverySlicesFromMessages } from '../context/localIndex.js'

const fixture = JSON.parse(
  readFileSync(
    join(import.meta.dir, 'fixtures/compact-boundary-transcript.json'),
    'utf8',
  ),
)

describe('localIndex', () => {
  test('extracts pre-compact user decision slices', () => {
    const slices = buildRecoverySlicesFromMessages(
      fixture.messages,
      fixture.query,
    )
    const combined = slices.map(s => s.content).join('\n')
    expect(combined).toContain(fixture.expectedSnippet)
    expect(slices.every(s => s.source === 'transcript' || s.source === 'compact_summary')).toBe(true)
  })

  test('does not index memory paths', () => {
    const slices = buildRecoverySlicesFromMessages(
      [
        {
          type: 'attachment',
          attachment: { type: 'relevant_memories', memories: [{ path: '/mem/x.md', content: 'secret' }] },
        },
      ],
      'secret',
    )
    expect(slices).toEqual([])
  })
})
