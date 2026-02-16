/**
 * Minimal Telegram WebApp SDK typings + safe access helpers.
 *
 * We intentionally DON'T install an npm SDK package here.
 * Telegram injects `window.Telegram.WebApp` in the Mini App environment.
 *
 * Docs: https://core.telegram.org/bots/webapps
 */

export type TelegramColorScheme = 'light' | 'dark'

export type TelegramWebAppUser = {
  id: number
  first_name?: string
  last_name?: string
  username?: string
  language_code?: string
  photo_url?: string
}

export type TelegramWebAppInitDataUnsafe = {
  user?: TelegramWebAppUser
  start_param?: string
  // ... other fields exist, but are not needed for the skeleton
}

export type TelegramWebAppContact = {
  phone_number?: string
  first_name?: string
  last_name?: string
  user_id?: number
  vcard?: string
}

export type TelegramWebAppEvent = 'themeChanged' | 'contactRequested'

export type TelegramThemeParams = Record<string, string | undefined>

export type TelegramWebApp = {
  colorScheme?: TelegramColorScheme
  /**
   * Raw initData query string (used to validate on backend).
   */
  initData?: string
  initDataUnsafe?: TelegramWebAppInitDataUnsafe
  themeParams?: TelegramThemeParams
  ready?: () => void
  expand?: () => void
  /**
   * Subscribe to Telegram events.
   * We keep it flexible because some events may pass payloads depending on platform version.
   */
  onEvent?: (eventType: TelegramWebAppEvent, callback: (...args: any[]) => void) => void
  offEvent?: (eventType: TelegramWebAppEvent, callback: (...args: any[]) => void) => void

  /**
   * Request user's contact (phone number).
   * Availability depends on Telegram version and app context.
   */
  requestContact?: (callback?: (success: boolean, contact?: TelegramWebAppContact) => void) => void

  /**
   * Simple native alert inside Telegram.
   */
  showAlert?: (message: string, callback?: () => void) => void

  /**
   * Haptic feedback (if supported).
   */
  HapticFeedback?: {
    notificationOccurred?: (type: 'error' | 'success' | 'warning') => void
  }

  /**
   * Open Telegram deep link (recommended for share links inside Telegram).
   */
  openTelegramLink?: (url: string) => void

  /**
   * Open external link.
   */
  openLink?: (url: string) => void

  /**
   * Open an invoice by URL (from createInvoiceLink). For Telegram Stars payments.
   * callback(success: boolean) is called when the invoice is closed.
   */
  openInvoice?: (url: string, callback?: (success: boolean) => void) => void
}

declare global {
  interface Window {
    Telegram?: {
      WebApp?: TelegramWebApp
    }
  }
}

export function getTelegramWebApp(): TelegramWebApp | undefined {
  return window.Telegram?.WebApp
}

export function getTelegramColorScheme(
  webApp: TelegramWebApp | undefined,
): TelegramColorScheme | undefined {
  return webApp?.colorScheme
}

export function getTelegramLanguageCode(webApp: TelegramWebApp | undefined): string | undefined {
  return webApp?.initDataUnsafe?.user?.language_code
}

export function getTelegramInitData(webApp: TelegramWebApp | undefined): string | undefined {
  return webApp?.initData
}

export function getTelegramStartParam(webApp: TelegramWebApp | undefined): string | undefined {
  return webApp?.initDataUnsafe?.start_param
}

export function getTelegramThemeParams(
  webApp: TelegramWebApp | undefined,
): TelegramThemeParams | undefined {
  return webApp?.themeParams
}


