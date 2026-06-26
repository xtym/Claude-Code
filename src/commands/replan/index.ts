import type { Command } from '../../commands.js'
import { isPlanningEnabled } from '../../cognitive/flags.js'

const replan = {
  type: 'local',
  name: 'replan',
  description: 'Revise the active session plan after failures or changed requirements',
  argumentHint: '[reason]',
  isEnabled: () => isPlanningEnabled(),
  supportsNonInteractive: true,
  load: () => import('./replan.js'),
} satisfies Command

export default replan
