import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { useTelegram } from './TelegramProvider'
import { ApiError, getJson, postJson } from '../../shared/utils/api'
import { getApiBase } from '../../shared/utils/apiBase'

export type AuthStatus = 'idle' | 'loading' | 'authenticated' | 'error'

export type AuthUser = {
  telegramId: number
  username?: string | null
  firstName?: string | null
  lastName?: string | null
  languageCode?: string | null
  photoUrl?: string | null
  phoneNumber?: string | null
}

type TelegramAuthResponse = {
  token: string
  user: AuthUser
}

type AuthContextValue = {
  status: AuthStatus
  token?: string
  user?: AuthUser
  error?: string
  lastAuthUrl?: string
  lastAuthHttpStatus?: number
  retry: () => void
  logout: () => void
  refreshUser: () => Promise<AuthUser | undefined>
  setPreferredLanguage: (language: string) => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

const STORAGE_KEY = 'admarketplace.jwt'

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const { isTelegram, isReady, initData } = useTelegram()

  const [status, setStatus] = useState<AuthStatus>('idle')
  const [token, setToken] = useState<string | undefined>(() => localStorage.getItem(STORAGE_KEY) ?? undefined)
  const [user, setUser] = useState<AuthUser | undefined>(undefined)
  const [error, setError] = useState<string | undefined>(undefined)
  const [lastAuthUrl, setLastAuthUrl] = useState<string | undefined>(undefined)
  const [lastAuthHttpStatus, setLastAuthHttpStatus] = useState<number | undefined>(undefined)
  // wsStatus is reserved for future UI; keep it out to avoid unused var warnings.
  const [lastInitDataAuthed, setLastInitDataAuthed] = useState<string | undefined>(undefined)

  const logout = () => {
    localStorage.removeItem(STORAGE_KEY)
    setToken(undefined)
    setUser(undefined)
    setStatus('idle')
    setError(undefined)
  }

  const retry = () => {
    // Keep current user visible; just retry auth in background.
    setStatus('idle')
  }

  // Realtime updates (e.g. phone verification) via WebSocket.
  useEffect(() => {
    if (!token) return
    if (status !== 'authenticated') return

    const base = getApiBase()
    if (!base.startsWith('http')) return

    const wsUrl = base.replace(/^https:/, 'wss:').replace(/^http:/, 'ws:') + `/ws?token=${encodeURIComponent(token)}`

    let ws: WebSocket | null = null
    let closed = false
    try {
      ws = new WebSocket(wsUrl)
    } catch {
      return
    }

    ws.onopen = () => {
      if (closed) return
      // connected
    }
    ws.onerror = () => {
      if (closed) return
      // error
    }
    ws.onmessage = (ev) => {
      if (closed) return
      try {
        const msg = JSON.parse(ev.data as string) as { type?: string; phoneNumber?: string }
        if (msg.type === 'phone_updated' && msg.phoneNumber) {
          setUser((prev) => (prev ? { ...prev, phoneNumber: msg.phoneNumber } : prev))
        }
      } catch {
        // ignore
      }
    }

    return () => {
      closed = true
      try {
        ws?.close()
      } catch {
        // ignore
      }
    }
  }, [status, token])

  const refreshUser = async (): Promise<AuthUser | undefined> => {
    if (!token) {
      throw new Error('not_authenticated')
    }
    const apiBase = getApiBase()
    if (!apiBase) return undefined
    const url = `${apiBase}/api/user/profile`
    const next = await getJson<AuthUser>(url, {
      headers: { Authorization: `Bearer ${token}` },
    })
    setUser(next)
    return next
  }

  const hasTelegramAuth = Boolean(isReady && isTelegram && initData)

  const setPreferredLanguage = async (language: string): Promise<void> => {
    if (!token) return
    const apiBase = getApiBase()
    if (!apiBase) return
    const url = `${apiBase}/api/user/language`
    await postJson(url, { language }, { headers: { Authorization: `Bearer ${token}` } })
  }

  useEffect(() => {
    // Telegram-first flow:
    // On every Mini App open (initData available), validate initData on backend and obtain JWT.
    if (!isReady) return
    if (!isTelegram) return
    if (!initData) return
    if (lastInitDataAuthed === initData) return

    const apiBase = getApiBase()
    const url = `${apiBase}/api/auth/telegram`
    setLastAuthUrl(url)
    setLastAuthHttpStatus(undefined)

    const ac = new AbortController()
    const timeoutId = window.setTimeout(() => ac.abort(), 12000)

    setStatus('loading')
    setError(undefined)

    void postJson<TelegramAuthResponse>(
      url,
      { initData, isAdmin: false },
      {
        signal: ac.signal,
      },
    )
      .then((res) => {
        window.clearTimeout(timeoutId)
        setToken(res.token)
        localStorage.setItem(STORAGE_KEY, res.token)
        setUser(res.user)
        setStatus('authenticated')
        setLastInitDataAuthed(initData)
      })
      .catch((e: unknown) => {
        window.clearTimeout(timeoutId)
        setStatus('error')
        if (e instanceof DOMException && e.name === 'AbortError') {
          setError('auth_timeout')
          return
        }
        if (e instanceof ApiError) {
          setLastAuthHttpStatus(e.status)
          setError(e.bodyText ?? e.message)
          return
        }
        setError(e instanceof Error ? e.message : 'unknown_error')
      })

    return () => {
      window.clearTimeout(timeoutId)
      ac.abort()
    }
  }, [initData, isReady, isTelegram, lastInitDataAuthed])

  // Fallback: if we're NOT in Telegram (or initData missing) but have a stored JWT, load profile.
  useEffect(() => {
    if (hasTelegramAuth) return
    if (status !== 'idle') return
    if (!token) return
    if (user) return

    let cancelled = false
    setStatus('loading')
    void refreshUser()
      .then((u) => {
        if (cancelled) return
        if (u) {
          setStatus('authenticated')
        } else {
          logout()
        }
      })
      .catch(() => {
        if (cancelled) return
        logout()
      })

    return () => {
      cancelled = true
    }
  }, [hasTelegramAuth, logout, refreshUser, status, token, user])

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      token,
      user,
      error,
      lastAuthUrl,
      lastAuthHttpStatus,
      retry,
      logout,
      refreshUser,
      setPreferredLanguage,
    }),
    [
      error,
      lastAuthHttpStatus,
      lastAuthUrl,
      logout,
      refreshUser,
      retry,
      setPreferredLanguage,
      status,
      token,
      user,
    ],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}


