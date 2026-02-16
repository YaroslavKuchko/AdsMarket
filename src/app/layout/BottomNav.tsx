import CampaignRoundedIcon from '@mui/icons-material/CampaignRounded'
import PersonRoundedIcon from '@mui/icons-material/PersonRounded'
import ReceiptLongRoundedIcon from '@mui/icons-material/ReceiptLongRounded'
import StorefrontRoundedIcon from '@mui/icons-material/StorefrontRounded'
import { BottomNavigation, BottomNavigationAction, Paper } from '@mui/material'
import { useMemo } from 'react'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { useLocation, useNavigate } from 'react-router-dom'
import { routes } from '../router'

type TabValue = (typeof routes)[keyof typeof routes]

export function BottomNav() {
  const { t } = useTranslation()
  const location = useLocation()
  const navigate = useNavigate()

  const tabs = useMemo(
    () =>
      [
        {
          value: routes.market,
          label: t('nav.market'),
          icon: <StorefrontRoundedIcon />,
        },
        {
          value: routes.myChannels,
          label: t('nav.myChannels'),
          icon: <CampaignRoundedIcon />,
        },
        {
          value: routes.orders,
          label: t('nav.orders'),
          icon: <ReceiptLongRoundedIcon />,
        },
        {
          value: routes.profile,
          label: t('nav.profile'),
          icon: <PersonRoundedIcon />,
        },
      ] as const satisfies ReadonlyArray<{
        value: TabValue
        label: string
        icon: ReactNode
      }>,
    [t],
  )

  const value =
    tabs.find((x) => location.pathname.startsWith(x.value))?.value ?? routes.market

  return (
    <Paper
      elevation={0}
      sx={{
        position: 'fixed',
        left: 0,
        right: 0,
        bottom: 0,
        borderTop: 1,
        borderColor: 'divider',
        pb: 'env(safe-area-inset-bottom)',
      }}
    >
      <BottomNavigation
        showLabels
        value={value}
        onChange={(_, nextValue: TabValue) => navigate(nextValue)}
        sx={{
          height: 72,
          bgcolor: 'background.paper',
          '& .MuiBottomNavigationAction-label': {
            fontSize: 12,
            mt: 0.25,
          },
        }}
      >
        {tabs.map((tab) => (
          <BottomNavigationAction
            key={tab.value}
            value={tab.value}
            label={tab.label}
            icon={tab.icon}
          />
        ))}
      </BottomNavigation>
    </Paper>
  )
}


