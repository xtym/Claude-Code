import { isMemoryWriteEnabled } from '../flags.js'
import { write } from './MemoryStore.js'
import type { REPLHookContext } from '../../utils/hooks/postSamplingHooks.js'

export async function tryCognitiveMemoryWrite(
  stopHookContext: REPLHookContext,
): Promise<void> {
  if (!isMemoryWriteEnabled()) return
  if (stopHookContext.toolUseContext.agentId) return

  const lastAssistant = stopHookContext.messages
    .findLast(m => m.type === 'assistant')
  if (!lastAssistant) return

  // Extract text from the assistant's message content blocks
  const content = extractTextFromMessage(lastAssistant)
  if (!content || content.length < 100) return

  // Session memory write: project scope, auto-categorized tags
  const tags = extractMemoryTags(content, stopHookContext)
  await write({
    scope: 'project',
    tags,
    content: content.slice(0, 4000),
  })
}

function extractTextFromMessage(
  msg: { type: string; message?: { content?: unknown } },
): string | null {
  if (!msg.message?.content) return null
  const content = msg.message.content
  if (typeof content === 'string') return content
  if (Array.isArray(content)) {
    const parts = content
      .filter((b: unknown): b is { type: string; text?: string } =>
        typeof b === 'object' && b !== null && (b as Record<string, unknown>).type === 'text',
      )
      .map((b) => (b as { text?: string }).text ?? '')
    return parts.join('\n').trim() || null
  }
  return null
}

function extractMemoryTags(
  content: string,
  _ctx: REPLHookContext,
): string[] {
  // Phase 3 v1: extract top 3 noun-phrase keywords from content
  const stopWords = new Set([
    'this', 'that', 'with', 'from', 'have', 'been', 'will', 'what',
    'when', 'where', 'which', 'their', 'there', 'about', 'would',
    'could', 'should', 'after', 'before', 'between', 'other', 'using',
    'being', 'done', 'made', 'make', 'just', 'also', 'very', 'than',
  ])

  const words = content
    .toLowerCase()
    .split(/[^a-z0-9]+/)
    .filter(w => w.length >= 4 && !stopWords.has(w))

  const freq: Record<string, number> = {}
  for (const w of words) {
    freq[w] = (freq[w] ?? 0) + 1
  }
  return Object.entries(freq)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3)
    .map(([word]) => word)
}
