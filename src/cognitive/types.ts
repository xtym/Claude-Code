import type { UUID } from 'crypto'
import type { QuerySource } from '../constants/querySource.js'

export type RecoverySliceSource =
  | 'transcript'
  | 'tool_result'
  | 'plan_snippet'
  | 'compact_summary'

export type RecoverySlice = {
  source: RecoverySliceSource
  content: string
  relevanceScore: number
  tokenEstimate: number
  compactBoundaryId?: string
  sliceId: string
}

export type RecoveryPrefetch = {
  promise: Promise<RecoverySlice[]>
  settledAt: number | null
  consumedOnIteration: number
  [Symbol.dispose](): void
}

export type CognitiveScopeParams = {
  querySource: QuerySource
  agentId?: UUID
}

export type MemoryScope = 'session' | 'project' | 'user'

export type MemoryEntry = {
  id: string
  scope: MemoryScope
  tags: string[]
  content: string
  createdAt: number
  path?: string
}

export type PlanStepStatus =
  | 'pending'
  | 'running'
  | 'done'
  | 'failed'
  | 'skipped'

export type PlanStep = {
  id: string
  description: string
  dependsOn?: string[]
  status: PlanStepStatus
  retryCount: number
  taskId?: string
  expectedTools?: string[]
}

export type PlanStatus =
  | 'draft'
  | 'approved'
  | 'executing'
  | 'failed'
  | 'done'

export type PlanState = {
  id: string
  steps: PlanStep[]
  status: PlanStatus
  activeStepId?: string
  replanCountsByStepId?: Record<string, number>
}

/** Alias for spec compatibility */
export type Plan = PlanState

export type ToolErrorKind =
  | 'recoverable'
  | 'permission_denied'
  | 'aborted'
  | 'validation'

export type PlanFailureRecord = {
  stepId: string
  toolName: string
  toolUseId: string
  errorKind: ToolErrorKind
  timestamp: number
}
