export {
  buildEmbeddingIndex,
  queryEmbeddingIndex,
  serializeIndex,
  deserializeIndex,
} from './embedding/localEmbeddingIndex.js'
export { rerankSlicesWithEmbedding, rankMemoriesWithEmbedding, clearEmbeddingCache } from './embedding/embeddingRanker.js'
export { isEmbeddingEnabled } from './flags.js'
export {
  startTranscriptRecoveryPrefetch,
  toAttachmentMessages,
} from './context/TranscriptRecoveryIndex.js'
export { snapshotPreCompactRegion } from './context/localIndex.js'
export { persistSlices, loadPersistedSlices } from './context/recoveryIndexPersistence.js'
export {
  isCognitiveLayerEnabled,
  isCognitiveScopeAllowed,
  isMemorySurfaceEnabled,
  isMemoryWriteEnabled,
  isPlanningEnabled,
  isTranscriptRecoveryEnabled,
} from './flags.js'
export { recall, surfaceOnSessionStart, write } from './memory/MemoryStore.js'
export { rankMemoryHeaders } from './memory/rankMemories.js'
export { findExistingMemoryByTags, mergeMemoryContent } from './memory/deduplicate.js'
export {
  getSessionPlan,
  isActive as isPlanningActive,
  onPlanApproved,
  onTaskCreated,
  planFromRevisedMarkdown,
  requestReplan,
  storeForkReplanContext,
  clearForkReplanContext,
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
