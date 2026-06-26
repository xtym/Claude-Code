import type { RecoverySlice } from './types.js'
import { getProviderCapabilities } from './ProviderCapabilities.js'

/**
 * Max recovery injection bytes per session (Anthropic baseline).
 * Value matches RELEVANT_MEMORIES_CONFIG.MAX_SESSION_BYTES (60KB) / 2.
 * Hardcoded to avoid circular-init TDZ: importing from attachments.ts
 * creates a circular dependency through the cognitive module chain.
 * @deprecated Use getMaxCognitiveInjectionBytes() for provider-aware budget.
 */
export const MAX_COGNITIVE_INJECTION_BYTES = 30_000

function getMaxCognitiveInjectionBytes(): number {
  const caps = getProviderCapabilities()
  // Anthropic: 30KB budget; proxy: smaller budget due to no prompt cache
  return caps.supportsPromptCache ? 30_000 : 15_000
}

export function estimateSliceBytes(slice: RecoverySlice): number {
  return Buffer.byteLength(slice.content, 'utf8')
}

export function getMaxInjectionBytesForTurn(
  memoryBytesAlreadyUsed = 0,
): number {
  const maxBytes = getMaxCognitiveInjectionBytes()
  return Math.max(0, maxBytes - memoryBytesAlreadyUsed)
}

export function allocateRecoverySlices(
  slices: RecoverySlice[],
  opts: { maxBytes: number; memoryBytesAlreadyUsed: number },
): RecoverySlice[] {
  const budget = getMaxInjectionBytesForTurn(opts.memoryBytesAlreadyUsed)
  const effectiveMax = Math.min(budget, opts.maxBytes)
  if (effectiveMax <= 0) return []

  const sorted = [...slices].sort(
    (a, b) => b.relevanceScore - a.relevanceScore,
  )
  const selected: RecoverySlice[] = []
  let used = 0
  for (const s of sorted) {
    const bytes = estimateSliceBytes(s)
    if (used + bytes > effectiveMax) continue
    selected.push(s)
    used += bytes
  }
  return selected
}
