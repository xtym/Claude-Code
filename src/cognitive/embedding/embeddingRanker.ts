import type { MemoryHeader } from '../../memdir/memoryScan.js'
import { scanMemoryFiles } from '../../memdir/memoryScan.js'
import { getAutoMemPath } from '../../memdir/paths.js'
import { readMemoriesForSurfacing } from '../../utils/attachments.js'
import { isEmbeddingEnabled } from '../flags.js'
import type { MemoryEntry, MemoryScope, RecoverySlice } from '../types.js'
import { buildEmbeddingIndex, queryEmbeddingIndex } from './localEmbeddingIndex.js'
import type { EmbeddingIndexEntry } from './localEmbeddingIndex.js'

// ---------------------------------------------------------------------------
// Module-level cache: memory dir path → cached index + last known mtimes
// Memory files only change during stop hooks, so we avoid rebuilding the
// embedding index on every turn when nothing has changed.
// ---------------------------------------------------------------------------

const indexCache = new Map<
  string,
  {
    index: EmbeddingIndexEntry[]
    dirMtime: number // timestamp of last scan
    fileMtimes: Map<string, number> // per-file mtimes
  }
>()

const CACHE_TTL_MS = 60_000 // 1 minute max age regardless of mtime

/**
 * Get mtime of a path, defaulting to 0 on error.
 */
async function getMtime(path: string): Promise<number> {
  try {
    const { stat } = await import('fs/promises')
    const s = await stat(path)
    return s.mtimeMs
  } catch {
    return 0
  }
}

/**
 * Cache-aware version of building memory embedding index.
 * Skips rebuild if memory dir and all files have unchanged mtimes.
 */
async function getCachedMemoryIndex(
  memoryDir: string,
  headers: Array<{ filePath: string; mtimeMs: number }>,
  surfaced: Array<{ path: string; content: string }>,
  signal: AbortSignal,
): Promise<EmbeddingIndexEntry[]> {
  const cached = indexCache.get(memoryDir)
  const now = Date.now()

  const dirMtime = await getMtime(memoryDir)

  if (cached) {
    // Check if cache is still fresh
    if (now - cached.dirMtime < CACHE_TTL_MS) {
      // Verify all files have same mtimes
      let stale = false
      for (const h of headers) {
        const prevMtime = cached.fileMtimes.get(h.filePath)
        if (prevMtime !== h.mtimeMs) {
          stale = true
          break
        }
      }
      if (!stale && cached.fileMtimes.size === headers.length) {
        signal?.throwIfAborted()
        return cached.index
      }
    }
  }

  // Rebuild index
  const index = buildEmbeddingIndex(
    surfaced.map(m => ({ id: m.path, text: m.content })),
  )

  // Update cache
  indexCache.set(memoryDir, {
    index,
    dirMtime: now,
    fileMtimes: new Map(headers.map(h => [h.filePath, h.mtimeMs])),
  })

  return index
}

/**
 * Clear the embedding index cache (useful for tests).
 */
export function clearEmbeddingCache(): void {
  indexCache.clear()
}

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

  // Build embedding index from content (uses mtime-based cache)
  const index = await getCachedMemoryIndex(memoryDir, headers, surfaced, signal)
  if (index.length === 0) return []

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
