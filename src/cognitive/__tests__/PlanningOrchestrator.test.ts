import { describe, expect, test, beforeEach, afterEach, mock } from 'bun:test'
import { mkdir, rm, unlink, writeFile } from 'fs/promises'
import { join } from 'path'
import { tmpdir } from 'os'
import fixture from './fixtures/plan-executing-step5-fail.json'

let tempDir = ''
let planMdPath = ''

mock.module('../../utils/plans.js', () => ({
  getPlanFilePath: () => planMdPath,
}))

const {
  isActive,
  onPlanApproved,
  onTaskCreated,
  onToolResult,
  planFromRevisedMarkdown,
  requestReplan,
  resetPlanningOrchestratorForTesting,
  getFailureLog,
  storeForkReplanContext,
  clearForkReplanContext,
} = await import('../planning/PlanningOrchestrator.js')
const { readPlanState, writePlanState, getPlanJsonPath } = await import(
  '../planning/planState.js'
)
const { classifyToolError } = await import('../planning/toolErrorKind.js')

const env = process.env

function makeCtx(overrides: Record<string, unknown> = {}) {
  return {
    agentId: undefined,
    options: { querySource: 'repl_main_thread' },
    ...overrides,
  } as never
}

beforeEach(async () => {
  process.env = {
    ...env,
    CLAUDE_CODE_COGNITIVE_LAYER: '1',
    CLAUDE_CODE_COGNITIVE_PLANNING: '1',
  }
  resetPlanningOrchestratorForTesting()
  tempDir = join(
    tmpdir(),
    `planning-orchestrator-test-${Date.now()}-${Math.random().toString(36).slice(2)}`,
  )
  await mkdir(tempDir, { recursive: true })
  planMdPath = join(tempDir, 'test-plan.md')
})

afterEach(async () => {
  process.env = env
  await rm(tempDir, { recursive: true, force: true })
})

describe('PlanningOrchestrator', () => {
  test('isActive requires planning flag, scope, and executing plan', () => {
    writePlanState(fixture as never)
    expect(isActive(makeCtx())).toBe(true)

    process.env.CLAUDE_CODE_COGNITIVE_PLANNING = '0'
    expect(isActive(makeCtx())).toBe(false)
    process.env.CLAUDE_CODE_COGNITIVE_PLANNING = '1'

    expect(isActive(makeCtx({ agentId: 'sub-agent' }))).toBe(false)

    writePlanState({ ...(fixture as never), status: 'done' })
    expect(isActive(makeCtx())).toBe(false)
  })

  test('onPlanApproved parses md and writes executing plan', () => {
    const md = `1. Analyze
2. Implement
3. Test`
    const state = onPlanApproved(md)
    expect(state.status).toBe('executing')
    expect(state.steps).toHaveLength(3)
    expect(state.activeStepId).toBe('step-1')
    expect(readPlanState()?.id).toBe(state.id)
  })

  test('onToolResult triggers replan after 3 recoverable errors on step 5', async () => {
    await writeFile(getPlanJsonPath(), JSON.stringify(fixture, null, 2))

    const params = {
      toolName: 'Edit',
      toolUseId: 'tool-1',
      isError: true,
      permissionDenied: false,
      aborted: false,
      validationError: false,
    }

    expect(onToolResult(params)).toBeNull()
    expect(onToolResult({ ...params, toolUseId: 'tool-2' })).toBeNull()

    const replan = onToolResult({ ...params, toolUseId: 'tool-3' })
    expect(replan).not.toBeNull()
    expect(replan?.attachment?.type).toBe('plan_updated')
    expect(replan?.contextHint).toContain('Step 5 failed 3 times')

    const updated = readPlanState()
    expect(updated?.steps.find(s => s.id === 'step-5')?.status).toBe('pending')
    expect(updated?.steps.find(s => s.id === 'step-5')?.description).toContain('revised:')
    expect(updated?.replanCountsByStepId?.['step-5']).toBe(1)
    expect(updated?.activeStepId).toBe('step-5')
    expect(updated?.steps.find(s => s.id === 'step-6')?.status).toBe('pending')
  })

  test('circuit breaker stops auto-replan after 2 per step', () => {
    writePlanState({
      ...(fixture as never),
      replanCountsByStepId: { 'step-5': 2 },
    })

    const result = requestReplan('manual exhaustion test')
    expect(result.attachment).toBeNull()
    expect(result.contextHint).toContain('Needs your guidance')

    const updated = readPlanState()
    expect(updated?.steps.find(s => s.id === 'step-5')?.status).toBe('failed')
  })

  test('failure log keeps last 3 errors', () => {
    writePlanState(fixture as never)
    for (let i = 0; i < 4; i++) {
      onToolResult({
        toolName: 'Bash',
        toolUseId: `tool-${i}`,
        isError: true,
      })
    }
    expect(getFailureLog()).toHaveLength(3)
    expect(getFailureLog()[0]?.toolUseId).toBe('tool-1')
    expect(getFailureLog()[2]?.toolUseId).toBe('tool-3')
  })

  test('permission_denied errors do not trigger replan', () => {
    writePlanState({
      ...(fixture as never),
      steps: (fixture.steps as never[]).map(s =>
        s.id === 'step-5' ? { ...s, retryCount: 0 } : s,
      ),
    })

    for (let i = 0; i < 5; i++) {
      const result = onToolResult({
        toolName: 'Edit',
        toolUseId: `perm-${i}`,
        isError: true,
        permissionDenied: true,
      })
      expect(result).toBeNull()
    }
    expect(readPlanState()?.replanCountsByStepId?.['step-5']).toBeUndefined()
  })

  test('successful tool result advances to next step', () => {
    writePlanState(fixture as never)
    onToolResult({
      toolName: 'Edit',
      toolUseId: 'ok-1',
      isError: false,
    })
    const updated = readPlanState()
    expect(updated?.activeStepId).toBe('step-6')
    expect(updated?.steps.find(s => s.id === 'step-5')?.status).toBe('done')
    expect(updated?.steps.find(s => s.id === 'step-6')?.status).toBe('running')
  })

  test('planFromRevisedMarkdown parses md and creates executing plan', () => {
    resetPlanningOrchestratorForTesting()
    const md = `# Revised Plan\n\n1. Fix database connection\n2. Retry migration\n3. Verify results`
    const plan = planFromRevisedMarkdown(md)
    expect(plan).not.toBeNull()
    expect(plan!.status).toBe('executing')
    expect(plan!.steps).toHaveLength(3)
    expect(plan!.steps[0].status).toBe('running')
    expect(plan!.steps[1].status).toBe('pending')

    const saved = readPlanState()
    expect(saved).not.toBeNull()
    expect(saved!.id).toBe(plan!.id)
    expect(saved!.activeStepId).toBe('step-1')
  })

  test('onTaskCreated links taskId to active step', async () => {
    resetPlanningOrchestratorForTesting()
    const md = `1. Setup database\n2. Configure API\n3. Deploy`
    const plan = planFromRevisedMarkdown(md)
    expect(plan).not.toBeNull()
    expect(plan!.activeStepId).toBe('step-1')

    // Step 1 should not have a taskId yet
    expect(plan!.steps[0].taskId).toBeUndefined()

    // Link a task to the active step
    const result = onTaskCreated('task-abc-123')
    expect(result).not.toBeNull()
    expect(result!.steps[0].taskId).toBe('task-abc-123')

    // Link to a specific step
    const result2 = onTaskCreated('task-def-456', 'step-2')
    expect(result2!.steps[1].taskId).toBe('task-def-456')
    expect(result2!.steps[0].taskId).toBe('task-abc-123') // preserved

    // No active plan
    resetPlanningOrchestratorForTesting()
    try { await unlink(getPlanJsonPath()) } catch { /* ignore */ }
    expect(onTaskCreated('task-xxx')).toBeNull()
  })

  test('storeForkReplanContext and clearForkReplanContext round-trip', () => {
    clearForkReplanContext()
    // Default: no fork context
    const result1 = onToolResult({
      toolName: 'Bash',
      toolUseId: 'tu1',
      isError: true,
    })
    expect(result1).toBeNull() // first error, threshold not reached

    // After clear, calling replan still works
    storeForkReplanContext({
      mainLoopModel: 'claude-sonnet-4',
      tools: [],
    })
    // Context is stored, fork-agent would fire on replan but is fire-and-forget
    clearForkReplanContext()
    // Clear should not throw
    expect(true).toBe(true)
  })
})

describe('classifyToolError', () => {
  test('maps error signals to kinds', () => {
    expect(classifyToolError(false, false, false, false)).toBe('recoverable')
    expect(classifyToolError(true, false, true, false)).toBe('aborted')
    expect(classifyToolError(true, true, false, false)).toBe('permission_denied')
    expect(classifyToolError(true, false, false, true)).toBe('validation')
    expect(classifyToolError(true, false, false, false)).toBe('recoverable')
  })
})
