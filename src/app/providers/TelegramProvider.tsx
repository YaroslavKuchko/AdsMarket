import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import {
  type TelegramColorScheme,
  type TelegramWebApp,
  type TelegramWebAppContact,
  type TelegramThemeParams,
  type TelegramWebAppUser,
  getTelegramColorScheme,
  getTelegramInitData,
  getTelegramLanguageCode,
  getTelegramStartParam,
  getTelegramThemeParams,
  getTelegramWebApp,
} from '../../shared/utils/telegram'

type TelegramContextValue = {
  isReady: boolean
  isTelegram: boolean
  webApp?: TelegramWebApp
  user?: TelegramWebAppUser
  initData?: string
  startParam?: string
  themeParams?: TelegramThemeParams
  colorScheme: TelegramColorScheme
  languageCode: string
  requestContact: () => Promise<boolean>
}

const TelegramContext = createContext<TelegramContextValue | null>(null)

export function useTelegram() {
  const ctx = useContext(TelegramContext)
  if (!ctx) {
    throw new Error('useTelegram must be used within TelegramProvider')
  }
  return ctx
}

export function TelegramProvider({ children }: { children: ReactNode }) {
  const [isReady, setIsReady] = useState(false)
  const [webApp, setWebApp] = useState<TelegramWebApp | undefined>(undefined)
  const [colorScheme, setColorScheme] = useState<TelegramColorScheme>('light')
  const [languageCode, setLanguageCode] = useState<string>('en')
  const [user, setUser] = useState<TelegramWebAppUser | undefined>(undefined)
  const [initData, setInitData] = useState<string | undefined>(undefined)
  const [startParam, setStartParam] = useState<string | undefined>(undefined)
  const [themeParams, setThemeParams] = useState<TelegramThemeParams | undefined>(undefined)

  useEffect(() => {
    let activeWa: TelegramWebApp | undefined
    let cleanupEvent = () => {}

    const sync = (wa: TelegramWebApp | undefined) => {
      setColorScheme(getTelegramColorScheme(wa) ?? 'light')
      setLanguageCode(getTelegramLanguageCode(wa) ?? 'en')
      setUser(wa?.initDataUnsafe?.user)
      setInitData(getTelegramInitData(wa))
      setStartParam(getTelegramStartParam(wa))
      setThemeParams(getTelegramThemeParams(wa))
      setIsReady(true)
    }

    const setup = (wa: TelegramWebApp | undefined) => {
      if (activeWa === wa) return
      cleanupEvent()
      activeWa = wa
      setWebApp(wa)

      // Telegram init (safe for browser fallback)
      wa?.ready?.()
      wa?.expand?.()

      sync(wa)

      // Optional: react to Telegram theme changes
      if (wa?.onEvent) {
        const handler = () => sync(wa)
        wa.onEvent('themeChanged', handler)
        cleanupEvent = () => wa.offEvent?.('themeChanged', handler)
      } else {
        cleanupEvent = () => {}
      }
    }

    // First attempt
    setup(getTelegramWebApp())

    // If opened in Telegram, WebApp object should exist, but some clients
    // may initialize it slightly позже — poll briefly.
    let tries = 0
    const intervalId = window.setInterval(() => {
      if (activeWa) return
      const found = getTelegramWebApp()
      if (found) {
        setup(found)
        window.clearInterval(intervalId)
        return
      }
      tries += 1
      if (tries >= 25) {
        // 2.5s max; stop polling, keep browser fallback.
        setIsReady(true)
        window.clearInterval(intervalId)
      }
    }, 100)

    return () => {
      cleanupEvent()
      window.clearInterval(intervalId)
    }
  }, [])

  const requestContact = async (): Promise<boolean> => {
    const wa = webApp
    if (!wa?.requestContact) return false
    // IMPORTANT: Mini App doesn't get the phone number itself.
    // Telegram sends the contact to the bot chat; frontend should refresh profile from backend.
    return await new Promise<boolean>((resolve) => {
      wa.requestContact?.((success: boolean, _contact?: TelegramWebAppContact) => resolve(Boolean(success)))
    })
  }

  const value = useMemo<TelegramContextValue>(
    () => ({
      isReady,
      // Important: telegram-web-app.js may define window.Telegram.WebApp even in regular browser.
      // We consider it "Telegram environment" only when we actually have initData or user.
      isTelegram: Boolean(webApp && (initData || user)),
      webApp,
      user,
      initData,
      startParam,
      themeParams,
      colorScheme,
      languageCode,
      requestContact,
    }),
    [
      colorScheme,
      initData,
      isReady,
      languageCode,
      startParam,
      themeParams,
      user,
      webApp,
    ],
  )

  return <TelegramContext.Provider value={value}>{children}</TelegramContext.Provider>
}


