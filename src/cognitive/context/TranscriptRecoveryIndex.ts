import type { QuerySource } from '../../constants/querySource.js'
import type { ToolUseContext } from '../../Tool.js'
import type { AttachmentMessage } from '../../types/message.js'
import {
  createAttachmentMessage,
  type Attachment,
} from '../../utils/attachments.js'
import type { Message } from '../../types/message.js'
import { createChildAbortController } from '../../utils/abortController.js'
import { isTranscriptRecoveryEnabled, isCognitiveScopeAllowed } from '../flags.js'
import { allocateRecoverySlices } from '../InjectionBudgetCoordinator.js'
import type { RecoveryPrefetch, RecoverySlice } from '../types.js'
import { buildRecoverySlicesFromMessages, getTranscriptMessageText } from './localIndex.js'

export type TranscriptRecoveryContext = {
  querySource: QuerySource
  agentId: ToolUseContext['agentId']
  abortController: AbortController
  memoryBytesAlreadyUsed?: number
}

export function startTranscriptRecoveryPrefetch(
  messages: readonly Message[],
  ctx: TranscriptRecoveryContext,
): RecoveryPrefetch | undefined {
  if (!isTranscriptRecoveryEnabled()) return undefined
  if (!isCognitiveScopeAllowed({ querySource: ctx.querySource, agentId: ctx.agentId })) {
    return undefined
  }

  const lastUser = messages.findLast(m => m.type === 'user' && !m.isMeta)
  const query = lastUser ? getTranscriptMessageText(lastUser) : ''
  if (!query || !/\s/.test(query.trim())) return undefined

  const controller = createChildAbortController(ctx.abortController)

  const promise = Promise.resolve().then(() => {
    if (controller.signal.aborted) return []
    const slices = buildRecoverySlicesFromMessages(messages, query)
    return allocateRecoverySlices(slices, {
      maxBytes: Number.MAX_SAFE_INTEGER,
      memoryBytesAlreadyUsed: ctx.memoryBytesAlreadyUsed ?? 0,
    })
  })

  const handle: RecoveryPrefetch = {
    promise,
    settledAt: null,
    consumedOnIteration: -1,
    [Symbol.dispose]() {
      controller.abort()
    },
  }
  void promise.finally(() => {
    handle.settledAt = Date.now()
  })
  return handle
}

export function recoverySlicesToAttachments(
  slices: RecoverySlice[],
): Attachment[] {
  if (slices.length === 0) return []
  return [
    {
      type: 'recovered_context',
      slices: slices.map(s => ({
        source: s.source,
        content: s.content,
        relevanceScore: s.relevanceScore,
      })),
    },
  ]
}

export function toAttachmentMessages(
  slices: RecoverySlice[],
): AttachmentMessage[] {
  return recoverySlicesToAttachments(slices).map(createAttachmentMessage)
}
