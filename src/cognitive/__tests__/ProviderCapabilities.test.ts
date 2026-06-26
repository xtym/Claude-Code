import { describe, test, expect, beforeEach, afterEach } from 'bun:test'
import {
  getProviderCapabilities,
  setProviderCapabilitiesOverride,
} from '../ProviderCapabilities.js'

describe('ProviderCapabilities', () => {
  afterEach(() => {
    setProviderCapabilitiesOverride(null)
  })

  test('anthropic path enables cache and thinking', () => {
    const caps = getProviderCapabilities()
    expect(caps.supportsPromptCache).toBe(true)
    expect(caps.supportsThinking).toBe(true)
    expect(caps.supportsEffort).toBe(true)
    expect(caps.providerName).toBe('anthropic')
  })

  test('custom proxy disables cache and thinking', () => {
    setProviderCapabilitiesOverride({
      supportsPromptCache: false,
      supportsThinking: false,
      supportsEffort: false,
      providerName: 'custom-proxy',
    })
    const caps = getProviderCapabilities()
    expect(caps.supportsPromptCache).toBe(false)
    expect(caps.supportsThinking).toBe(false)
    expect(caps.supportsEffort).toBe(false)
  })

  test('override can enable caps for proxy', () => {
    setProviderCapabilitiesOverride({
      supportsPromptCache: true,
      supportsThinking: true,
      supportsEffort: true,
      providerName: 'deepseek',
    })
    const caps = getProviderCapabilities()
    expect(caps.supportsPromptCache).toBe(true)
    expect(caps.supportsThinking).toBe(true)
    expect(caps.providerName).toBe('deepseek')
  })

  test('clearing override returns to default', () => {
    setProviderCapabilitiesOverride({
      supportsPromptCache: false,
      supportsThinking: false,
      supportsEffort: false,
      providerName: 'custom-proxy',
    })
    setProviderCapabilitiesOverride(null)
    const caps = getProviderCapabilities()
    expect(caps.supportsPromptCache).toBe(true) // back to Anthropic defaults when no proxy
    expect(caps.providerName).toBe('anthropic')
  })
})
