# Phase 1: Transcript Recovery Index Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Inject pre-compact transcript decisions back into the query loop after autocompact, without duplicating existing memory-file prefetch, using a shared injection budget.

**Architecture:** New `src/cognitive/` module with `TranscriptRecoveryIndex` (local JSON index + keyword/recency scoring), `InjectionBudgetCoordinator` (shared byte ceiling with `RELEVANT_MEMORIES_CONFIG`), and `ProviderCapabilities` stub. Hooks into `query.ts` via the same prefetch/consume pattern as `startRelevantMemoryPrefetch`. Main-thread only via scope gate.

**Tech Stack:** TypeScript (ESM), Bun test runner (`bun:test`), existing `Message` / `AttachmentMessage` types, `isEnvTruthy` for feature flags.

**Spec reference:** `docs/superpowers/specs/2026-06-25-agent-cognitive-layer-design.md` (Revision 2) — Phase 1 only.

---

## File Map

| File | Responsibility |
|------|----------------|
| `src/cognitive/types.ts` | Shared interfaces: `RecoverySlice`, `RecoveryPrefetch`, `ToolErrorKind` (future) |
| `src/cognitive/flags.ts` | Env flag helpers: `isCognitiveLayerEnabled`, `isTranscriptRecoveryEnabled`, scope gate |
| `src/cognitive/ProviderCapabilities.ts` | Anthropic vs proxy capability matrix |
| `src/cognitive/InjectionBudgetCoordinator.ts` | Shared byte budget with memory prefetch |
| `src/cognitive/context/relevanceScore.ts` | Score slices by keyword + recency + compact proximity |
| `src/cognitive/context/localIndex.ts` | Build/persist/load recovery index from messages |
| `src/cognitive/context/TranscriptRecoveryIndex.ts` | Prefetch/consume/toAttachments public API |
| `src/cognitive/index.ts` | Re-exports for `query.ts` import |
| `src/cognitive/__tests__/*.test.ts` | Unit tests |
| `src/cognitive/__tests__/fixtures/compact-boundary-transcript.json` | T1a fixture |
| `src/query.ts` | Prefetch init, consume block, compact-boundary hook (~40 lines) |
| `src/utils/attachments.ts` | Add `recovered_context` attachment type (minimal union extension) |

---

## Task 1: Feature Flags and Types

**Files:**
- Create: `src/cognitive/types.ts`
- Create: `src/cognitive/flags.ts`
- Test: `src/cognitive/__tests__/flags.test.ts`

- [ ] **Step 1: Write the failing test**

Create `src/cognitive/__tests__/flags.test.ts`:

```typescript
import { describe, expect, test, beforeEach, afterEach } from 'bun:test'
import {
  isCognitiveLayerEnabled,
  isTranscriptRecoveryEnabled,
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
    expect(isCognitiveLayerEnabled()).toBe(false)
    expect(isTranscriptRecoveryEnabled()).toBe(false)
  })

  test('context flag requires master', () => {
    process.env.CLAUDE_CODE_COGNITIVE_LAYER = '1'
    process.env.CLAUDE_CODE_COGNITIVE_CONTEXT = '1'
    expect(isTranscriptRecoveryEnabled()).toBe(true)
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bun test src/cognitive/__tests__/flags.test.ts`

Expected: FAIL — cannot find module `../flags.js`

- [ ] **Step 3: Write minimal implementation**

Create `src/cognitive/types.ts`:

```typescript
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
```

Create `src/cognitive/flags.ts`:

```typescript
import type { QuerySource } from '../constants/querySource.js'
import { isEnvTruthy } from '../utils/envUtils.js'
import type { CognitiveScopeParams } from './types.js'

export function isCognitiveLayerEnabled(): boolean {
  return isEnvTruthy(process.env.CLAUDE_CODE_COGNITIVE_LAYER)
}

export function isTranscriptRecoveryEnabled(): boolean {
  return isCognitiveLayerEnabled() && isEnvTruthy(process.env.CLAUDE_CODE_COGNITIVE_CONTEXT)
}

const MAIN_THREAD_SOURCES: ReadonlySet<string> = new Set(['repl_main_thread'])

export function isCognitiveScopeAllowed(params: CognitiveScopeParams): boolean {
  if (params.agentId !== undefined) return false
  return MAIN_THREAD_SOURCES.has(params.querySource)
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bun test src/cognitive/__tests__/flags.test.ts`

Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/cognitive/types.ts src/cognitive/flags.ts src/cognitive/__tests__/flags.test.ts
git commit -m "feat(cognitive): add feature flags and core types for Phase 1"
```

---

## Task 2: ProviderCapabilities Stub

**Files:**
- Create: `src/cognitive/ProviderCapabilities.ts`
- Test: `src/cognitive/__tests__/ProviderCapabilities.test.ts`

- [ ] **Step 1: Write the failing test**

Create `src/cognitive/__tests__/ProviderCapabilities.test.ts`:

```typescript
import { describe, expect, test, beforeEach, afterEach } from 'bun:test'
import { getProviderCapabilities } from '../ProviderCapabilities.js'

const env = process.env

beforeEach(() => { process.env = { ...env } })
afterEach(() => { process.env = env })

describe('ProviderCapabilities', () => {
  test('anthropic path enables cache and thinking', () => {
    delete process.env.CLAUDE_CODE_CUSTOM_PROXY
    delete process.env.ANTHROPIC_BASE_URL
    const caps = getProviderCapabilities()
    expect(caps.supportsPromptCache).toBe(true)
    expect(caps.supportsThinking).toBe(true)
  })

  test('custom proxy disables cache and thinking', () => {
    process.env.CLAUDE_CODE_CUSTOM_PROXY = '1'
    const caps = getProviderCapabilities()
    expect(caps.supportsPromptCache).toBe(false)
    expect(caps.supportsThinking).toBe(false)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bun test src/cognitive/__tests__/ProviderCapabilities.test.ts`

Expected: FAIL — module not found

- [ ] **Step 3: Write minimal implementation**

Create `src/cognitive/ProviderCapabilities.ts`:

```typescript
import { isCustomApiProxyMode } from '../utils/customProxy.js'
import { getContextWindowForModel } from '../utils/context.js'
import { getDefaultSonnetModel } from '../utils/model/model.js'

export type ProviderCapabilities = {
  supportsPromptCache: boolean
  supportsThinking: boolean
  supportsEffort: boolean
  maxContextWindow: number
  preferredSummarizerModel: string
}

export function getProviderCapabilities(model?: string): ProviderCapabilities {
  const isProxy = isCustomApiProxyMode()
  const resolvedModel = model ?? getDefaultSonnetModel()
  return {
    supportsPromptCache: !isProxy,
    supportsThinking: !isProxy,
    supportsEffort: !isProxy,
    maxContextWindow: getContextWindowForModel(resolvedModel),
    preferredSummarizerModel: resolvedModel,
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bun test src/cognitive/__tests__/ProviderCapabilities.test.ts`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/cognitive/ProviderCapabilities.ts src/cognitive/__tests__/ProviderCapabilities.test.ts
git commit -m "feat(cognitive): add ProviderCapabilities stub"
```

---

## Task 3: InjectionBudgetCoordinator

**Files:**
- Create: `src/cognitive/InjectionBudgetCoordinator.ts`
- Test: `src/cognitive/__tests__/InjectionBudgetCoordinator.test.ts`

- [ ] **Step 1: Write the failing test**

Create `src/cognitive/__tests__/InjectionBudgetCoordinator.test.ts`:

```typescript
import { describe, expect, test } from 'bun:test'
import type { RecoverySlice } from '../types.js'
import {
  MAX_COGNITIVE_INJECTION_BYTES,
  allocateRecoverySlices,
  estimateSliceBytes,
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
      maxBytes: 10,
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
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bun test src/cognitive/__tests__/InjectionBudgetCoordinator.test.ts`

Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

Create `src/cognitive/InjectionBudgetCoordinator.ts`:

```typescript
import type { RecoverySlice } from './types.js'
import { RELEVANT_MEMORIES_CONFIG } from '../utils/attachments.js'
import { getProviderCapabilities } from './ProviderCapabilities.js'

/** Half of session memory budget when memory prefetch may also inject */
export const MAX_COGNITIVE_INJECTION_BYTES = Math.floor(
  RELEVANT_MEMORIES_CONFIG.MAX_SESSION_BYTES / 2,
)

export function estimateSliceBytes(slice: RecoverySlice): number {
  return Buffer.byteLength(slice.content, 'utf8')
}

export function getMaxInjectionBytesForTurn(
  memoryBytesAlreadyUsed: number,
): number {
  const caps = getProviderCapabilities()
  const tokenBudgetBytes = Math.floor(caps.maxContextWindow * 0.05 * 4)
  const sharedCeiling = Math.min(
    MAX_COGNITIVE_INJECTION_BYTES,
    tokenBudgetBytes,
  )
  return Math.max(0, sharedCeiling - memoryBytesAlreadyUsed)
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bun test src/cognitive/__tests__/InjectionBudgetCoordinator.test.ts`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/cognitive/InjectionBudgetCoordinator.ts src/cognitive/__tests__/InjectionBudgetCoordinator.test.ts
git commit -m "feat(cognitive): add InjectionBudgetCoordinator with shared byte ceiling"
```

---

## Task 4: Relevance Scoring

**Files:**
- Create: `src/cognitive/context/relevanceScore.ts`
- Test: `src/cognitive/__tests__/relevanceScore.test.ts`

- [ ] **Step 1: Write the failing test**

Create `src/cognitive/__tests__/relevanceScore.test.ts`:

```typescript
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `bun test src/cognitive/__tests__/relevanceScore.test.ts`

Expected: FAIL

- [ ] **Step 3: Write minimal implementation**

Create `src/cognitive/context/relevanceScore.ts`:

```typescript
export type ScoreParams = {
  content: string
  query: string
  turnIndex: number
  maxTurnIndex: number
  compactBoundaryTurn?: number
}

function tokenize(text: string): string[] {
  return text
    .toLowerCase()
    .split(/[^a-z0-9_]+/i)
    .filter(t => t.length >= 3)
}

export function scoreRecoverySlice(params: ScoreParams): number {
  const queryTokens = new Set(tokenize(params.query))
  const contentTokens = tokenize(params.content)
  if (queryTokens.size === 0 || contentTokens.length === 0) return 0

  let matches = 0
  for (const t of contentTokens) {
    if (queryTokens.has(t)) matches++
  }
  const keywordScore = matches / queryTokens.size

  const recencyScore =
    params.maxTurnIndex > 0 ? params.turnIndex / params.maxTurnIndex : 0

  let boundaryBoost = 0
  if (
    params.compactBoundaryTurn !== undefined &&
    params.turnIndex < params.compactBoundaryTurn
  ) {
    const distance = params.compactBoundaryTurn - params.turnIndex
    boundaryBoost = Math.max(0, 1 - distance / 20) * 0.3
  }

  return Math.min(1, keywordScore * 0.6 + recencyScore * 0.1 + boundaryBoost)
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `bun test src/cognitive/__tests__/relevanceScore.test.ts`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/cognitive/context/relevanceScore.ts src/cognitive/__tests__/relevanceScore.test.ts
git commit -m "feat(cognitive): add keyword/recency/boundary relevance scoring"
```

---

## Task 5: Local Index Builder

**Files:**
- Create: `src/cognitive/context/localIndex.ts`
- Test: `src/cognitive/__tests__/localIndex.test.ts`
- Create: `src/cognitive/__tests__/fixtures/compact-boundary-transcript.json`

- [ ] **Step 1: Create fixture**

Create `src/cognitive/__tests__/fixtures/compact-boundary-transcript.json`:

```json
{
  "messages": [
    { "type": "user", "uuid": "u1", "content": "Let's use PostgreSQL for the persistence layer." },
    { "type": "assistant", "uuid": "a1", "content": "Agreed. I'll design around PostgreSQL." },
    { "type": "user", "uuid": "u2", "content": "Also add Redis for caching." },
    { "type": "system", "subtype": "compact_boundary", "uuid": "b1", "compactMetadata": { "trigger": "auto" } },
    { "type": "user", "uuid": "u3", "content": "Continue with the database schema." }
  ],
  "query": "database postgres schema",
  "expectedSnippet": "PostgreSQL"
}
```

- [ ] **Step 2: Write the failing test**

Create `src/cognitive/__tests__/localIndex.test.ts`:

```typescript
import { describe, expect, test } from 'bun:test'
import { readFileSync } from 'fs'
import { join } from 'path'
import { buildRecoverySlicesFromMessages } from '../context/localIndex.js'

const fixture = JSON.parse(
  readFileSync(
    join(import.meta.dir, 'fixtures/compact-boundary-transcript.json'),
    'utf8',
  ),
)

describe('localIndex', () => {
  test('extracts pre-compact user decision slices', () => {
    const slices = buildRecoverySlicesFromMessages(
      fixture.messages,
      fixture.query,
    )
    const combined = slices.map(s => s.content).join('\n')
    expect(combined).toContain(fixture.expectedSnippet)
    expect(slices.every(s => s.source === 'transcript' || s.source === 'compact_summary')).toBe(true)
  })

  test('does not index memory paths', () => {
    const slices = buildRecoverySlicesFromMessages(
      [
        {
          type: 'attachment',
          attachment: { type: 'relevant_memories', memories: [{ path: '/mem/x.md', content: 'secret' }] },
        },
      ],
      'secret',
    )
    expect(slices).toEqual([])
  })
})
```

- [ ] **Step 3: Run test to verify it fails**

Run: `bun test src/cognitive/__tests__/localIndex.test.ts`

Expected: FAIL

- [ ] **Step 4: Write minimal implementation**

Create `src/cognitive/context/localIndex.ts`:

```typescript
import { randomUUID } from 'crypto'
import type { Message } from '../../types/message.js'
import { isCompactBoundaryMessage } from '../../utils/messages.js'
import type { RecoverySlice } from '../types.js'
import { scoreRecoverySlice } from './relevanceScore.js'

function getMessageText(message: Message): string | null {
  if (message.type === 'user' || message.type === 'assistant') {
    if (typeof message.content === 'string') return message.content
    if (Array.isArray(message.content)) {
      return message.content
        .filter((b): b is { type: 'text'; text: string } => b.type === 'text')
        .map(b => b.text)
        .join('\n')
    }
  }
  return null
}

export function buildRecoverySlicesFromMessages(
  messages: readonly Message[],
  query: string,
): RecoverySlice[] {
  const boundaryIndex = messages.findLastIndex(m => isCompactBoundaryMessage(m))
  const endIndex = boundaryIndex === -1 ? messages.length : boundaryIndex
  const slices: RecoverySlice[] = []

  for (let i = 0; i < endIndex; i++) {
    const m = messages[i]
    if (!m) continue
    if (m.type === 'attachment') {
      // Skip memory-file attachments — owned by startRelevantMemoryPrefetch
      if (m.attachment.type === 'relevant_memories') continue
    }
    const text = getMessageText(m)
    if (!text || text.trim().length < 20) continue

    const score = scoreRecoverySlice({
      content: text,
      query,
      turnIndex: i,
      maxTurnIndex: messages.length,
      compactBoundaryTurn: boundaryIndex === -1 ? undefined : boundaryIndex,
    })
    if (score <= 0) continue

    slices.push({
      sliceId: randomUUID(),
      source: m.type === 'user' ? 'transcript' : 'transcript',
      content: text.slice(0, 2000),
      relevanceScore: score,
      tokenEstimate: Math.ceil(text.length / 4),
      compactBoundaryId:
        boundaryIndex === -1 ? undefined : String(boundaryIndex),
    })
  }

  return slices
}

export function snapshotPreCompactRegion(
  messages: readonly Message[],
  boundaryId: string,
): RecoverySlice[] {
  const summaryText = messages
    .map(getMessageText)
    .filter((t): t is string => !!t)
    .join('\n')
    .slice(0, 4000)

  if (!summaryText) return []

  return [
    {
      sliceId: randomUUID(),
      source: 'compact_summary',
      content: summaryText,
      relevanceScore: 1,
      tokenEstimate: Math.ceil(summaryText.length / 4),
      compactBoundaryId: boundaryId,
    },
  ]
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `bun test src/cognitive/__tests__/localIndex.test.ts`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/cognitive/context/localIndex.ts src/cognitive/__tests__/localIndex.test.ts src/cognitive/__tests__/fixtures/compact-boundary-transcript.json
git commit -m "feat(cognitive): build recovery slices from transcript messages"
```

---

## Task 6: TranscriptRecoveryIndex (prefetch / consume / attachments)

**Files:**
- Create: `src/cognitive/context/TranscriptRecoveryIndex.ts`
- Modify: `src/utils/attachments.ts` — extend `Attachment` union
- Test: `src/cognitive/__tests__/TranscriptRecoveryIndex.test.ts`

- [ ] **Step 1: Extend Attachment type**

In `src/utils/attachments.ts`, add to the `Attachment` union (near `relevant_memories`):

```typescript
  | {
      type: 'recovered_context'
      slices: Array<{
        source: string
        content: string
        relevanceScore: number
      }>
    }
```

- [ ] **Step 2: Write the failing test**

Create `src/cognitive/__tests__/TranscriptRecoveryIndex.test.ts`:

```typescript
import { describe, expect, test, beforeEach, afterEach } from 'bun:test'
import {
  startTranscriptRecoveryPrefetch,
  recoverySlicesToAttachments,
} from '../context/TranscriptRecoveryIndex.js'

const env = process.env

beforeEach(() => {
  process.env = { ...env, CLAUDE_CODE_COGNITIVE_LAYER: '1', CLAUDE_CODE_COGNITIVE_CONTEXT: '1' }
})
afterEach(() => { process.env = env })

describe('TranscriptRecoveryIndex', () => {
  test('prefetch returns undefined when flag off', () => {
    process.env.CLAUDE_CODE_COGNITIVE_LAYER = '0'
    const result = startTranscriptRecoveryPrefetch([], {
      querySource: 'repl_main_thread',
      agentId: undefined,
      abortController: new AbortController(),
    } as never)
    expect(result).toBeUndefined()
  })

  test('recoverySlicesToAttachments maps slices', () => {
    const attachments = recoverySlicesToAttachments([
      {
        sliceId: '1',
        source: 'transcript',
        content: 'Use PostgreSQL',
        relevanceScore: 0.9,
        tokenEstimate: 10,
      },
    ])
    expect(attachments[0]?.type).toBe('recovered_context')
  })
})
```

- [ ] **Step 3: Run test to verify it fails**

Run: `bun test src/cognitive/__tests__/TranscriptRecoveryIndex.test.ts`

Expected: FAIL

- [ ] **Step 4: Write minimal implementation**

Create `src/cognitive/context/TranscriptRecoveryIndex.ts`:

```typescript
import type { QuerySource } from '../../constants/querySource.js'
import type { ToolUseContext } from '../../Tool.js'
import type { Attachment, AttachmentMessage } from '../../utils/attachments.js'
import type { Message } from '../../types/message.js'
import { createChildAbortController } from '../../utils/abortController.js'
import { getUserMessageText } from '../../utils/messages.js'
import { isTranscriptRecoveryEnabled, isCognitiveScopeAllowed } from '../flags.js'
import { allocateRecoverySlices } from '../InjectionBudgetCoordinator.js'
import type { RecoveryPrefetch, RecoverySlice } from '../types.js'
import { buildRecoverySlicesFromMessages } from './localIndex.js'

export type TranscriptRecoveryContext = {
  querySource: QuerySource
  agentId: ToolUseContext['agentId']
  abortController: AbortController
  memoryBytesAlreadyUsed?: number
}

export function startTranscriptRecoveryPrefetch(
  messages: readonly Message[],
  ctx: TranscriptRecoveryContext,
): RecoveryPrefetch | undefined {
  if (!isTranscriptRecoveryEnabled()) return undefined
  if (!isCognitiveScopeAllowed({ querySource: ctx.querySource, agentId: ctx.agentId })) {
    return undefined
  }

  const lastUser = messages.findLast(m => m.type === 'user' && !m.isMeta)
  const query = lastUser ? getUserMessageText(lastUser) : ''
  if (!query || !/\s/.test(query.trim())) return undefined

  const controller = createChildAbortController(ctx.abortController)
  const firedAt = Date.now()

  const promise = Promise.resolve().then(() => {
    if (controller.signal.aborted) return []
    const slices = buildRecoverySlicesFromMessages(messages, query)
    return allocateRecoverySlices(slices, {
      maxBytes: Number.MAX_SAFE_INTEGER,
      memoryBytesAlreadyUsed: ctx.memoryBytesAlreadyUsed ?? 0,
    })
  })

  const handle: RecoveryPrefetch = {
    promise,
    settledAt: null,
    consumedOnIteration: -1,
    [Symbol.dispose]() {
      controller.abort()
    },
  }
  void promise.finally(() => {
    handle.settledAt = Date.now()
  })
  return handle
}

export function recoverySlicesToAttachments(
  slices: RecoverySlice[],
): Attachment[] {
  if (slices.length === 0) return []
  return [
    {
      type: 'recovered_context',
      slices: slices.map(s => ({
        source: s.source,
        content: s.content,
        relevanceScore: s.relevanceScore,
      })),
    },
  ]
}

export function toAttachmentMessages(
  slices: RecoverySlice[],
): AttachmentMessage[] {
  const attachments = recoverySlicesToAttachments(slices)
  return attachments.map(attachment => ({
    type: 'attachment' as const,
    attachment,
  })) as AttachmentMessage[]
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `bun test src/cognitive/__tests__/TranscriptRecoveryIndex.test.ts`

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/cognitive/context/TranscriptRecoveryIndex.ts src/utils/attachments.ts src/cognitive/__tests__/TranscriptRecoveryIndex.test.ts
git commit -m "feat(cognitive): add TranscriptRecoveryIndex prefetch and attachments"
```

---

## Task 7: query.ts Integration

**Files:**
- Modify: `src/query.ts` (~40 lines)
- Create: `src/cognitive/index.ts`

- [ ] **Step 1: Add barrel export**

Create `src/cognitive/index.ts`:

```typescript
export {
  startTranscriptRecoveryPrefetch,
  toAttachmentMessages,
} from './context/TranscriptRecoveryIndex.js'
export { snapshotPreCompactRegion } from './context/localIndex.js'
export { isTranscriptRecoveryEnabled } from './flags.js'
```

- [ ] **Step 2: Add import and prefetch init in queryLoop**

Near the existing `startRelevantMemoryPrefetch` block in `src/query.ts` (~line 301), add:

```typescript
import {
  startTranscriptRecoveryPrefetch,
  toAttachmentMessages,
  snapshotPreCompactRegion,
} from './cognitive/index.js'
import { collectSurfacedMemories } from './utils/attachments.js' // if not already imported
```

After `using pendingMemoryPrefetch = startRelevantMemoryPrefetch(...)`:

```typescript
  using pendingRecoveryPrefetch = startTranscriptRecoveryPrefetch(
    state.messages,
    {
      querySource,
      agentId: state.toolUseContext.agentId,
      abortController: state.toolUseContext.abortController,
      memoryBytesAlreadyUsed: collectSurfacedMemories(state.messages).totalBytes,
    },
  )
```

- [ ] **Step 3: Hook compact boundary snapshot**

Inside `if (compactionResult) {` block, **before** `messagesForQuery = postCompactMessages` (~line 528):

```typescript
      if (isTranscriptRecoveryEnabled()) {
        const boundaryId = deps.uuid()
        snapshotPreCompactRegion(messagesForQuery, boundaryId)
        // Phase 1: in-memory only via rebuild on next prefetch from postCompact messages
      }
```

Note: Phase 1 relies on `buildRecoverySlicesFromMessages` reading `compact_boundary` in the message list after compact — the snapshot call documents intent; persist to disk is optional follow-up if T1a needs cross-restart recovery.

- [ ] **Step 4: Add consume block after memory prefetch consume** (~line 1614)

```typescript
    if (
      pendingRecoveryPrefetch &&
      pendingRecoveryPrefetch.settledAt !== null &&
      pendingRecoveryPrefetch.consumedOnIteration === -1
    ) {
      const recoverySlices = await pendingRecoveryPrefetch.promise
      for (const msg of toAttachmentMessages(recoverySlices)) {
        yield msg
        toolResults.push(msg)
      }
      pendingRecoveryPrefetch.consumedOnIteration = turnCount - 1
    }
```

- [ ] **Step 5: Run unit tests (no REPL required)**

Run: `bun test src/cognitive/__tests__`

Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/cognitive/index.ts src/query.ts
git commit -m "feat(cognitive): integrate TranscriptRecoveryIndex into query loop"
```

---

## Task 8: T1a Integration Test + T5 Regression Guard

**Files:**
- Create: `src/cognitive/__tests__/integration.test.ts`

- [ ] **Step 1: Write integration test for T1a fixture**

Create `src/cognitive/__tests__/integration.test.ts`:

```typescript
import { describe, expect, test, beforeEach, afterEach } from 'bun:test'
import { readFileSync } from 'fs'
import { join } from 'path'
import {
  startTranscriptRecoveryPrefetch,
  toAttachmentMessages,
} from '../context/TranscriptRecoveryIndex.js'
import { collectSurfacedMemories } from '../../utils/attachments.js'

const fixture = JSON.parse(
  readFileSync(
    join(import.meta.dir, 'fixtures/compact-boundary-transcript.json'),
    'utf8',
  ),
)

const env = process.env

beforeEach(() => {
  process.env = {
    ...env,
    CLAUDE_CODE_COGNITIVE_LAYER: '1',
    CLAUDE_CODE_COGNITIVE_CONTEXT: '1',
  }
})
afterEach(() => { process.env = env })

describe('T1a compact boundary fixture', () => {
  test('recovery attachment contains pre-compact decision after boundary', async () => {
    const handle = startTranscriptRecoveryPrefetch(fixture.messages, {
      querySource: 'repl_main_thread',
      agentId: undefined,
      abortController: new AbortController(),
      memoryBytesAlreadyUsed: collectSurfacedMemories(fixture.messages).totalBytes,
    })
    expect(handle).toBeDefined()
    const slices = await handle!.promise
    const text = toAttachmentMessages(slices)
      .map(m => JSON.stringify(m.attachment))
      .join('\n')
    expect(text).toContain(fixture.expectedSnippet)
    handle![Symbol.dispose]()
  })
})

describe('T5 master flag off', () => {
  test('prefetch returns undefined when disabled', () => {
    process.env.CLAUDE_CODE_COGNITIVE_LAYER = '0'
    const handle = startTranscriptRecoveryPrefetch(fixture.messages, {
      querySource: 'repl_main_thread',
      agentId: undefined,
      abortController: new AbortController(),
    })
    expect(handle).toBeUndefined()
  })
})
```

- [ ] **Step 2: Run full cognitive test suite**

Run: `bun test src/cognitive/__tests__`

Expected: all tests PASS (T1a + T5 + unit tests)

- [ ] **Step 3: Commit**

```bash
git add src/cognitive/__tests__/integration.test.ts
git commit -m "test(cognitive): add T1a fixture and T5 regression tests"
```

---

## Task 9: Manual Verification (when REPL bootable)

**Files:** none

- [ ] **Step 1: Enable flags and run**

```powershell
$env:CLAUDE_CODE_COGNITIVE_LAYER = "1"
$env:CLAUDE_CODE_COGNITIVE_CONTEXT = "1"
bun test src/cognitive/__tests__
bun run dev
```

- [ ] **Step 2: Long session smoke**

In a session, make an explicit architecture decision early, continue past autocompact threshold, verify recovered context appears in transcript (search for `recovered_context` attachment in session log if visible).

- [ ] **Step 3: Verify flag off**

```powershell
$env:CLAUDE_CODE_COGNITIVE_LAYER = "0"
bun run dev
```

Confirm no behavioral change vs baseline.

---

## Spec Coverage Self-Review

| Spec requirement | Task |
|------------------|------|
| TranscriptRecoveryIndex, not memory/ | Task 5 `localIndex` skips `relevant_memories` |
| Prefetch/consume pattern | Task 6 + Task 7 |
| InjectionBudgetCoordinator | Task 3 |
| Scope gate main thread only | Task 1 + Task 6 |
| onCompactBoundary | Task 7 snapshot hook |
| ProviderCapabilities stub | Task 2 |
| T1a acceptance | Task 8 |
| T-pipe unit tests | Tasks 1–6 |
| T5 regression | Task 8 |
| Feature flags | Task 1 |
| No REPL dependency for CI | All tests via `bun test` |

**Deferred to Phase 1.5+ (not in this plan):** MemoryStore.surfaceOnSessionStart, disk persistence of recovery-index.json, queryProfiler telemetry events.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-25-transcript-recovery-index.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration

2. **Inline Execution** — implement tasks in this session with checkpoints between tasks

Which approach?
