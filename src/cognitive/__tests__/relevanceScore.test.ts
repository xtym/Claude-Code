import { describe, expect, test } from 'bun:test'
import { scoreRecoverySlice } from '../context/relevanceScore.js'

describe('scoreRecoverySlice', () => {
  test('keyword match increases score', () => {
    const high = scoreRecoverySlice({
      content: 'Use PostgreSQL for persistence layer',
      query: 'database postgres schema',
      turnIndex: 5,
      maxTurnIndex: 50,
      compactBoundaryTurn: 30,
    })
    const low = scoreRecoverySlice({
      content: 'Lint passed on utils folder',
      query: 'database postgres schema',
      turnIndex: 5,
      maxTurnIndex: 50,
      compactBoundaryTurn: 30,
    })
    expect(high).toBeGreaterThan(low)
  })

  test('pre-compact slice near boundary scores higher when query matches', () => {
    const preCompact = scoreRecoverySlice({
      content: 'Architecture: event-driven modules',
      query: 'architecture modules',
      turnIndex: 28,
      maxTurnIndex: 50,
      compactBoundaryTurn: 30,
    })
    expect(preCompact).toBeGreaterThan(0.3)
  })
})
