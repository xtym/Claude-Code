import type { ToolErrorKind } from '../types.js'

export function classifyToolError(
  isError: boolean,
  permissionDenied: boolean,
  aborted: boolean,
  validationError: boolean,
): ToolErrorKind {
  if (!isError) return 'recoverable'
  if (aborted) return 'aborted'
  if (permissionDenied) return 'permission_denied'
  if (validationError) return 'validation'
  return 'recoverable'
}

export function replanThresholdFor(kind: ToolErrorKind): number {
  return kind === 'validation' ? 2 : 3
}
