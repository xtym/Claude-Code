# Claude-Code — Cognitive Layer

## Architecture Overview

Claude-Code has a **Cognitive Layer** that sits outside the main `query()` loop and enhances agent intelligence. It is feature-flagged behind `CLAUDE_CODE_COGNITIVE_LAYER=1` with sub-flags for each capability.

### Enabling All Features

```powershell
$env:CLAUDE_CODE_COGNITIVE_LAYER = "1"
$env:CLAUDE_CODE_COGNITIVE_CONTEXT = "1"           # Transcript Recovery
$env:CLAUDE_CODE_COGNITIVE_MEMORY_SURFACE = "1"    # Cross-session memory surfacing
$env:CLAUDE_CODE_COGNITIVE_MEMORY_WRITE = "1"      # Memory write (stop hooks)
$env:CLAUDE_CODE_COGNITIVE_PLANNING = "1"           # Planning Orchestrator
$env:CLAUDE_CODE_COGNITIVE_EMBEDDING = "1"          # Semantic embedding (Phase 3.1)
```

### Implemented Modules

| Module | Phase | What it does |
|--------|-------|-------------|
| `localEmbeddingIndex` | 3.1 | Character n-gram (2-4) TF-IDF index with cosine similarity — pure TypeScript, no deps |
| `embeddingRanker` | 3.1 | Reranks RecoverySlices and memory files by embedding similarity to query; keyword-independent recall |
| `TranscriptRecoveryIndex` | 1 | After compact, injects pre-compact user decisions into context via `RecoverySlice[]` attachments |
| `localIndex` | 1 | Builds slices from transcript region before compact boundary |
| `InjectionBudgetCoordinator` | 1 | Manages shared 30KB token budget for cognitive attachments |
| `ProviderCapabilities` | 1 | Returns cache/thinking caps based on Anthropic vs proxy path |
| `relevanceScore` | 1 | Scores slices by keyword overlap, recency, compact proximity |
| `MemoryStore.recall()` / `surfaceOnSessionStart()` | 1.5 | Reads auto-memory files from `~/.claude/projects/<path>/memory/`, ranks by keyword, injects `session_memory_surface` attachment on first turn |
| `PlanningOrchestrator` | 2 | Track plan steps, trigger auto-replan after 3 recoverable tool errors (circuit breaker: 2 max) |
| `planState` / `toolErrorKind` | 2 | Sidecar `plan.json` read/write, tool error classification |
| `MemoryStore.write()` | 3 | Unified write facade: tag-based dedup via `findExistingMemoryByTags` (>40% tag overlap → merge), frontmatter YAML with `created`/`tags`/`description` |
| `deduplicate.ts` | 3 | Tag overlap matching, frontmatter-preserving content merge |
| `memoryWriteHook.ts` | 3 | Stop-hook integration: extracts top-3 keywords as tags, writes session memory on turn end |

### Key Design Decisions

- **Scope gate**: All cognitive features only activate on `repl_main_thread` (not subagents) via `isCognitiveScopeAllowed()`
- **Prefetch/consume pattern**: Recovery index uses the same `pendingPrefetch` pattern as existing memory prefetch for parallelism
- **Sidecar pattern**: Plan state is a `.plan.json` file next to `plan.md` — machine-readable without re-parsing markdown
- **Stop hooks are fire-and-forget**: `tryCognitiveMemoryWrite()` runs via `void` in stopHooks, never blocks the main loop
- **Tag dedup threshold**: >40% tag array intersection triggers merge instead of creating a new memory file

### File Layout

```
src/cognitive/
├── index.ts                          # Barrel exports
├── types.ts                          # Shared types (RecoverySlice, MemoryEntry, Plan, etc.)
├── flags.ts                          # Feature flag helpers
├── ProviderCapabilities.ts           # Anthropic vs proxy feature caps
├── InjectionBudgetCoordinator.ts     # Token budget for attachments
├── context/
│   ├── TranscriptRecoveryIndex.ts    # Phase 1: prefetch → attachment
│   ├── localIndex.ts                 # Phase 1: slice builder from messages
│   └── relevanceScore.ts             # Phase 1: slice relevance scoring
├── memory/
│   ├── MemoryStore.ts                # Phase 1.5 + 3: recall, surfaceOnSessionStart, write
│   ├── rankMemories.ts               # Phase 1.5: memory header ranking
│   ├── sessionSurface.ts             # Phase 1.5: first-turn detection + surface
│   ├── deduplicate.ts                # Phase 3: tag-overlap dedup + content merge
│   └── memoryWriteHook.ts            # Phase 3: stop-hooks integration
├── planning/
│   ├── PlanningOrchestrator.ts       # Phase 2: plan lifecycle + auto-replan
│   ├── planState.ts                  # Phase 2: plan.json sidecar I/O
│   ├── toolErrorKind.ts              # Phase 2: error classification
│   ├── planningHook.ts               # Phase 2: tool-result routing to orchestrator
│   └── replanAttachments.ts          # Phase 2: plan_updated attachment builder
└── __tests__/                        # 61 tests across 15 files
```

### Key Integration Points

- `src/query.ts` — `pendingRecoveryPrefetch` + compact boundary hook
- `src/query/stopHooks.ts` — `tryCognitiveMemoryWrite()` after autoDream
- `src/services/tools/toolExecution.ts` — `handlePlanningToolResult` after tool errors
- `src/utils/processUserInput/processUserInput.ts` — `maybeAppendSessionMemorySurface` on first turn
- `src/tools/ExitPlanModeTool/ExitPlanModeV2Tool.ts` — `onPlanApproved` after user approves plan
- `src/commands/replan/` — `/replan` slash command
