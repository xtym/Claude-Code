import { writeFileSync } from 'fs'
import { randomUUID } from 'crypto'
import type { AgentId } from '../../types/ids.js'
import { getFsImplementation } from '../../utils/fsOperations.js'
import { logError } from '../../utils/log.js'
import { getPlanFilePath } from '../../utils/plans.js'
import type { PlanState, PlanStep } from '../types.js'

export function getPlanStatePath(agentId?: AgentId): string {
  return getPlanFilePath(agentId).replace(/\.md$/, '.plan.json')
}

export function getPlanJsonPath(agentId?: AgentId): string {
  return getPlanStatePath(agentId)
}

export function parseStepsFromPlanMd(planMd: string): PlanStep[] {
  const steps: PlanStep[] = []
  for (const line of planMd.split('\n')) {
    const numbered = line.match(/^\s*(\d+)\.\s+(.+)$/)
    if (numbered) {
      steps.push({
        id: `step-${numbered[1]}`,
        description: numbered[2]!.trim(),
        status: 'pending',
        retryCount: 0,
      })
      continue
    }
    const checklist = line.match(/^\s*[-*]\s+\[[ xX]\]\s+(.+)$/)
    if (checklist) {
      steps.push({
        id: `step-${steps.length + 1}`,
        description: checklist[1]!.trim(),
        status: 'pending',
        retryCount: 0,
      })
    }
  }
  return steps
}

export function firstRunnableStepId(plan: PlanState): string | undefined {
  for (const step of plan.steps) {
    if (step.status === 'done' || step.status === 'skipped') continue
    const deps = step.dependsOn ?? []
    const depsMet = deps.every(depId =>
      plan.steps.some(s => s.id === depId && s.status === 'done'),
    )
    if (depsMet) return step.id
  }
  return undefined
}

export function readPlanState(agentId?: AgentId): PlanState | null {
  const path = getPlanStatePath(agentId)
  try {
    if (!getFsImplementation().existsSync(path)) return null
    const raw = getFsImplementation().readFileSync(path, { encoding: 'utf-8' })
    return JSON.parse(raw) as PlanState
  } catch (error) {
    logError(error)
    return null
  }
}

export function writePlanState(plan: PlanState, agentId?: AgentId): void {
  const path = getPlanStatePath(agentId)
  try {
    writeFileSync(path, `${JSON.stringify(plan, null, 2)}\n`, 'utf8')
  } catch (error) {
    logError(error)
  }
}

export function createExecutingPlanState(steps: PlanStep[]): PlanState {
  const activeStepId = firstRunnableStepId({
    id: '',
    steps,
    status: 'executing',
  })
  const runningSteps = steps.map(step => ({
    ...step,
    status:
      step.id === activeStepId ? ('running' as const) : ('pending' as const),
  }))
  return {
    id: randomUUID(),
    steps: runningSteps,
    status: 'executing',
    activeStepId,
    replanCountsByStepId: {},
  }
}

export function planFromApprovedMarkdown(planMd: string, planId: string): PlanState {
  const steps = parseStepsFromPlanMd(planMd)
  const activeStepId = firstRunnableStepId({ id: planId, steps, status: 'executing' })
  const runningSteps = steps.map(step => ({
    ...step,
    status:
      step.id === activeStepId ? ('running' as const) : ('pending' as const),
  }))
  return {
    id: planId,
    steps: runningSteps,
    status: 'executing',
    activeStepId,
    replanCountsByStepId: {},
  }
}
