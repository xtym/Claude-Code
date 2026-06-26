import { isCustomApiProxyMode } from '../utils/customProxy.js'
import { getMainLoopModel } from '../utils/model/model.js'

export type ProviderCapabilities = {
  supportsPromptCache: boolean
  supportsThinking: boolean
  supportsEffort: boolean
  providerName: string
}

// Allow overriding provider caps externally (for testing and dynamic updates)
let overriddenCaps: ProviderCapabilities | null = null

export function setProviderCapabilitiesOverride(
  caps: ProviderCapabilities | null,
): void {
  overriddenCaps = caps
}

export function getProviderCapabilities(): ProviderCapabilities {
  if (overriddenCaps) return overriddenCaps

  if (isCustomApiProxyMode()) {
    // Try to detect from model name
    const model = getMainLoopModel()
    if (model) {
      const knownCaps = detectProviderFromModel(model)
      if (knownCaps) return knownCaps
    }
    // Default proxy caps: conservative
    return {
      supportsPromptCache: false,
      supportsThinking: false,
      supportsEffort: false,
      providerName: 'custom-proxy',
    }
  }

  return {
    supportsPromptCache: true,
    supportsThinking: true,
    supportsEffort: true,
    providerName: 'anthropic',
  }
}

function detectProviderFromModel(model: string): ProviderCapabilities | null {
  const m = model.toLowerCase()

  // OpenAI-compatible
  if (m.includes('gpt') || m.includes('o1') || m.includes('o3')) {
    return {
      supportsPromptCache: true,
      supportsThinking: false,
      supportsEffort: false,
      providerName: 'openai',
    }
  }

  // Google
  if (m.includes('gemini')) {
    return {
      supportsPromptCache: false,
      supportsThinking: false,
      supportsEffort: false,
      providerName: 'google',
    }
  }

  // DeepSeek
  if (m.includes('deepseek')) {
    return {
      supportsPromptCache: true,
      supportsThinking: true,
      supportsEffort: false,
      providerName: 'deepseek',
    }
  }

  // Groq, Mistral, etc.
  if (m.includes('groq') || m.includes('mixtral') || m.includes('llama')) {
    return {
      supportsPromptCache: false,
      supportsThinking: false,
      supportsEffort: false,
      providerName: 'open-source',
    }
  }

  // Unknown model — return null to use defaults
  return null
}
