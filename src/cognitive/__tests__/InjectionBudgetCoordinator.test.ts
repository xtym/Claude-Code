import { describe, expect, test } from 'bun:test'
import type { RecoverySlice } from '../types.js'
import {
  MAX_COGNITIVE_INJECTION_BYTES,
  allocateRecoverySlices,
  estimateSliceBytes,
  getMaxInjectionBytesForTurn,
} from '../InjectionBudgetCoordinator.js'

function slice(content: string, score: number): RecoverySlice {
  return {
    sliceId: content,
    source: 'transcript',
    content,
    relevanceScore: score,
    tokenEstimate: Math.ceil(content.length / 4),
  }
}

describe('InjectionBudgetCoordinator', () => {
  test('estimateSliceBytes uses UTF-8 byte length', () => {
    expect(estimateSliceBytes(slice('hello', 1))).toBe(5)
  })

  test('allocate respects max bytes and score order', () => {
    const slices = [
      slice('aaa', 0.1),
      slice('bbbbbbbb', 0.9),
      slice('cc', 0.5),
    ]
    const result = allocateRecoverySlices(slices, {
      maxBytes: 9,
      memoryBytesAlreadyUsed: 0,
    })
    expect(result.map(s => s.content)).toEqual(['bbbbbbbb'])
  })

  test('allocate subtracts memory bytes already used', () => {
    const slices = [slice('12345', 1)]
    const result = allocateRecoverySlices(slices, {
      maxBytes: MAX_COGNITIVE_INJECTION_BYTES,
      memoryBytesAlreadyUsed: MAX_COGNITIVE_INJECTION_BYTES,
    })
    expect(result).toEqual([])
  })

  test('getMaxInjectionBytesForTurn caps at 30k for default provider', () => {
    const bytes = getMaxInjectionBytesForTurn(0)
    expect(bytes).toBe(30_000)
  })

  test('getMaxInjectionBytesForTurn subtracts already-used memory', () => {
    const bytes = getMaxInjectionBytesForTurn(10_000)
    expect(bytes).toBe(20_000)
  })
})
