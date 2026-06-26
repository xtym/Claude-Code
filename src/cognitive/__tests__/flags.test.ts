import { describe, expect, test, beforeEach, afterEach } from 'bun:test'
import {
  isCognitiveLayerEnabled,
  isTranscriptRecoveryEnabled,
  isMemorySurfaceEnabled,
  isMemoryWriteEnabled,
  isPlanningEnabled,
  isCognitiveScopeAllowed,
} from '../flags.js'

const env = process.env

beforeEach(() => {
  process.env = { ...env }
})

afterEach(() => {
  process.env = env
})

describe('cognitive flags', () => {
  test('master flag off disables all', () => {
    process.env.CLAUDE_CODE_COGNITIVE_LAYER = '0'
    process.env.CLAUDE_CODE_COGNITIVE_CONTEXT = '1'
    process.env.CLAUDE_CODE_COGNITIVE_PLANNING = '1'
    expect(isCognitiveLayerEnabled()).toBe(false)
    expect(isTranscriptRecoveryEnabled()).toBe(false)
    expect(isMemorySurfaceEnabled()).toBe(false)
    expect(isMemoryWriteEnabled()).toBe(false)
    expect(isPlanningEnabled()).toBe(false)
  })

  test('context flag requires master', () => {
    process.env.CLAUDE_CODE_COGNITIVE_LAYER = '1'
    process.env.CLAUDE_CODE_COGNITIVE_CONTEXT = '1'
    expect(isTranscriptRecoveryEnabled()).toBe(true)
  })

  test('memory surface flag requires master', () => {
    process.env.CLAUDE_CODE_COGNITIVE_LAYER = '1'
    process.env.CLAUDE_CODE_COGNITIVE_MEMORY_SURFACE = '1'
    expect(isMemorySurfaceEnabled()).toBe(true)
    process.env.CLAUDE_CODE_COGNITIVE_LAYER = '0'
    expect(isMemorySurfaceEnabled()).toBe(false)
  })

  test('planning flag requires master', () => {
    process.env.CLAUDE_CODE_COGNITIVE_LAYER = '1'
    process.env.CLAUDE_CODE_COGNITIVE_PLANNING = '1'
    expect(isPlanningEnabled()).toBe(true)
    process.env.CLAUDE_CODE_COGNITIVE_LAYER = '0'
    expect(isPlanningEnabled()).toBe(false)
    process.env.CLAUDE_CODE_COGNITIVE_LAYER = '1'
    process.env.CLAUDE_CODE_COGNITIVE_PLANNING = '0'
    expect(isPlanningEnabled()).toBe(false)
  })

  test('memory write flag requires master', () => {
    process.env.CLAUDE_CODE_COGNITIVE_LAYER = '1'
    process.env.CLAUDE_CODE_COGNITIVE_MEMORY_WRITE = '1'
    expect(isMemoryWriteEnabled()).toBe(true)
    process.env.CLAUDE_CODE_COGNITIVE_LAYER = '0'
    expect(isMemoryWriteEnabled()).toBe(false)
    process.env.CLAUDE_CODE_COGNITIVE_LAYER = '1'
    process.env.CLAUDE_CODE_COGNITIVE_MEMORY_WRITE = '0'
    expect(isMemoryWriteEnabled()).toBe(false)
  })

  test('scope gate rejects subagents', () => {
    expect(
      isCognitiveScopeAllowed({
        querySource: 'repl_main_thread',
        agentId: undefined,
      }),
    ).toBe(true)
    expect(
      isCognitiveScopeAllowed({
        querySource: 'repl_main_thread',
        agentId: 'agent-123',
      }),
    ).toBe(false)
    expect(
      isCognitiveScopeAllowed({
        querySource: 'agent:foo',
        agentId: undefined,
      }),
    ).toBe(false)
  })
})
