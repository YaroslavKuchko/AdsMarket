import TelegramIcon from '@mui/icons-material/Telegram'
import { Box, Button, Typography } from '@mui/material'
import { useTranslation } from 'react-i18next'

const TELEGRAM_LINK = 'https://t.me/ads_marketplacebot/adsmarket'

export function TelegramStubPage() {
  const { t } = useTranslation()

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        p: 3,
        background: 'linear-gradient(180deg, #1a1a2e 0%, #16213e 100%)',
        color: '#fff',
      }}
    >
      <Box
        component="img"
        src="/icon-512.png"
        alt="AdsMarket"
        sx={{ width: 120, height: 120, mb: 3, borderRadius: 2 }}
      />
      <Typography variant="h4" sx={{ fontWeight: 800, mb: 1, textAlign: 'center' }}>
        AdsMarket
      </Typography>
      <Typography variant="body1" sx={{ color: 'rgba(255,255,255,0.8)', mb: 4, textAlign: 'center', maxWidth: 320 }}>
        {t('stub.description')}
      </Typography>
      <Button
        variant="contained"
        href={TELEGRAM_LINK}
        target="_blank"
        rel="noopener noreferrer"
        startIcon={<TelegramIcon />}
        sx={{
          py: 1.5,
          px: 3,
          fontSize: '1.1rem',
          fontWeight: 700,
          bgcolor: '#0088cc',
          '&:hover': { bgcolor: '#0077b5' },
        }}
      >
        {t('stub.openInTelegram')}
      </Button>
    </Box>
  )
}
