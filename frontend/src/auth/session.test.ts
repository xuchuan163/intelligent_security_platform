import {
  clearAuthSession,
  decodeJwtPayload,
  getAccessTokenExpiresAtMs,
  getStoredAccessToken,
  getStoredRefreshToken,
  hasStoredSession,
  isAccessTokenExpiringSoon,
  storeAuthTokens,
} from './session'

const memoryStore = new Map<string, string>()
Object.defineProperty(globalThis, 'localStorage', {
  value: {
    getItem: (key: string) => memoryStore.get(key) ?? null,
    setItem: (key: string, value: string) => {
      memoryStore.set(key, value)
    },
    removeItem: (key: string) => {
      memoryStore.delete(key)
    },
  },
  configurable: true,
})

function assertEqual<T>(actual: T, expected: T, message: string) {
  if (actual !== expected) {
    throw new Error(`${message}: expected ${String(expected)}, got ${String(actual)}`)
  }
}

function assertTruthy(value: unknown, message: string) {
  if (!value) {
    throw new Error(message)
  }
}

function assertFalsy(value: unknown, message: string) {
  if (value) {
    throw new Error(message)
  }
}

function buildToken(expSeconds: number): string {
  const header = btoa(JSON.stringify({ alg: 'none', typ: 'JWT' }))
  const payload = btoa(JSON.stringify({ sub: 'mock-admin', exp: expSeconds }))
  return `${header}.${payload}.signature`
}

const futureExp = Math.floor(Date.now() / 1000) + 3600
const pastExp = Math.floor(Date.now() / 1000) - 60
const futureToken = buildToken(futureExp)
const pastToken = buildToken(pastExp)

assertTruthy(decodeJwtPayload(futureToken)?.sub, 'decode jwt payload')
assertEqual(getAccessTokenExpiresAtMs(futureToken), futureExp * 1000, 'jwt exp ms')
assertFalsy(isAccessTokenExpiringSoon(futureToken, 60_000), 'future token not expiring soon')
assertTruthy(isAccessTokenExpiringSoon(pastToken, 60_000), 'past token expiring soon')

storeAuthTokens('access-demo', 'refresh-demo')
assertEqual(getStoredAccessToken(), 'access-demo', 'store access token')
assertEqual(getStoredRefreshToken(), 'refresh-demo', 'store refresh token')
assertTruthy(hasStoredSession(), 'has stored session')

clearAuthSession()
assertEqual(getStoredAccessToken(), null, 'clear access token')
assertEqual(getStoredRefreshToken(), null, 'clear refresh token')
assertFalsy(hasStoredSession(), 'session cleared')

console.log('session.test.ts: all assertions passed')
