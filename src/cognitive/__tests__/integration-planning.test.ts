import { describe, expect, test, beforeEach, afterEach, mock } from 'bun:test'
import { mkdir, rm, writeFile } from 'fs/promises'
import { join } from 'path'
import { tmpdir } from 'os'
import fixture from './fixtures/plan-executing-step5-fail.json'
import { handlePlanningToolResult } from '../planning/planningHook.js'
import { resetPlanningOrchestratorForTesting } from '../planning/PlanningOrchestrator.js'
import { getPlanJsonPath, readPlanState } from '../planning/planState.js'

let tempDir = ''
let planMdPath = ''

mock.module('../../utils/plans.js', () => ({
  getPlanFilePath: () => planMdPath,
}))

const env = process.env

function makeToolContext() {
  return {
    agentId: undefined,
    options: { querySource: 'repl_main_thread' },
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
    `integration-planning-${Date.now()}-${Math.random().toString(36).slice(2)}`,
  )
  await mkdir(tempDir, { recursive: true })
  planMdPath = join(tempDir, 'test-plan.md')
  await writeFile(getPlanJsonPath(), JSON.stringify(fixture, null, 2))
})

afterEach(async () => {
  process.env = env
  await rm(tempDir, { recursive: true, force: true })
})

describe('T2 plan step 5 triple failure', () => {
  test('handlePlanningToolResult emits plan_updated after 3 recoverable errors', () => {
    const ctx = makeToolContext()
    const params = {
      toolName: 'Edit',
      toolUseId: 'tool-1',
      isError: true,
      errorKind: 'recoverable' as const,
      toolUseContext: ctx,
      querySource: 'repl_main_thread' as const,
    }

    expect(handlePlanningToolResult(params)).toEqual([])
    expect(handlePlanningToolResult({ ...params, toolUseId: 'tool-2' })).toEqual([])

    const messages = handlePlanningToolResult({ ...params, toolUseId: 'tool-3' })
    expect(messages).toHaveLength(2)
    expect(messages[0]?.type).toBe('attachment')
    expect(messages[0]?.attachment.type).toBe('plan_updated')
    expect(messages[1]?.type).toBe('user')
    expect(messages[1]?.message.content).toContain('Step 5 failed 3 times')

    const updated = readPlanState()
    expect(updated?.steps.find(s => s.id === 'step-5')?.status).toBe('pending')
    expect(updated?.steps.find(s => s.id === 'step-5')?.description).toContain('revised:')
    expect(updated?.replanCountsByStepId?.['step-5']).toBe(1)
    expect(updated?.activeStepId).toBe('step-5')
    expect(updated?.steps.find(s => s.id === 'step-6')?.status).toBe('pending')
  })
})
