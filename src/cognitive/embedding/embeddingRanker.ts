import type { MemoryHeader } from '../../memdir/memoryScan.js'
import { scanMemoryFiles } from '../../memdir/memoryScan.js'
import { getAutoMemPath } from '../../memdir/paths.js'
import { readMemoriesForSurfacing } from '../../utils/attachments.js'
import { isEmbeddingEnabled } from '../flags.js'
import type { MemoryEntry, MemoryScope, RecoverySlice } from '../types.js'
import { buildEmbeddingIndex, queryEmbeddingIndex } from './localEmbeddingIndex.js'

/**
 * Rerank RecoverySlice array using embedding similarity instead of keyword score.
 * Updates each slice's relevanceScore in place.
 */
export function rerankSlicesWithEmbedding(
  slices: RecoverySlice[],
  query: string,
): RecoverySlice[] {
  if (!isEmbeddingEnabled() || slices.length === 0 || !query.trim()) return slices

  const index = buildEmbeddingIndex(
    slices.map(s => ({ id: s.sliceId, text: s.content, metadata: { sliceId: s.sliceId } })),
  )
  const results = queryEmbeddingIndex(index, query, slices.length)
  if (results.length === 0) return slices

  // Build lookup from queryEmbeddingIndex result
  const scoreMap = new Map(results.map(r => [String(r.metadata?.sliceId ?? r.id), r.score]))
  const maxScore = results[0].score

  return slices
    .map(s => ({
      ...s,
      relevanceScore: maxScore > 0 ? (scoreMap.get(s.sliceId) ?? 0) / maxScore : 0,
    }))
    .sort((a, b) => b.relevanceScore - a.relevanceScore)
}

/**
 * Rank memory files by embedding similarity to query (reads actual content).
 * Falls back to rankMemoryHeaders when embedding is disabled.
 */
export async function rankMemoriesWithEmbedding(
  query: string,
  scope: MemoryScope,
  limit: number,
  memoryDir: string,
  signal: AbortSignal,
): Promise<MemoryEntry[]> {
  if (scope !== 'project') return []

  const headers = await scanMemoryFiles(memoryDir, signal)
  if (headers.length === 0) return []

  // Read all memory file content
  const surfaced = await readMemoriesForSurfacing(
    headers.map(h => ({ path: h.filePath, mtimeMs: h.mtimeMs })),
    signal,
  )
  if (surfaced.length === 0) return []

  // Build embedding index from content
  const index = buildEmbeddingIndex(
    surfaced.map(m => ({
      id: m.path,
      text: m.content,
      metadata: { path: m.path, mtimeMs: m.mtimeMs },
    })),
  )
  const results = queryEmbeddingIndex(index, query, limit)

  // Map results back to MemoryEntry format, preserving embedding ranking order
  const surfaceByPath = new Map(surfaced.map(m => [m.path, m]))
  const headerByPath = new Map(headers.map(h => [h.filePath, h]))

  return results
    .map(r => {
      const memory = surfaceByPath.get(r.id)
      const header = headerByPath.get(r.id)
      if (!memory) return null
      return {
        id: memory.path,
        scope: 'project' as const,
        tags: header ? tagsFromHeader(header) : [],
        content: memory.content,
        createdAt: memory.mtimeMs,
        path: memory.path,
      }
    })
    .filter((m): m is MemoryEntry => m !== null)
}

function tagsFromHeader(header: MemoryHeader): string[] {
  const tags: string[] = []
  if (header.type) tags.push(header.type)
  const nameParts = header.filename
    .replace(/\.md$/i, '')
    .split(/[/\\_-]+/)
    .filter(part => part.length >= 2)
  tags.push(...nameParts)
  if (header.description) tags.push(header.description)
  return [...new Set(tags)]
}
