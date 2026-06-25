import { isEnvTruthy } from './envUtils.js'
import { isFirstPartyAnthropicBaseUrl } from './model/providers.js'

/**
 * True when API traffic goes to a non-Anthropic endpoint (local LiteLLM proxy,
 * OpenAI-compatible gateway, etc.). In this mode we skip OAuth / Claude login.
 */
export function isCustomApiProxyMode(): boolean {
  if (isEnvTruthy(process.env.CLAUDE_CODE_CUSTOM_PROXY)) {
    return true
  }
  if (!process.env.ANTHROPIC_BASE_URL) {
    return false
  }
  return !isFirstPartyAnthropicBaseUrl()
}
