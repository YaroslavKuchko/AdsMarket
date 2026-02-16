import {
  Box,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Slider,
  TextField,
  Typography,
} from '@mui/material'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../../app/providers/AuthProvider'
import { useTelegram } from '../../app/providers/TelegramProvider'
import { Button } from '../../shared/ui/Button'
import { getApiBase } from '../../shared/utils/apiBase'
import { getJson } from '../../shared/utils/api'
import { postJson } from '../../shared/utils/api'
import { starsIcon, usdtIcon } from '../../shared/assets/icons'

type StarsExchangeDialogProps = {
  open: boolean
  onClose: () => void
  onSuccess?: () => void
  starsBalance: number
}

export function StarsExchangeDialog({
  open,
  onClose,
  onSuccess,
  starsBalance,
}: StarsExchangeDialogProps) {
  const { t } = useTranslation()
  const { token } = useAuth()
  const { webApp } = useTelegram()
  const [amount, setAmount] = useState(100)
  const [inputValue, setInputValue] = useState('100')
  const [loading, setLoading] = useState(false)
  const [starsPerUsd, setStarsPerUsd] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (open) {
      setAmount(Math.min(100, Math.max(1, starsBalance)))
      setInputValue(String(Math.min(100, Math.max(1, starsBalance))))
      setError(null)
    }
  }, [open, starsBalance])

  useEffect(() => {
    if (open) {
      getJson<{ starsPerUsd?: number }>(`${getApiBase()}/api/config`)
        .then((c) => setStarsPerUsd(c.starsPerUsd ?? null))
        .catch(() => setStarsPerUsd(50))
    }
  }, [open])

  const maxAmount = Math.max(1, Math.min(100_000, Math.floor(starsBalance)))
  const clampedAmount = Math.max(1, Math.min(maxAmount, amount))
  const usdtReceived =
    starsPerUsd != null && starsPerUsd > 0
      ? (clampedAmount / starsPerUsd).toFixed(2)
      : '—'

  const handleSliderChange = (_: Event, value: number | number[]) => {
    const v = Array.isArray(value) ? value[0] : value
    setAmount(v)
    setInputValue(String(v))
    setError(null)
  }

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const v = e.target.value.replace(/\D/g, '')
    setInputValue(v)
    const num = parseInt(v, 10)
    if (!Number.isNaN(num)) setAmount(Math.max(1, Math.min(maxAmount, num)))
    setError(null)
  }

  const handleBlur = () => {
    const num = parseInt(inputValue, 10)
    if (Number.isNaN(num) || num < 1) {
      setAmount(1)
      setInputValue('1')
    } else if (num > maxAmount) {
      setAmount(maxAmount)
      setInputValue(String(maxAmount))
    } else {
      setAmount(num)
      setInputValue(String(num))
    }
  }

  const handleSubmit = async () => {
    if (!token) {
      setError(t('profile.starsExchange.noAuth'))
      return
    }
    const stars = Math.max(1, Math.min(maxAmount, parseInt(inputValue, 10) || amount))
    if (stars > starsBalance) {
      setError(t('profile.starsExchange.insufficient'))
      return
    }

    setLoading(true)
    setError(null)
    try {
      await postJson(
        `${getApiBase()}/api/stars/exchange`,
        { amount: stars },
        { headers: { Authorization: `Bearer ${token}` } }
      )
      webApp?.HapticFeedback?.notificationOccurred?.('success')
      onSuccess?.()
      onClose()
    } catch (e) {
      console.error('Stars exchange:', e)
      setError(t('profile.starsExchange.error'))
      webApp?.HapticFeedback?.notificationOccurred?.('error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open={open} onClose={onClose} PaperProps={{ sx: { borderRadius: 3, m: 2 } }}>
      <DialogTitle sx={{ fontWeight: 800, display: 'flex', alignItems: 'center', gap: 1 }}>
        <Box component="img" src={starsIcon} alt="" sx={{ width: 24, height: 24 }} />
        {t('profile.starsExchange.titlePrefix')}
        <Box component="img" src={usdtIcon} alt="" sx={{ width: 24, height: 24, borderRadius: '50%' }} />
        {t('profile.starsExchange.titleSuffix')}
      </DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          {t('profile.starsExchange.description', { rate: starsPerUsd ?? '—' })}
        </Typography>

        {starsBalance < 1 && (
          <Typography variant="body2" color="error" sx={{ mb: 2 }}>
            {t('profile.starsExchange.noBalance')}
          </Typography>
        )}

        <Box sx={{ px: 0.5 }}>
          <Slider
            value={clampedAmount}
            min={1}
            max={maxAmount}
            step={1}
            onChange={handleSliderChange}
            valueLabelDisplay="auto"
            valueLabelFormat={(v) => v.toLocaleString()}
            disabled={starsBalance < 1}
            sx={{
              mt: 1,
              mb: 2,
              '& .MuiSlider-thumb': {
                backgroundImage: `url(${starsIcon})`,
                backgroundRepeat: 'no-repeat',
                backgroundPosition: 'center',
                backgroundSize: '55%',
                backgroundColor: 'rgba(34, 168, 83, 0.95)',
                border: '2px solid #22C55E',
                '&:hover, &.Mui-focusVisible': {
                  boxShadow: '0 0 0 8px rgba(34, 168, 83, 0.25)',
                },
                '&.Mui-active': {
                  backgroundSize: '75%',
                  transform: 'translate(-50%, -50%) scale(1.35)',
                  boxShadow: '0 0 0 12px rgba(34, 168, 83, 0.3)',
                },
              },
            }}
          />
        </Box>

        <TextField
          fullWidth
          label={t('profile.starsExchange.amountLabel')}
          value={inputValue}
          onChange={handleInputChange}
          onBlur={handleBlur}
          placeholder={`1 - ${maxAmount.toLocaleString()}`}
          inputProps={{ inputMode: 'numeric', min: 1, max: maxAmount }}
          error={Boolean(error)}
          helperText={error}
          disabled={starsBalance < 1}
          sx={{ mb: 2 }}
        />

        <Box
          sx={{
            p: 1.5,
            borderRadius: 2,
            bgcolor: 'action.hover',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 1,
          }}
        >
          <Typography variant="body2" color="text.secondary">
            {t('profile.starsExchange.youReceive')}
          </Typography>
          <Typography sx={{ fontWeight: 800, fontSize: 18 }}>
            {usdtReceived} USDT
          </Typography>
        </Box>
      </DialogContent>
      <DialogActions sx={{ p: 2, pt: 0 }}>
        <Button variant="outlined" onClick={onClose}>
          {t('common.cancel')}
        </Button>
        <Button
          variant="contained"
          onClick={() => void handleSubmit()}
          disabled={loading || starsBalance < 1}
        >
          {loading ? t('profile.starsExchange.processing') : t('profile.starsExchange.exchange')}
        </Button>
      </DialogActions>
    </Dialog>
  )
}
