import type { UUID } from 'crypto'
import type { QuerySource } from '../../constants/querySource.js'
import { scanMemoryFiles, type MemoryHeader } from '../../memdir/memoryScan.js'
import { getAutoMemPath } from '../../memdir/paths.js'
import type { AttachmentMessage } from '../../types/message.js'
import {
  createAttachmentMessage,
  readMemoriesForSurfacing,
} from '../../utils/attachments.js'
import { isCognitiveScopeAllowed, isMemorySurfaceEnabled } from '../flags.js'
import type { MemoryEntry, MemoryScope } from '../types.js'
import { rankMemoryHeaders } from './rankMemories.js'

const DEFAULT_RECALL_LIMIT = 5

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

export async function recall(
  query: string,
  scope: MemoryScope,
  limit = DEFAULT_RECALL_LIMIT,
  signal?: AbortSignal,
): Promise<MemoryEntry[]> {
  if (scope !== 'project') return []

  const memoryDir = getAutoMemPath()
  const abortSignal = signal ?? new AbortController().signal
  const headers = await scanMemoryFiles(memoryDir, abortSignal)
  const ranked = rankMemoryHeaders(headers, query, limit)
  if (ranked.length === 0) return []

  const surfaced = await readMemoriesForSurfacing(
    ranked.map(header => ({ path: header.filePath, mtimeMs: header.mtimeMs })),
    abortSignal,
  )
  const headerByPath = new Map(ranked.map(header => [header.filePath, header]))

  return surfaced.map(memory => {
    const header = headerByPath.get(memory.path)
    return {
      id: memory.path,
      scope: 'project' as const,
      tags: header ? tagsFromHeader(header) : [],
      content: memory.content,
      createdAt: memory.mtimeMs,
      path: memory.path,
    }
  })
}

export async function surfaceOnSessionStart(
  query: string,
  ctx: {
    querySource: QuerySource
    agentId?: UUID
    signal?: AbortSignal
  },
): Promise<AttachmentMessage[]> {
  if (!isMemorySurfaceEnabled()) return []
  if (
    !isCognitiveScopeAllowed({
      querySource: ctx.querySource,
      agentId: ctx.agentId,
    })
  ) {
    return []
  }

  const memoryDir = getAutoMemPath()
  const abortSignal = ctx.signal ?? new AbortController().signal
  const headers = await scanMemoryFiles(memoryDir, abortSignal)
  const ranked = rankMemoryHeaders(headers, query, DEFAULT_RECALL_LIMIT)
  if (ranked.length === 0) return []

  const surfaced = await readMemoriesForSurfacing(
    ranked.map(header => ({ path: header.filePath, mtimeMs: header.mtimeMs })),
    abortSignal,
  )
  if (surfaced.length === 0) return []

  return [
    createAttachmentMessage({
      type: 'session_memory_surface',
      memories: surfaced.map(memory => ({
        path: memory.path,
        content: memory.content,
        mtimeMs: memory.mtimeMs,
        header: memory.header,
      })),
    }),
  ]
}
