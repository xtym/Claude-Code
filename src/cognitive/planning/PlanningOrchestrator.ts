import { randomUUID } from 'crypto'
import type { QuerySource } from '../../constants/querySource.js'
import type { ToolUseContext } from '../../Tool.js'
import type { Attachment } from '../../utils/attachments.js'
import type { Message } from '../../types/message.js'
import {
  isCognitiveScopeAllowed,
  isPlanningEnabled,
} from '../flags.js'
import type {
  PlanFailureRecord,
  PlanState,
  ToolErrorKind,
} from '../types.js'
import { buildPlanUpdatedAttachment } from './replanAttachments.js'
import {
  firstRunnableStepId,
  parseStepsFromPlanMd,
  planFromApprovedMarkdown,
  readPlanState,
  writePlanState,
} from './planState.js'
import { classifyToolError } from './toolErrorKind.js'

const RECOVERABLE_FAILURE_THRESHOLD = 3
const MAX_AUTO_REPLANS_PER_STEP = 2
const MAX_FAILURE_LOG = 3

type PlanningScope = {
  querySource: QuerySource
  agentId?: ToolUseContext['agentId']
}

type PlanningContext = PlanningScope | ToolUseContext

export type ToolResultParams = {
  toolName: string
  toolUseId: string
  isError: boolean
  permissionDenied?: boolean
  aborted?: boolean
  validationError?: boolean
}

export type ReplanOutput = {
  attachment: Attachment | null
  contextHint: string
}

let sessionPlan: PlanState | null = null
const consecutiveRecoverableErrors = new Map<string, number>()
const validationErrorsByStep = new Map<string, number>()
const failureLog: PlanFailureRecord[] = []

function scopeFromContext(ctx: PlanningContext): PlanningScope {
  if ('options' in ctx) {
    return {
      querySource: ctx.options.querySource ?? 'repl_main_thread',
      agentId: ctx.agentId,
    }
  }
  return ctx
}

export function resetPlanningOrchestratorForTests(): void {
  resetPlanningOrchestratorForTesting()
}

export function resetPlanningOrchestratorForTesting(): void {
  sessionPlan = null
  consecutiveRecoverableErrors.clear()
  validationErrorsByStep.clear()
  failureLog.length = 0
}

export function setSessionPlanForTests(plan: PlanState | null): void {
  sessionPlan = plan
}

export function getSessionPlan(): PlanState | null {
  return sessionPlan
}

export function getFailureLog(): PlanFailureRecord[] {
  return failureLog.slice()
}

function scopeAllowed(scope: PlanningScope): boolean {
  return isCognitiveScopeAllowed(scope)
}

function loadActivePlan(): PlanState | null {
  const diskPlan = readPlanState()
  if (diskPlan) {
    sessionPlan = diskPlan.status === 'executing' ? diskPlan : null
    return sessionPlan
  }
  if (sessionPlan?.status === 'executing') return sessionPlan
  sessionPlan = null
  return null
}

function activeStep(plan: PlanState) {
  if (!plan.activeStepId) return undefined
  return plan.steps.find(step => step.id === plan.activeStepId)
}

function stepNumber(stepId: string | undefined): string {
  return stepId?.replace(/^step-/, '') ?? '?'
}

function revisePlanAfterFailure(plan: PlanState, reason: string): ReplanOutput {
  const step = activeStep(plan)
  const revisedDescription = step
    ? `${step.description} (revised: try alternate approach)`
    : 'Revise failed step'

  const nextSteps = plan.steps.map(entry => {
    if (entry.id !== plan.activeStepId) return entry
    return {
      ...entry,
      description: revisedDescription,
      status: 'pending' as const,
      retryCount: entry.retryCount + 1,
    }
  })

  const replanCountsByStepId = {
    ...(plan.replanCountsByStepId ?? {}),
  }
  if (plan.activeStepId) {
    replanCountsByStepId[plan.activeStepId] =
      (replanCountsByStepId[plan.activeStepId] ?? 0) + 1
  }

  const revised: PlanState = {
    ...plan,
    steps: nextSteps,
    activeStepId: plan.activeStepId,
    replanCountsByStepId,
  }

  sessionPlan = revised
  writePlanState(revised)

  const contextHint = `[Plan revised after step failure] Step ${stepNumber(plan.activeStepId)} failed ${RECOVERABLE_FAILURE_THRESHOLD} times. Follow the updated plan in the attachment.`

  return {
    attachment: buildPlanUpdatedAttachment(revised, reason),
    contextHint,
  }
}

export function planFromRevisedMarkdown(planMd: string): PlanState | null {
  if (!planMd.trim()) return null

  const steps = parseStepsFromPlanMd(planMd)
  if (steps.length === 0) return null

  const planId = sessionPlan?.id ?? randomUUID()

  const activeStepId = firstRunnableStepId({ id: planId, steps, status: 'executing' })
  const runningSteps = steps.map(step => ({
    ...step,
    status: step.id === activeStepId ? ('running' as const) : ('pending' as const),
  }))

  const revised: PlanState = {
    id: planId,
    steps: runningSteps,
    status: 'executing',
    activeStepId,
    replanCountsByStepId: {},
  }

  sessionPlan = revised
  writePlanState(revised)
  clearFailureCounters(activeStepId ?? '')
  consecutiveRecoverableErrors.clear()
  validationErrorsByStep.clear()

  return revised
}

function shouldTriggerReplan(
  stepId: string,
  errorKind: ToolErrorKind,
): boolean {
  if (errorKind === 'permission_denied' || errorKind === 'aborted') {
    return false
  }
  if (errorKind === 'recoverable') {
    const count = (consecutiveRecoverableErrors.get(stepId) ?? 0) + 1
    consecutiveRecoverableErrors.set(stepId, count)
    return count >= RECOVERABLE_FAILURE_THRESHOLD
  }
  if (errorKind === 'validation') {
    const count = (validationErrorsByStep.get(stepId) ?? 0) + 1
    validationErrorsByStep.set(stepId, count)
    return count >= 2
  }
  return false
}

function recordFailure(
  plan: PlanState,
  toolName: string,
  toolUseId: string,
  errorKind: ToolErrorKind,
): void {
  if (!plan.activeStepId) return
  failureLog.push({
    stepId: plan.activeStepId,
    toolName,
    toolUseId,
    errorKind,
    timestamp: Date.now(),
  })
  while (failureLog.length > MAX_FAILURE_LOG) {
    failureLog.shift()
  }
}

function clearFailureCounters(stepId: string): void {
  consecutiveRecoverableErrors.delete(stepId)
  validationErrorsByStep.delete(stepId)
}

function advanceAfterStepSuccess(plan: PlanState): PlanState {
  const current = activeStep(plan)
  if (!current) return plan
  const steps = plan.steps.map(step => {
    if (step.id === current.id) {
      return { ...step, status: 'done' as const }
    }
    return step
  })
  const nextActiveStepId = firstRunnableStepId({ ...plan, steps })
  const nextSteps = steps.map(step => {
    if (step.id === nextActiveStepId && step.status === 'pending') {
      return { ...step, status: 'running' as const }
    }
    return step
  })
  const next: PlanState = {
    ...plan,
    steps: nextSteps,
    activeStepId: nextActiveStepId,
  }
  sessionPlan = next
  writePlanState(next)
  return next
}

function isCircuitBreakerOpen(plan: PlanState, stepId: string): boolean {
  return (plan.replanCountsByStepId?.[stepId] ?? 0) >= MAX_AUTO_REPLANS_PER_STEP
}

function markStepNeedsGuidance(plan: PlanState): ReplanOutput {
  if (!plan.activeStepId) {
    return {
      attachment: null,
      contextHint:
        '[Plan step needs guidance] Automatic replan limit reached for the active step. Use /replan or adjust the plan manually.',
    }
  }

  const steps = plan.steps.map(step =>
    step.id === plan.activeStepId
      ? { ...step, status: 'failed' as const }
      : step,
  )
  const updated: PlanState = { ...plan, steps }
  sessionPlan = updated
  writePlanState(updated)

  return {
    attachment: null,
    contextHint:
      '[Plan step needs guidance] Needs your guidance — automatic replan limit reached for the active step. Use /replan or adjust the plan manually.',
  }
}

export function isActive(ctx: PlanningContext): boolean {
  const scope = scopeFromContext(ctx)
  if (!isPlanningEnabled() || !scopeAllowed(scope)) return false
  return loadActivePlan() !== null
}

export function onPlanApproved(planMarkdown: string): PlanState {
  if (!isPlanningEnabled()) {
    return planFromApprovedMarkdown(planMarkdown, randomUUID())
  }
  const plan = planFromApprovedMarkdown(planMarkdown, randomUUID())
  if (plan.steps.length === 0) return plan
  sessionPlan = plan
  writePlanState(plan)
  clearFailureCounters(plan.activeStepId ?? '')
  return plan
}

export function onToolResult(params: ToolResultParams): ReplanOutput | null {
  const plan = loadActivePlan()
  if (!plan?.activeStepId) return null

  const errorKind = classifyToolError(
    params.isError,
    params.permissionDenied ?? false,
    params.aborted ?? false,
    params.validationError ?? false,
  )

  if (!params.isError) {
    clearFailureCounters(plan.activeStepId)
    advanceAfterStepSuccess(plan)
    return null
  }

  recordFailure(plan, params.toolName, params.toolUseId, errorKind)

  if (!shouldTriggerReplan(plan.activeStepId, errorKind)) return null

  if (isCircuitBreakerOpen(plan, plan.activeStepId)) {
    return markStepNeedsGuidance(plan)
  }

  clearFailureCounters(plan.activeStepId)
  return revisePlanAfterFailure(
    plan,
    `Step ${plan.activeStepId} failed repeatedly during tool execution`,
  )
}

export function requestReplan(
  reason: string,
  _context?: ToolUseContext,
): ReplanOutput {
  const plan = loadActivePlan()
  if (!plan?.activeStepId) {
    return { attachment: null, contextHint: '' }
  }

  if (isCircuitBreakerOpen(plan, plan.activeStepId)) {
    return markStepNeedsGuidance(plan)
  }

  return revisePlanAfterFailure(plan, reason || 'User requested replan')
}

export function replanOutputToMessages(result: ReplanOutput): Message[] {
  const messages: Message[] = []
  if (result.attachment) {
    messages.push({
      attachment: result.attachment,
      type: 'attachment',
      uuid: randomUUID(),
      timestamp: new Date().toISOString(),
    })
  }
  if (result.contextHint) {
    messages.push({
      type: 'user',
      uuid: randomUUID(),
      message: { role: 'user', content: result.contextHint },
      isMeta: true,
      timestamp: new Date().toISOString(),
    })
  }
  return messages
}

export async function* requestReplanStream(
  reason: string,
  context?: ToolUseContext,
): AsyncGenerator<Message> {
  for (const message of replanOutputToMessages(requestReplan(reason, context))) {
    yield message
  }
}
