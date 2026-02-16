import type { ReactNode } from 'react'
import { useTelegram } from './providers/TelegramProvider'
import { TelegramStubPage } from '../pages/TelegramStubPage'

type TelegramGateProps = {
  children: ReactNode
}

/**
 * When the app is opened outside Telegram (e.g. in a browser),
 * show a stub with a button to open in Telegram.
 */
export function TelegramGate({ children }: TelegramGateProps) {
  const { isTelegram, isReady } = useTelegram()

  if (!isReady) {
    return null // brief flash; providers are still initializing
  }

  if (!isTelegram) {
    return <TelegramStubPage />
  }

  return <>{children}</>
}
