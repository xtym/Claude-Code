import type { MemoryHeader } from '../../memdir/memoryScan.js'

const QUERY_STOP_WORDS = new Set([
  'not',
  'the',
  'and',
  'for',
  'with',
  'this',
  'that',
  'from',
  'are',
  'was',
  'has',
  'have',
  'use',
])

function tokenize(text: string, options?: { query?: boolean }): string[] {
  return text
    .toLowerCase()
    .split(/[^a-z0-9_]+/i)
    .filter(
      t =>
        t.length >= 3 &&
        !(options?.query && QUERY_STOP_WORDS.has(t)),
    )
}

function scoreMemoryHeader(
  header: MemoryHeader,
  query: string,
  maxMtimeMs: number,
): number {
  const queryTokens = new Set(tokenize(query, { query: true }))
  const searchable = [header.filename, header.description ?? ''].join(' ')
  const contentTokens = tokenize(searchable)
  const recencyScore =
    maxMtimeMs > 0 ? header.mtimeMs / maxMtimeMs : 0

  if (queryTokens.size === 0 || contentTokens.length === 0) {
    return recencyScore
  }

  let matches = 0
  for (const t of contentTokens) {
    for (const q of queryTokens) {
      if (t === q || t.includes(q) || q.includes(t)) {
        matches++
        break
      }
    }
  }
  const keywordScore = matches / queryTokens.size

  return keywordScore * 0.7 + recencyScore * 0.3
}

export function rankMemoryHeaders(
  headers: MemoryHeader[],
  query: string,
  limit: number,
): MemoryHeader[] {
  const maxMtimeMs = Math.max(0, ...headers.map(h => h.mtimeMs))
  return [...headers]
    .map(header => ({
      header,
      score: scoreMemoryHeader(header, query, maxMtimeMs),
    }))
    .sort(
      (a, b) =>
        b.score - a.score ||
        b.header.mtimeMs - a.header.mtimeMs,
    )
    .slice(0, limit)
    .map(({ header }) => header)
}
