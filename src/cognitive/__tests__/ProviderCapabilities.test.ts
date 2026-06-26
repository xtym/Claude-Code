import { describe, expect, test, beforeEach, afterEach } from 'bun:test'
import { getProviderCapabilities } from '../ProviderCapabilities.js'

const env = process.env

beforeEach(() => { process.env = { ...env } })
afterEach(() => { process.env = env })

describe('ProviderCapabilities', () => {
  test('anthropic path enables cache and thinking', () => {
    delete process.env.CLAUDE_CODE_CUSTOM_PROXY
    delete process.env.ANTHROPIC_BASE_URL
    const caps = getProviderCapabilities()
    expect(caps.supportsPromptCache).toBe(true)
    expect(caps.supportsThinking).toBe(true)
  })

  test('custom proxy disables cache and thinking', () => {
    process.env.CLAUDE_CODE_CUSTOM_PROXY = '1'
    const caps = getProviderCapabilities()
    expect(caps.supportsPromptCache).toBe(false)
    expect(caps.supportsThinking).toBe(false)
  })
})
