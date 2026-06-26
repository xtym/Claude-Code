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
    for (const q of queryTokens) {
      if (t === q || t.includes(q) || q.includes(t)) {
        matches++
        break
      }
    }
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
