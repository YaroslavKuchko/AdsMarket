import { Box, Button, Typography } from '@mui/material'
import { Navigate, createBrowserRouter } from 'react-router-dom'
import { ChannelDetailsPage } from '../pages/Channel/ChannelDetailsPage'
import { MarketPage } from '../pages/Market/MarketPage'
import { MyChannelsPage } from '../pages/MyChannels/MyChannelsPage'
import { OrdersPage } from '../pages/Orders/OrdersPage'
import { ProfilePage } from '../pages/Profile/ProfilePage'
import { MainLayout } from './layout/MainLayout'

export const routes = {
  market: '/market',
  myChannels: '/my-channels',
  orders: '/orders',
  profile: '/profile',
  channelDetails: '/channel/:channelId',
} as const

export function createAppRouter() {
  return createBrowserRouter([
    {
      element: <MainLayout />,
      errorElement: (
        <Box sx={{ p: 3, textAlign: 'center', minHeight: '100vh', pt: 'env(safe-area-inset-top)' }}>
          <Typography variant="h6" sx={{ mb: 1, fontWeight: 700 }}>Что-то пошло не так</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Попробуйте обновить страницу или перезапустить приложение.
          </Typography>
          <Button variant="contained" onClick={() => window.location.reload()}>Обновить</Button>
        </Box>
      ),
      children: [
        { index: true, element: <Navigate to={routes.market} replace /> },
        { path: routes.market, element: <MarketPage /> },
        { path: routes.myChannels, element: <MyChannelsPage /> },
        { path: routes.orders, element: <OrdersPage /> },
        { path: routes.profile, element: <ProfilePage /> },
        { path: routes.channelDetails, element: <ChannelDetailsPage /> },
        { path: '*', element: <Navigate to={routes.market} replace /> },
      ],
    },
  ])
}


