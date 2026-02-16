import { CssBaseline, ThemeProvider as MuiThemeProvider } from '@mui/material'
import { createContext, useContext, useMemo, useState } from 'react'
import type { PaletteMode } from '@mui/material'
import type { ReactNode } from 'react'
import { useTelegram } from './TelegramProvider'
import { createDarkTheme } from '../../shared/theme/dark'
import { createLightTheme } from '../../shared/theme/light'

export type ThemePreference = 'auto' | PaletteMode

type ThemeContextValue = {
  preference: ThemePreference
  setPreference: (next: ThemePreference) => void
  effectiveMode: PaletteMode
}

const ThemeContext = createContext<ThemeContextValue | null>(null)

export function useAppTheme() {
  const ctx = useContext(ThemeContext)
  if (!ctx) {
    throw new Error('useAppTheme must be used within AppThemeProvider')
  }
  return ctx
}

export function AppThemeProvider({ children }: { children: ReactNode }) {
  const { colorScheme } = useTelegram()
  const [preference, setPreference] = useState<ThemePreference>('auto')

  const effectiveMode: PaletteMode =
    preference === 'auto' ? (colorScheme === 'dark' ? 'dark' : 'light') : preference

  const theme = useMemo(
    () => (effectiveMode === 'dark' ? createDarkTheme() : createLightTheme()),
    [effectiveMode],
  )

  const value = useMemo<ThemeContextValue>(
    () => ({ preference, setPreference, effectiveMode }),
    [effectiveMode, preference],
  )

  return (
    <ThemeContext.Provider value={value}>
      <MuiThemeProvider theme={theme}>
        <CssBaseline />
        {children}
      </MuiThemeProvider>
    </ThemeContext.Provider>
  )
}


