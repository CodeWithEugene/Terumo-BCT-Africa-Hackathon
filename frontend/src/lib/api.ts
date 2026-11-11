// One place for every call to the server, the offline switch and the small local cache.

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

const OFFLINE_KEY = 'sp:simulate-offline'

export function isSimulatedOffline(): boolean {
  try {
    return localStorage.getItem(OFFLINE_KEY) === '1'
  } catch {
    return false
  }
}

export function setSimulatedOffline(on: boolean): void {
  try {
    localStorage.setItem(OFFLINE_KEY, on ? '1' : '0')
  } catch {
    /* storage not available */
  }
  window.dispatchEvent(new Event('sp:offline-changed'))
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (isSimulatedOffline()) throw new ApiError(0, 'Offline (simulated).')
  let response: Response
  try {
    response = await fetch(path, {
      credentials: 'same-origin',
      headers: init?.body ? { 'Content-Type': 'application/json' } : undefined,
      ...init,
    })
  } catch {
    throw new ApiError(0, 'Could not reach the server.')
  }
  if (!response.ok) {
    let detail = `The server answered ${response.status}.`
    try {
      const body = await response.json()
      if (typeof body.detail === 'string') detail = body.detail
    } catch {
      /* not JSON */
    }
    throw new ApiError(response.status, detail)
  }
  return (await response.json()) as T
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) }),
}

// --- Local cache: the last answer for a request, kept in the browser -----------------

interface Cached<T> {
  savedAt: string
  data: T
}

export function saveCache<T>(key: string, data: T): void {
  try {
    localStorage.setItem(`sp:cache:${key}`, JSON.stringify({ savedAt: new Date().toISOString(), data }))
  } catch {
    /* storage full or not available: the app still works online */
  }
}

export function readCache<T>(key: string): Cached<T> | null {
  try {
    const raw = localStorage.getItem(`sp:cache:${key}`)
    return raw ? (JSON.parse(raw) as Cached<T>) : null
  } catch {
    return null
  }
}

export function clearCache(): void {
  try {
    Object.keys(localStorage)
      .filter((k) => k.startsWith('sp:cache:'))
      .forEach((k) => localStorage.removeItem(k))
  } catch {
    /* nothing to clear */
  }
}

/** Get from the server; if that fails, fall back to the last saved answer. */
export async function getWithCache<T>(path: string): Promise<{ data: T; cachedAt: string | null }> {
  try {
    const data = await api.get<T>(path)
    saveCache(path, data)
    return { data, cachedAt: null }
  } catch (error) {
    const cached = readCache<T>(path)
    const unreachable = error instanceof ApiError && (error.status === 0 || error.status >= 500)
    if (cached && unreachable) return { data: cached.data, cachedAt: cached.savedAt }
    throw error
  }
}
