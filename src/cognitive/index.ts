export {
  startTranscriptRecoveryPrefetch,
  toAttachmentMessages,
} from './context/TranscriptRecoveryIndex.js'
export { snapshotPreCompactRegion } from './context/localIndex.js'
export {
  isCognitiveLayerEnabled,
  isCognitiveScopeAllowed,
  isMemorySurfaceEnabled,
  isPlanningEnabled,
  isTranscriptRecoveryEnabled,
} from './flags.js'
export { recall, surfaceOnSessionStart } from './memory/MemoryStore.js'
export { rankMemoryHeaders } from './memory/rankMemories.js'
export {
  getSessionPlan,
  isActive as isPlanningActive,
  onPlanApproved,
  requestReplan,
} from './planning/PlanningOrchestrator.js'
export { handlePlanningToolResult } from './planning/planningHook.js'
export type {
  MemoryEntry,
  MemoryScope,
  Plan,
  PlanFailureRecord,
  PlanState,
  RecoverySlice,
  ToolErrorKind,
} from './types.js'
