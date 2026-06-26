import type { UUID } from 'crypto'
import type { QuerySource } from '../../constants/querySource.js'
import type { AttachmentMessage, Message } from '../../types/message.js'
import { surfaceOnSessionStart } from './MemoryStore.js'

export function isFirstUserTurnInSession(
  messages: readonly Message[] | undefined,
): boolean {
  if (!messages || messages.length === 0) return true
  return !messages.some(m => m.type === 'assistant')
}

export async function maybeAppendSessionMemorySurface(params: {
  inputString: string | null
  messages: readonly Message[] | undefined
  querySource: QuerySource
  agentId?: UUID
  attachmentMessages: AttachmentMessage[]
}): Promise<void> {
  const { inputString, messages, querySource, agentId, attachmentMessages } =
    params

  if (!isFirstUserTurnInSession(messages)) return
  if (inputString === null) return
  if (inputString.startsWith('/')) return

  const surfaced = await surfaceOnSessionStart(inputString, {
    querySource,
    agentId,
  })
  attachmentMessages.push(...surfaced)
}
