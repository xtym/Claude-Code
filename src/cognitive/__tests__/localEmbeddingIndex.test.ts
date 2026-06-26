import { describe, test, expect } from 'bun:test'
import {
  buildEmbeddingIndex,
  queryEmbeddingIndex,
  serializeIndex,
  deserializeIndex,
} from '../embedding/localEmbeddingIndex.js'

describe('Phase 3.1 localEmbeddingIndex', () => {
  test('buildIndex + query returns top-K results', () => {
    const docs = [
      { id: '1', text: 'User prefers Bun over npm for JavaScript package management' },
      { id: '2', text: 'React component system architecture with hooks' },
      { id: '3', text: 'PostgreSQL database connection configuration' },
    ]
    const index = buildEmbeddingIndex(docs)
    const results = queryEmbeddingIndex(index, 'Bun package manager', 2)
    expect(results.length).toBeGreaterThanOrEqual(1)
    // "bun" should be most relevant for the Bun query
    expect(results[0].id).toBe('1')
  })

  test('character n-grams enable keyword-independent recall', () => {
    const docs = [
      { id: 'bun', text: 'Fast JavaScript runtime and package manager' },
      { id: 'node', text: 'Server-side JavaScript runtime environment' },
    ]
    const index = buildEmbeddingIndex(docs)
    // "runtime" appears in both, "javascript" appears in both, but "package" is only in bun
    const results = queryEmbeddingIndex(index, 'package management', 2)
    expect(results.length).toBe(2)
    // bun should score higher because "package" n-grams overlap more
    expect(results[0].id).toBe('bun')
  })

  test('handles empty corpus gracefully', () => {
    const index = buildEmbeddingIndex([])
    const results = queryEmbeddingIndex(index, 'anything', 5)
    expect(results).toEqual([])
  })

  test('serialize/deserialize round-trip preserves vectors', () => {
    const docs = [
      { id: 'iris', text: 'Quantum entanglement is a physical phenomenon' },
      { id: 'python', text: 'Python is a popular programming language for data science' },
    ]
    const index = buildEmbeddingIndex(docs)
    const json = serializeIndex(index)
    const restored = deserializeIndex(json)
    expect(restored).toHaveLength(2)
    expect(restored[0].id).toBe('iris')
    expect(restored[0].magnitude).toBeGreaterThan(0)
    expect(Object.keys(restored[0].vector).length).toBeGreaterThan(0)
    // Round-trip should preserve similarity ranking
    const q1 = queryEmbeddingIndex(index, 'quantum physics', 2)
    const q2 = queryEmbeddingIndex(restored, 'quantum physics', 2)
    expect(q1[0].id).toBe(q2[0].id)
  })

  test('prefers semantically similar documents', () => {
    const docs = [
      { id: 'database', text: 'database index query performance optimization postgresql' },
      { id: 'frontend', text: 'button style color layout responsive css react' },
      { id: 'api', text: 'api restful endpoint request response routing graphql' },
    ]
    const index = buildEmbeddingIndex(docs)
    const results = queryEmbeddingIndex(index, 'database query optimization', 3)
    expect(results[0].id).toBe('database')
    // Round-trip preserves ordering
    const json = serializeIndex(index)
    const restored = deserializeIndex(json)
    const restoredResults = queryEmbeddingIndex(restored, 'database query optimization', 3)
    expect(restoredResults[0].id).toBe(results[0].id)
  })
})
