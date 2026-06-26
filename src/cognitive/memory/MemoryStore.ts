import { randomUUID } from 'crypto'
import { mkdir, readFile, writeFile } from 'fs/promises'
import { join } from 'path'
import type { UUID } from 'crypto'
import type { QuerySource } from '../../constants/querySource.js'
import { scanMemoryFiles, type MemoryHeader } from '../../memdir/memoryScan.js'
import { getAutoMemPath } from '../../memdir/paths.js'
import type { AttachmentMessage } from '../../types/message.js'
import {
  createAttachmentMessage,
  readMemoriesForSurfacing,
} from '../../utils/attachments.js'
import { parseFrontmatter } from '../../utils/frontmatterParser.js'
import {
  isCognitiveScopeAllowed,
  isEmbeddingEnabled,
  isMemorySurfaceEnabled,
  isMemoryWriteEnabled,
} from '../flags.js'
import { rankMemoriesWithEmbedding } from '../embedding/embeddingRanker.js'
import type { MemoryEntry, MemoryScope } from '../types.js'
import { rankMemoryHeaders } from './rankMemories.js'
import { findExistingMemoryByTags, mergeMemoryContent, parseFrontmatterTags } from './deduplicate.js'

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

  // When embedding is enabled, use content-based embedding ranking instead of header keyword matching
  if (isEmbeddingEnabled()) {
    return rankMemoriesWithEmbedding(query, scope, limit, memoryDir, abortSignal)
  }

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

/**
 * Normalise a tag string into a safe filename fragment.
 */
function tagToFilename(tag: string): string {
  return tag.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '')
}

/**
 * Render tags as a comma-separated YAML inline string.
 */
function yamlList(items: string[]): string {
  return items.join(', ')
}

/**
 * Parse tags from a memory file's frontmatter using the shared parser.
 */
export async function parseTagsFromFile(filePath: string): Promise<string[]> {
  try {
    const raw = await readFile(filePath, 'utf8')
    const { frontmatter } = parseFrontmatter(raw, filePath)
    return parseFrontmatterTags(frontmatter.tags)
  } catch {
    return []
  }
}

export type WriteMemoryParams = {
  scope: MemoryScope
  tags: string[]
  content: string
}

export async function write(
  params: WriteMemoryParams,
): Promise<{ path: string }> {
  if (!isMemoryWriteEnabled()) {
    return { path: '' }
  }

  const memoryDir = getAutoMemPath()
  await mkdir(memoryDir, { recursive: true }).catch(() => {})

  const signal = new AbortController().signal
  const existing = params.tags.length > 0
    ? await findExistingMemoryByTags(params.tags, memoryDir, signal)
    : null

  const now = Date.now()

  if (existing) {
    // Merge tags from new entry into existing file
    const { frontmatter } = parseFrontmatter(existing.content, existing.path)
    const existingTags = parseFrontmatterTags(frontmatter.tags)
    const mergedTags = [...new Set([...existingTags, ...params.tags])]

    const merged = mergeMemoryContent(existing.content, params.content, now, mergedTags)
    await writeFile(existing.path, merged, 'utf-8')
    return { path: existing.path }
  }

  // No overlap: create a new file
  const slug = params.tags.length > 0 ? tagToFilename(params.tags[0]) : 'memory'
  const filename = `${slug}-${randomUUID().slice(0, 8)}.md`
  const filePath = join(memoryDir, filename)
  const description = params.tags[0] || 'auto-memory'
  const content = [
    '---',
    `created: ${new Date(now).toISOString()}`,
    `tags: ${yamlList(params.tags)}`,
    `description: ${description}`,
    '---',
    '',
    params.content.slice(0, 4000),
  ].join('\n')
  await writeFile(filePath, content)

  return { path: filePath }
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

  // When embedding is enabled, use content-based ranking
  if (isEmbeddingEnabled()) {
    const memories = await rankMemoriesWithEmbedding(
      query,
      'project',
      DEFAULT_RECALL_LIMIT,
      memoryDir,
      abortSignal,
    )
    if (memories.length === 0) return []
    return [
      createAttachmentMessage({
        type: 'session_memory_surface',
        memories: memories.map(m => ({
          path: m.path ?? '',
          content: m.content,
          mtimeMs: m.createdAt as number,
        })),
      }),
    ]
  }

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
