import type { QuerySource } from '../../constants/querySource.js'
import type { ToolUseContext } from '../../Tool.js'
import type { Message } from '../../types/message.js'
import { createAttachmentMessage } from '../../utils/attachments.js'
import { createUserMessage } from '../../utils/messages.js'
import type { ToolErrorKind } from '../types.js'
import { isActive, onToolResult, storeForkReplanContext } from './PlanningOrchestrator.js'

export type PlanningToolResultParams = {
  toolName: string
  toolUseId: string
  isError: boolean
  errorKind: ToolErrorKind
  toolUseContext: ToolUseContext
  querySource: QuerySource
}

export function handlePlanningToolResult(
  params: PlanningToolResultParams,
): Message[] {
  const scope = {
    querySource: params.querySource,
    agentId: params.toolUseContext.agentId,
  }
  if (!isActive(scope)) return []

  // Store context for potential fork-agent auto-replan
  storeForkReplanContext({
    mainLoopModel: params.toolUseContext.options.mainLoopModel,
    tools: params.toolUseContext.options.tools as unknown[],
  })

  const replan = onToolResult({
    toolName: params.toolName,
    toolUseId: params.toolUseId,
    isError: params.isError,
    permissionDenied: params.errorKind === 'permission_denied',
    aborted: params.errorKind === 'aborted',
    validationError: params.errorKind === 'validation',
  })

  if (!replan) return []

  const messages: Message[] = []
  if (replan.attachment) {
    messages.push(createAttachmentMessage(replan.attachment))
  }
  if (replan.contextHint) {
    messages.push(createUserMessage({
      content: replan.contextHint,
      isMeta: true,
    }))
  }
  return messages
}
