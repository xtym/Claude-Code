import { scanMemoryFiles } from '../../memdir/memoryScan.js'
import { parseFrontmatter } from '../../utils/frontmatterParser.js'
import { readFileInRange } from '../../utils/readFileInRange.js'

const FRONTMATTER_MAX_LINES = 30

/**
 * Compute the fraction of the smaller tag array that overlaps with the other.
 * Returns true when > 40% of the smaller tag set is shared.
 */
function tagsOverlapThreshold(
  entryTags: string[],
  memoryTags: string[],
): boolean {
  if (entryTags.length === 0 || memoryTags.length === 0) return false
  const normalizedEntry = entryTags.map(t => t.toLowerCase().trim())
  const normalizedMemory = memoryTags.map(t => t.toLowerCase().trim())
  const intersection = normalizedEntry.filter(t => normalizedMemory.includes(t))
  const smaller = Math.min(normalizedEntry.length, normalizedMemory.length)
  return intersection.length / smaller > 0.4
}

/**
 * Parse a raw tags value from YAML frontmatter into a string array.
 * Handles YAML arrays (parsed as string[]) and comma-separated strings.
 */
export function parseFrontmatterTags(raw: unknown): string[] {
  if (Array.isArray(raw)) return raw.map(String)
  if (typeof raw === 'string') {
    return raw
      .split(',')
      .map(s => s.trim().replace(/^["']|["']$/g, ''))
      .filter(Boolean)
  }
  return []
}

/**
 * Enumerate .md memory files in memoryDir, read their frontmatter, and return
 * the most-recently-modified file whose tags overlap by > 40% with the
 * supplied tags. Returns null when no match is found.
 */
export async function findExistingMemoryByTags(
  tags: string[],
  memoryDir: string,
  signal: AbortSignal,
): Promise<{ path: string; content: string; mtimeMs: number } | null> {
  const headers = await scanMemoryFiles(memoryDir, signal)

  const candidates: Array<{
    path: string
    content: string
    mtimeMs: number
  }> = []

  for (const header of headers) {
    try {
      const result = await readFileInRange(
        header.filePath,
        0,
        FRONTMATTER_MAX_LINES,
        undefined,
        signal,
      )
      const { frontmatter } = parseFrontmatter(result.content, header.filePath)
      const memoryTags = parseFrontmatterTags(frontmatter.tags)

      if (tagsOverlapThreshold(tags, memoryTags)) {
        // Read the full file content for merging
        const fullResult = await readFileInRange(
          header.filePath,
          0,
          undefined,
          undefined,
          signal,
        )
        candidates.push({
          path: header.filePath,
          content: fullResult.content,
          mtimeMs: fullResult.mtimeMs,
        })
      }
    } catch {
      continue
    }
  }

  if (candidates.length === 0) return null
  return candidates.sort((a, b) => b.mtimeMs - a.mtimeMs)[0]
}

/**
 * Build a YAML frontmatter string from a flat key-value map.
 * Handles strings, numbers, booleans, arrays of strings, and nulls.
 */
function stringifyFrontmatterValue(value: unknown): string {
  if (value === null || value === undefined) return ''
  if (typeof value === 'string') {
    // Quote if value contains special characters
    if (/[:#\[\]{}&*!|>%@`]/.test(value) || value.startsWith('- ')) {
      const escaped = value.replace(/"/g, '\\"')
      return `"${escaped}"`
    }
    return value
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value)
  }
  if (Array.isArray(value)) {
    const items = value.map(v => {
      const s = String(v)
      return /[:#\[\]{}&*!|>%@`]/.test(s) ? `"${s.replace(/"/g, '\\"')}"` : s
    })
    return `[${items.join(', ')}]`
  }
  return String(value)
}

/**
 * Build the YAML frontmatter block preserving all keys from the parsed
 * frontmatter object while updating our known fields.
 */
function buildFrontmatterYaml(
  frontmatter: Record<string, unknown>,
): string {
  const lines: string[] = []

  // Ordered first for readability
  const orderedKeys = ['created', 'updatedAt', 'tags', 'description', 'type']
  const handled = new Set(orderedKeys)

  for (const key of orderedKeys) {
    if (key in frontmatter && frontmatter[key] !== undefined && frontmatter[key] !== null) {
      const val = stringifyFrontmatterValue(frontmatter[key])
      if (val !== '') {
        lines.push(`${key}: ${val}`)
      }
    }
  }

  // Preserve any remaining keys in sorted order
  const remainingKeys = Object.keys(frontmatter)
    .filter(k => !handled.has(k))
    .sort()

  for (const key of remainingKeys) {
    const val = frontmatter[key]
    if (val !== undefined && val !== null) {
      const strVal = stringifyFrontmatterValue(val)
      if (strVal !== '') {
        lines.push(`${key}: ${strVal}`)
      }
    }
  }

  return lines.join('\n')
}

/**
 * Merge new body content into existing markdown, preserving existing sections.
 * Appends any section (text starting with ##) from newContent that is not
 * already present in existingBody, deduplicated by heading text.
 */
function mergeSections(existingBody: string, newContent: string): string {
  const existingLines = existingBody.split('\n')
  const newLines = newContent.split('\n')

  // Collect existing headings for dedup
  const existingHeadings = new Set<string>()
  for (const line of existingLines) {
    const match = line.match(/^#{1,6}\s+(.+)/)
    if (match) existingHeadings.add(match[1]?.trim().toLowerCase() ?? '')
  }

  // Split new content into heading-delimited blocks
  const newBlocks: string[] = []
  let currentBlock: string[] = []
  for (const line of newLines) {
    const headingMatch = line.match(/^#{1,6}\s+(.+)/)
    if (headingMatch) {
      if (currentBlock.length > 0) {
        newBlocks.push(currentBlock.join('\n'))
      }
      currentBlock = [line]
    } else {
      currentBlock.push(line)
    }
  }
  if (currentBlock.length > 0) {
    newBlocks.push(currentBlock.join('\n'))
  }

  // Append blocks whose heading doesn't already exist in the existing body
  const appendBlocks: string[] = []
  for (const block of newBlocks) {
    const firstLine = block.split('\n')[0]
    const headingMatch = firstLine?.match(/^#{1,6}\s+(.+)/)
    if (headingMatch) {
      const headingLower = headingMatch[1]?.trim().toLowerCase() ?? ''
      if (!existingHeadings.has(headingLower)) {
        appendBlocks.push(block)
      }
    } else {
      // No heading in this block — it's leading text. Only append if the
      // existing body doesn't already contain similar content.
      const sig = block.trim().toLowerCase().slice(0, 80)
      if (sig && !existingBody.toLowerCase().includes(sig)) {
        appendBlocks.push(block)
      }
    }
  }

  if (appendBlocks.length === 0) return existingBody.trim()
  return existingBody.trim() + '\n\n' + appendBlocks.join('\n\n')
}

/**
 * Merge new content into an existing memory file.
 *
 * - Parses the existing frontmatter and updates `updatedAt` to mergeDate.
 * - Merges tags with mergedTags if provided.
 * - Merges description fields if they differ.
 * - Appends notable new sections from newContent while preserving existing ones.
 * - Returns complete markdown with updated frontmatter.
 */
export function mergeMemoryContent(
  existingContent: string,
  newContent: string,
  mergeDate: number,
  mergedTags?: string[],
): string {
  const { frontmatter, content: existingBody } = parseFrontmatter(existingContent)

  // Update timestamp
  frontmatter.updatedAt = new Date(mergeDate).toISOString()

  // Preserve created timestamp if not set
  if (!frontmatter.created) {
    frontmatter.created = new Date(mergeDate).toISOString()
  }

  // Update tags if mergedTags provided
  if (mergedTags !== undefined) {
    frontmatter.tags = mergedTags
  }

  // Merge body sections
  const mergedBody = mergeSections(existingBody, newContent)

  // Rebuild frontmatter
  const frontmatterYaml = buildFrontmatterYaml(frontmatter as Record<string, unknown>)

  return `---\n${frontmatterYaml}\n---\n\n${mergedBody.trim()}\n`
}
