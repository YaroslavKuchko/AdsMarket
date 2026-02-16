import { I18nextProvider } from 'react-i18next'
import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { useTelegram } from './TelegramProvider'
import { createI18n, normalizeLanguageCode } from '../../shared/i18n'

export function AppI18nProvider({ children }: { children: ReactNode }) {
  const { languageCode } = useTelegram()
  const [i18n] = useState(() => createI18n())

  const desired = useMemo(() => normalizeLanguageCode(languageCode), [languageCode])

  useEffect(() => {
    if (i18n.language !== desired) {
      void i18n.changeLanguage(desired)
    }
  }, [desired])

  return <I18nextProvider i18n={i18n}>{children}</I18nextProvider>
}


