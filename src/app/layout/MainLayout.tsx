import { Box } from '@mui/material'
import { useEffect } from 'react'
import { Outlet, useNavigate } from 'react-router-dom'
import { useTelegram } from '../providers/TelegramProvider'
import { routes } from '../router'
import { BottomNav } from './BottomNav'

/**
 * Main layout for Telegram Mini App.
 * - Provides safe-area paddings
 * - Keeps BottomNavigation fixed at the bottom
 */
export function MainLayout() {
  const navigate = useNavigate()
  const { startParam } = useTelegram()

  useEffect(() => {
    if (startParam === 'orders') {
      navigate(routes.orders, { replace: true })
    }
  }, [startParam, navigate])

  return (
    <Box
      sx={{
        minHeight: '100vh',
        bgcolor: 'background.default',
        color: 'text.primary',
        pt: 'env(safe-area-inset-top)',
        pb: 'calc(72px + env(safe-area-inset-bottom))',
      }}
    >
      <Box sx={{ px: 2, pt: 1, pb: 2 }}>
        <Outlet />
      </Box>
      <BottomNav />
    </Box>
  )
}


