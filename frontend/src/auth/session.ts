const ACCESS_TOKEN_KEY = 'cscec_access_token'
const REFRESH_TOKEN_KEY = 'cscec_refresh_token'
export const TOKEN_REFRESH_SKEW_MS = 60_000

export function isJwtAuthMode(): boolean {
  return import.meta.env.VITE_AUTH_MODE === 'jwt'
}

export function decodeJwtPayload(token: string): Record<string, unknown> | null {
  const parts = token.split('.')
  if (parts.length < 2) return null
  try {
    const base64 = parts[1].replace(/-/g, '+').replace(/_/g, '/')
    const padded = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), '=')
    return JSON.parse(atob(padded)) as Record<string, unknown>
  } catch {
    return null
  }
}

export function getAccessTokenExpiresAtMs(token: string): number | null {
  const payload = decodeJwtPayload(token)
  const exp = payload?.exp
  if (typeof exp !== 'number') return null
  return exp * 1000
}

export function isAccessTokenExpiringSoon(token: string, skewMs = TOKEN_REFRESH_SKEW_MS): boolean {
  const expiresAt = getAccessTokenExpiresAtMs(token)
  if (expiresAt === null) return false
  return Date.now() + skewMs >= expiresAt
}

export function getStoredAccessToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY)
}

export function getStoredRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_KEY)
}

export function storeAuthTokens(accessToken: string, refreshToken: string): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken)
  localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken)
}

export function clearAuthSession(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY)
  localStorage.removeItem(REFRESH_TOKEN_KEY)
}

export function hasStoredSession(): boolean {
  return Boolean(getStoredAccessToken())
}
