import type { QuerySource } from '../constants/querySource.js'
import { isEnvTruthy } from '../utils/envUtils.js'
import type { CognitiveScopeParams } from './types.js'

export function isCognitiveLayerEnabled(): boolean {
  return isEnvTruthy(process.env.CLAUDE_CODE_COGNITIVE_LAYER)
}

export function isTranscriptRecoveryEnabled(): boolean {
  return isCognitiveLayerEnabled() && isEnvTruthy(process.env.CLAUDE_CODE_COGNITIVE_CONTEXT)
}

export function isMemorySurfaceEnabled(): boolean {
  return (
    isCognitiveLayerEnabled() &&
    isEnvTruthy(process.env.CLAUDE_CODE_COGNITIVE_MEMORY_SURFACE)
  )
}

export function isMemoryWriteEnabled(): boolean {
  return isCognitiveLayerEnabled() && isEnvTruthy(process.env.CLAUDE_CODE_COGNITIVE_MEMORY_WRITE)
}

export function isEmbeddingEnabled(): boolean {
  return isCognitiveLayerEnabled() && isEnvTruthy(process.env.CLAUDE_CODE_COGNITIVE_EMBEDDING)
}

export function isPlanningEnabled(): boolean {
  return (
    isCognitiveLayerEnabled() &&
    isEnvTruthy(process.env.CLAUDE_CODE_COGNITIVE_PLANNING)
  )
}

const MAIN_THREAD_SOURCES: ReadonlySet<string> = new Set(['repl_main_thread'])

export function isCognitiveScopeAllowed(params: CognitiveScopeParams): boolean {
  if (params.agentId !== undefined) return false
  return MAIN_THREAD_SOURCES.has(params.querySource)
}