import { mkdir, readFile, writeFile } from 'fs/promises'
import { join } from 'path'
import { getAutoMemPath } from '../../memdir/paths.js'
import { isTranscriptRecoveryEnabled } from '../flags.js'

const MAX_PERSISTED_BYTES = 50 * 1024 * 1024

export type PersistedSlice = {
  sliceId: string
  source: string
  content: string
  tokenEstimate: number
  compactBoundaryId?: string
  createdAt: number
}

export function getCognitiveDir(): string {
  return join(getAutoMemPath(), '.cognitive')
}

export function getSlicesPath(): string {
  return join(getCognitiveDir(), 'recovery-slices.json')
}

export async function persistSlices(
  slices: PersistedSlice[],
): Promise<void> {
  if (!isTranscriptRecoveryEnabled()) return
  if (slices.length === 0) return

  const dir = getCognitiveDir()
  await mkdir(dir, { recursive: true }).catch(() => {})

  const existing = await loadPersistedSlices()
  const byId = new Map(existing.map(s => [s.sliceId, s]))
  for (const s of slices) {
    byId.set(s.sliceId, s)
  }

  const merged = Array.from(byId.values())
  const json = JSON.stringify(merged)
  const byteSize = new TextEncoder().encode(json).length

  if (byteSize > MAX_PERSISTED_BYTES) {
    merged.sort((a, b) => b.createdAt - a.createdAt)
    const truncated = merged.slice(0, 500)
    await writeFile(getSlicesPath(), JSON.stringify(truncated), 'utf-8')
    return
  }

  await writeFile(getSlicesPath(), json, 'utf-8')
}

export async function loadPersistedSlices(): Promise<PersistedSlice[]> {
  try {
    const raw = await readFile(getSlicesPath(), 'utf-8')
    return JSON.parse(raw) as PersistedSlice[]
  } catch {
    return []
  }
}
