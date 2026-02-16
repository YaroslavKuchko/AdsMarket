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
import { getTelegramWebApp } from '../../shared/utils/telegram'
import { postJson } from '../../shared/utils/api'
import { starsIcon } from '../../shared/assets/icons'

const MIN_STARS = 1
const MAX_STARS = 100_000

type StarsTopUpDialogProps = {
  open: boolean
  onClose: () => void
  onSuccess?: () => void
}

export function StarsTopUpDialog({ open, onClose, onSuccess }: StarsTopUpDialogProps) {
  const { t } = useTranslation()
  const { token } = useAuth()
  const { webApp } = useTelegram()
  const [amount, setAmount] = useState(100)
  const [inputValue, setInputValue] = useState('100')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (open) {
      setAmount(100)
      setInputValue('100')
      setError(null)
    }
  }, [open])

  const clampedAmount = Math.max(MIN_STARS, Math.min(MAX_STARS, amount))

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
    if (!Number.isNaN(num)) {
      const clamped = Math.max(MIN_STARS, Math.min(MAX_STARS, num))
      setAmount(clamped)
    }
    setError(null)
  }

  const handleBlur = () => {
    const num = parseInt(inputValue, 10)
    if (Number.isNaN(num) || num < MIN_STARS) {
      setAmount(MIN_STARS)
      setInputValue(String(MIN_STARS))
    } else if (num > MAX_STARS) {
      setAmount(MAX_STARS)
      setInputValue(String(MAX_STARS))
    } else {
      setAmount(num)
      setInputValue(String(num))
    }
  }

  const handleSubmit = async () => {
    if (!token) {
      setError(t('profile.starsTopUp.noAuth'))
      return
    }
    const stars = Math.max(MIN_STARS, Math.min(MAX_STARS, parseInt(inputValue, 10) || amount))
    if (stars < MIN_STARS || stars > MAX_STARS) {
      setError(t('profile.starsTopUp.invalidAmount'))
      return
    }

    const openInvoice = getTelegramWebApp()?.openInvoice ?? webApp?.openInvoice
    if (!openInvoice) {
      setError(t('profile.starsTopUp.notSupported'))
      return
    }

    setLoading(true)
    setError(null)
    try {
      const base = getApiBase()
      const res = await postJson<{ invoiceUrl: string }>(
        `${base}/api/stars/create-invoice`,
        { amount: stars },
        { headers: { Authorization: `Bearer ${token}` } }
      )
      if (!res.invoiceUrl) {
        setError(t('profile.starsTopUp.invoiceError'))
        return
      }
      onClose()
      openInvoice(res.invoiceUrl, (success) => {
        if (success) {
          onSuccess?.()
          webApp?.HapticFeedback?.notificationOccurred?.('success')
        } else {
          webApp?.HapticFeedback?.notificationOccurred?.('error')
        }
      })
    } catch (e) {
      console.error('Stars invoice:', e)
      setError(t('profile.starsTopUp.invoiceError'))
      webApp?.HapticFeedback?.notificationOccurred?.('error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      PaperProps={{
        sx: { borderRadius: 3, m: 2 },
      }}
    >
      <DialogTitle sx={{ fontWeight: 800, display: 'flex', alignItems: 'center', gap: 1 }}>
        <Box component="img" src={starsIcon} alt="" sx={{ width: 24, height: 24 }} />
        {t('profile.starsTopUp.title')}
      </DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          {t('profile.starsTopUp.description')}
        </Typography>
        <Box sx={{ px: 0.5 }}>
          <Slider
            value={clampedAmount}
            min={MIN_STARS}
            max={MAX_STARS}
            step={1}
            onChange={handleSliderChange}
            valueLabelDisplay="auto"
            valueLabelFormat={(v) => v.toLocaleString()}
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
          label={t('profile.starsTopUp.amountLabel')}
          value={inputValue}
          onChange={handleInputChange}
          onBlur={handleBlur}
          placeholder={`${MIN_STARS} - ${MAX_STARS.toLocaleString()}`}
          inputProps={{
            inputMode: 'numeric',
            pattern: '[0-9]*',
            min: MIN_STARS,
            max: MAX_STARS,
          }}
          error={Boolean(error)}
          helperText={error}
        />
      </DialogContent>
      <DialogActions sx={{ p: 2, pt: 0 }}>
        <Button variant="outlined" onClick={onClose}>
          {t('common.cancel')}
        </Button>
        <Button variant="contained" onClick={() => void handleSubmit()} disabled={loading}>
          {loading ? t('profile.starsTopUp.loading') : t('profile.wallet.topUp')}
        </Button>
      </DialogActions>
    </Dialog>
  )
}
