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
