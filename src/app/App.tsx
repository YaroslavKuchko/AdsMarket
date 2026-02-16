import { Box, Button, Typography } from '@mui/material'
import { RouterProvider } from 'react-router-dom'
import { createAppRouter } from './router'
import { ErrorBoundary } from './ErrorBoundary'
import { AuthProvider } from './providers/AuthProvider'
import { AppI18nProvider } from './providers/I18nProvider'
import { TelegramProvider } from './providers/TelegramProvider'
import { AppThemeProvider } from './providers/ThemeProvider'
import { TonConnectProvider } from './providers/TonConnectProvider'
import { TelegramGate } from './TelegramGate'

const router = createAppRouter()

export function App() {
  return (
    <ErrorBoundary
      fallback={
        <Box sx={{ p: 3, textAlign: 'center', minHeight: '100vh', pt: 'env(safe-area-inset-top)' }}>
          <Typography variant="h6" sx={{ mb: 1, fontWeight: 700 }}>Что-то пошло не так</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Попробуйте обновить страницу или перезапустить приложение.
          </Typography>
          <Button variant="contained" onClick={() => window.location.reload()}>Обновить</Button>
        </Box>
      }
    >
      <TelegramProvider>
        <TonConnectProvider>
          <AppThemeProvider>
            <AppI18nProvider>
              <AuthProvider>
                <TelegramGate>
                  <RouterProvider router={router} />
                </TelegramGate>
              </AuthProvider>
            </AppI18nProvider>
          </AppThemeProvider>
        </TonConnectProvider>
      </TelegramProvider>
    </ErrorBoundary>
  )
}


