import { randomUUID } from 'crypto'
import { readFileSync } from 'fs'
import { getSystemPrompt } from '../../constants/prompts.js'
import { getSystemContext, getUserContext } from '../../context.js'
import { getSessionPlan, requestReplan } from '../../cognitive/planning/PlanningOrchestrator.js'
import type { LocalCommandCall } from '../../types/command.js'
import type { Message } from '../../types/message.js'
import { FILE_READ_TOOL_NAME } from '../../tools/FileReadTool/prompt.js'
import { FILE_WRITE_TOOL_NAME } from '../../tools/FileWriteTool/prompt.js'
import { createAttachmentMessage } from '../../utils/attachments.js'
import { runForkedAgent } from '../../utils/forkedAgent.js'
import { createUserMessage } from '../../utils/messages.js'
import { getPlanFilePath } from '../../utils/plans.js'
import { asSystemPrompt } from '../../utils/systemPromptType.js'

export const call: LocalCommandCall = async (args, context) => {
  const reason = args.trim() || 'User requested replan via /replan'

  // Try fork-agent replan first
  try {
    const { tools, mainLoopModel } = context.options

    const [rawSystemPrompt, userContext, systemContext] = await Promise.all([
      getSystemPrompt(tools, mainLoopModel),
      getUserContext(),
      getSystemContext(),
    ])

    // Read current plan markdown
    let planMd = ''
    try {
      const planPath = getPlanFilePath()
      planMd = readFileSync(planPath, 'utf-8')
    } catch {
      // Plan file may not exist yet; fall through
    }

    const forkPrompt = [
      `You are a plan revision specialist. Your task is to revise the session plan in response to: ${reason}`,
      '',
      planMd ? `Current plan:\n\n${planMd}\n\n---\n` : '',
      'Read the plan file to see the current steps. Then revise the plan and write it back.',
      '',
      `Revision instructions:
1. Read the plan file using ${FILE_READ_TOOL_NAME}
2. Analyze what went wrong and how to fix it
3. Rewrite the plan file using ${FILE_WRITE_TOOL_NAME} with updated steps
4. Keep the same overall structure but revise descriptions, add steps, or reorder as needed
5. The plan is markdown with numbered steps (1., 2., 3. etc.) or checklist items (- [ ])
6. Mark completed steps as "- [x] step description"
7. Add your revision reasoning as a comment at the top of the file`,
      '',
      'Write the revised plan file now.',
    ].join('\n')

    // Create fork context messages with the current plan if available
    const forkContextMessages = planMd
      ? [createUserMessage({ content: `Current plan to revise:\n\n${planMd}` })]
      : []

    const result = await runForkedAgent({
      promptMessages: [createUserMessage({ content: forkPrompt })],
      cacheSafeParams: {
        systemPrompt: asSystemPrompt(rawSystemPrompt),
        userContext,
        systemContext,
        toolUseContext: context,
        forkContextMessages,
      },
      canUseTool: async (tool: { name: string }) => {
        const allowed =
          tool.name === FILE_READ_TOOL_NAME ||
          tool.name === FILE_WRITE_TOOL_NAME ||
          tool.name === 'Bash'
        if (allowed) {
          return { behavior: 'allow' as const }
        }
        return {
          behavior: 'deny' as const,
          message: 'Only Read, Write, and Bash tools are allowed for replan',
          decisionReason: {
            type: 'other' as const,
            reason: 'replan_fork',
          },
        }
      },
      querySource: 'session_memory',
      forkLabel: 'replan',
      maxTurns: 5,
      skipTranscript: true,
    })

    // Read the revised plan state from disk
    let newPlanMd = ''
    try {
      const planPath = getPlanFilePath()
      newPlanMd = readFileSync(planPath, 'utf-8')
    } catch {
      // Plan file may have been deleted or not written
    }

    if (newPlanMd && newPlanMd !== planMd) {
      // Re-load the plan state from the JSON sidecar (the fork agent should
      // have written the plan.md, and planFromRevisedMarkdown / getSessionPlan
      // picks up the sidecar if it was also updated)
      const updatedPlan = getSessionPlan()

      const attachment = updatedPlan
        ? {
            type: 'plan_updated' as const,
            reason,
            planId: updatedPlan.id,
            activeStepId: updatedPlan.activeStepId,
            steps: updatedPlan.steps.map(step => ({
              id: step.id,
              description: step.description,
              status: step.status,
            })),
          }
        : null

      const messages: Message[] = []
      if (attachment) {
        messages.push(createAttachmentMessage(attachment))
      }
      messages.push(
        createUserMessage({
          content: `[Plan revised via sub-agent] ${reason}`,
          isMeta: true,
        }),
      )

      return {
        type: 'messages',
        messages,
        shouldQuery: true,
        displayText: 'Plan revised by sub-agent.',
      }
    }
  } catch (err) {
    // Fall through to programmatic replan
  }

  // Fallback: programmatic replan
  const result = requestReplan(reason, context)
  const messages: Message[] = []

  if (result.attachment) {
    messages.push(createAttachmentMessage(result.attachment))
  }
  if (result.contextHint) {
    messages.push(
      createUserMessage({
        content: result.contextHint,
        isMeta: true,
      }),
    )
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
