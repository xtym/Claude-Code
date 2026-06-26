import { randomUUID } from 'crypto'
import type { Message } from '../../types/message.js'
import { getContentText, isCompactBoundaryMessage } from '../../utils/messages.js'
import type { RecoverySlice } from '../types.js'
import { scoreRecoverySlice } from './relevanceScore.js'

export function getTranscriptMessageText(message: Message): string | null {
  if (message.type === 'user' || message.type === 'assistant') {
    const withContent = message as Message & { content?: unknown }
    if (typeof withContent.content === 'string') return withContent.content
    if (Array.isArray(withContent.content)) {
      return withContent.content
        .filter((b): b is { type: 'text'; text: string } => b.type === 'text')
        .map(b => b.text)
        .join('\n')
    }
    if (message.type === 'user' && message.message?.content !== undefined) {
      return getContentText(message.message.content)
    }
    if (message.type === 'assistant' && message.message?.content !== undefined) {
      if (typeof message.message.content === 'string') return message.message.content
      if (Array.isArray(message.message.content)) {
        return (
          message.message.content
            .filter((b): b is { type: 'text'; text: string } => b.type === 'text')
            .map(b => b.text)
            .join('\n')
            .trim() || null
        )
      }
    }
  }
  return null
}

export function buildRecoverySlicesFromMessages(
  messages: readonly Message[],
  query: string,
): RecoverySlice[] {
  const boundaryIndex = messages.findLastIndex(m => isCompactBoundaryMessage(m))
  const endIndex = boundaryIndex === -1 ? messages.length : boundaryIndex
  const slices: RecoverySlice[] = []

  for (let i = 0; i < endIndex; i++) {
    const m = messages[i]
    if (!m) continue
    if (m.type === 'attachment') {
      const attachment = (m as { attachment?: { type?: string } }).attachment
      if (attachment?.type === 'relevant_memories') continue
    }
    const text = getTranscriptMessageText(m)
    if (!text || text.trim().length < 20) continue

    const score = scoreRecoverySlice({
      content: text,
      query,
      turnIndex: i,
      maxTurnIndex: messages.length,
      compactBoundaryTurn: boundaryIndex === -1 ? undefined : boundaryIndex,
    })
    if (score <= 0) continue

    slices.push({
      sliceId: randomUUID(),
      source: 'transcript',
      content: text.slice(0, 2000),
      relevanceScore: score,
      tokenEstimate: Math.ceil(text.length / 4),
      compactBoundaryId:
        boundaryIndex === -1 ? undefined : String(boundaryIndex),
    })
  }

  return slices
}

export function snapshotPreCompactRegion(
  messages: readonly Message[],
  boundaryId: string,
): RecoverySlice[] {
  const summaryText = messages
    .map(getTranscriptMessageText)
    .filter((t): t is string => !!t)
    .join('\n')
    .slice(0, 4000)

  if (!summaryText) return []

  return [
    {
      sliceId: randomUUID(),
      source: 'compact_summary',
      content: summaryText,
      relevanceScore: 1,
      tokenEstimate: Math.ceil(summaryText.length / 4),
      compactBoundaryId: boundaryId,
    },
  ]
}
