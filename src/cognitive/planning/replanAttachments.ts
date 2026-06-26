import type { Attachment } from '../../utils/attachments.js'
import type { PlanState } from '../types.js'

export function buildPlanUpdatedAttachment(
  revisedPlan: PlanState,
  reason: string,
): Attachment {
  return {
    type: 'plan_updated',
    reason,
    planId: revisedPlan.id,
    activeStepId: revisedPlan.activeStepId,
    steps: revisedPlan.steps.map(step => ({
      id: step.id,
      description: step.description,
      status: step.status,
    })),
  }
}
