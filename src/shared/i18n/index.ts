import i18next, { type i18n as I18nInstance } from 'i18next'
import { initReactI18next } from 'react-i18next'
import en from './locales/en.json'
import ru from './locales/ru.json'

export const resources = {
  en: { translation: en },
  ru: { translation: ru },
} as const

export type SupportedLanguage = keyof typeof resources

export function normalizeLanguageCode(code?: string): SupportedLanguage {
  if (!code) return 'en'
  const c = code.toLowerCase()
  if (c === 'ru' || c.startsWith('ru-')) return 'ru'
  return 'en'
}

export function createI18n(): I18nInstance {
  const instance = i18next.createInstance()
  void instance.use(initReactI18next).init({
    lng: 'en',
    fallbackLng: 'en',
    interpolation: { escapeValue: false },
    resources,
  })
  return instance
}


