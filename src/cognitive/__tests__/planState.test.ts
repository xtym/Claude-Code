import { describe, expect, test, beforeEach, afterEach, mock } from 'bun:test'
import { mkdir, rm } from 'fs/promises'
import { join } from 'path'
import { tmpdir } from 'os'

let tempDir = ''
let planMdPath = ''

mock.module('../../utils/plans.js', () => ({
  getPlanFilePath: () => planMdPath,
}))

const {
  getPlanJsonPath,
  parseStepsFromPlanMd,
  readPlanState,
  writePlanState,
  createExecutingPlanState,
} = await import('../planning/planState.js')

beforeEach(async () => {
  tempDir = join(
    tmpdir(),
    `plan-state-test-${Date.now()}-${Math.random().toString(36).slice(2)}`,
  )
  await mkdir(tempDir, { recursive: true })
  planMdPath = join(tempDir, 'test-plan.md')
})

afterEach(async () => {
  await rm(tempDir, { recursive: true, force: true })
})

describe('planState', () => {
  test('getPlanJsonPath replaces .md with .plan.json', () => {
    expect(getPlanJsonPath()).toBe(join(tempDir, 'test-plan.plan.json'))
  })

  test('parseStepsFromPlanMd extracts numbered steps', () => {
    const md = `# Plan

1. First step here
2. Second step here
- not a step
3. Third step
`
    const steps = parseStepsFromPlanMd(md)
    expect(steps).toHaveLength(3)
    expect(steps[0]).toMatchObject({
      id: 'step-1',
      description: 'First step here',
      status: 'pending',
      retryCount: 0,
    })
    expect(steps[2]?.id).toBe('step-3')
  })

  test('writePlanState and readPlanState round-trip', () => {
    const state = createExecutingPlanState([
      { id: 'step-1', description: 'Do thing', status: 'pending', retryCount: 0 },
      { id: 'step-2', description: 'Verify', status: 'pending', retryCount: 0 },
    ])
    writePlanState(state)
    const loaded = readPlanState()
    expect(loaded).toEqual(state)
  })

  test('createExecutingPlanState sets first step running', () => {
    const state = createExecutingPlanState([
      { id: 'step-1', description: 'A', status: 'pending', retryCount: 0 },
      { id: 'step-2', description: 'B', status: 'pending', retryCount: 0 },
    ])
    expect(state.status).toBe('executing')
    expect(state.activeStepId).toBe('step-1')
    expect(state.steps[0]?.status).toBe('running')
    expect(state.steps[1]?.status).toBe('pending')
  })
})
