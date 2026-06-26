import { requestReplan } from '../../cognitive/planning/PlanningOrchestrator.js'
import type { LocalCommandCall } from '../../types/command.js'
import type { Message } from '../../types/message.js'
import { createAttachmentMessage } from '../../utils/attachments.js'
import { createUserMessage } from '../../utils/messages.js'

export const call: LocalCommandCall = async (args, context) => {
  const reason = args.trim() || 'User requested replan via /replan'
  const result = requestReplan(reason, context)
  const messages: Message[] = []

  if (result.attachment) {
    messages.push(createAttachmentMessage(result.attachment))
  }
  if (result.contextHint) {
    messages.push(createUserMessage({
      content: result.contextHint,
      isMeta: true,
    }))
  }

  if (messages.length === 0) {
    return {
      type: 'text',
      value: 'No active executing plan to replan.',
    }
  }

  return {
    type: 'messages',
    messages,
    shouldQuery: true,
    displayText: 'Plan updated.',
  }
}
