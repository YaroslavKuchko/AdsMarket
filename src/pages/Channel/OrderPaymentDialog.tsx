import CloseRoundedIcon from '@mui/icons-material/CloseRounded'
import {
  Box,
  Dialog,
  DialogContent,
  DialogTitle,
  IconButton,
  Radio,
  RadioGroup,
  FormControlLabel,
  Typography,
} from '@mui/material'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../../app/providers/AuthProvider'
import { getApiBase } from '../../shared/utils/apiBase'
import { ApiError, getJson, postJson } from '../../shared/utils/api'
import { Button } from '../../shared/ui/Button'
import { starsIcon, tonIcon, usdtIcon } from '../../shared/assets/icons'

type Config = { starsPerUsd: number; tonUsdPrice: number }
type Balances = { stars: number; ton: number; usdt: number }
type Format = { id: number; priceStars: number; priceTon: number | null; priceUsdt: number | null; formatType: string; durationHours: number }

type OrderPaymentDialogProps = {
  open: boolean
  onClose: () => void
  onSuccess: (writePostLink: string) => void
  format: Format
  channelId: number
}

export function OrderPaymentDialog({
  open,
  onClose,
  onSuccess,
  format,
  channelId,
}: OrderPaymentDialogProps) {
  const { t } = useTranslation()
  const { token } = useAuth()
  const [config, setConfig] = useState<Config | null>(null)
  const [balances, setBalances] = useState<Balances | null>(null)
  const [currency, setCurrency] = useState<'stars' | 'usdt' | 'ton'>('usdt')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (open && token) {
      setError(null)
      const base = getApiBase()
      Promise.all([
        getJson<Config>(`${base}/api/config`, { headers: { Authorization: `Bearer ${token}` } }),
        getJson<Balances>(`${base}/api/wallet/balance`, { headers: { Authorization: `Bearer ${token}` } }),
      ])
        .then(([cfg, bal]) => {
          setConfig(cfg)
          setBalances(bal)
          if (format.priceUsdt != null && format.priceUsdt > 0) setCurrency('usdt')
          else if (format.priceStars > 0) setCurrency('stars')
          else setCurrency('ton')
        })
        .catch((e) => {
          console.error('Load payment data:', e)
          setError(t('channel.payment.errorLoad'))
        })
    }
  }, [open, token, format.priceUsdt, format.priceStars, t])

  const priceTon = config && format.priceUsdt != null && format.priceUsdt > 0
    ? format.priceUsdt / config.tonUsdPrice
    : 0

  const options: Array<{ cur: 'stars' | 'usdt' | 'ton'; label: string; amount: number; icon: string; available: number }> = []
  if (format.priceStars > 0 && balances) {
    options.push({
      cur: 'stars',
      label: `${format.priceStars} Stars`,
      amount: format.priceStars,
      icon: starsIcon,
      available: balances.stars,
    })
  }
  if (format.priceUsdt != null && format.priceUsdt > 0 && balances) {
    options.push({
      cur: 'usdt',
      label: `${format.priceUsdt} USDT`,
      amount: format.priceUsdt,
      icon: usdtIcon,
      available: balances.usdt,
    })
  }
  if (format.priceUsdt != null && format.priceUsdt > 0 && config && balances) {
    options.push({
      cur: 'ton',
      label: `${priceTon.toFixed(2)} TON`,
      amount: priceTon,
      icon: tonIcon,
      available: balances.ton,
    })
  }

  const canPay = options.some((o) => o.cur === currency) && (() => {
    const opt = options.find((o) => o.cur === currency)
    return opt ? opt.available >= opt.amount : false
  })()

  const handlePay = async () => {
    if (!token || !canPay) return
    const base = getApiBase()
    setLoading(true)
    setError(null)
    try {
      const res = await postJson<{ writePostLink?: string }>(
        `${base}/api/orders`,
        { channelId, formatId: format.id, currency },
        { headers: { Authorization: `Bearer ${token}` } }
      )
      onSuccess(res.writePostLink ?? '')
      onClose()
    } catch (e) {
      console.error('Create order:', e)
      if (e instanceof ApiError && e.bodyText) {
        try {
          const d = JSON.parse(e.bodyText) as { detail?: string }
          setError(typeof d.detail === 'string' ? d.detail : t('channel.payment.error'))
        } catch {
          setError(t('channel.payment.error'))
        }
      } else {
        setError(t('channel.payment.error'))
      }
    } finally {
      setLoading(false)
    }
  }

  if (options.length === 0) {
    return (
      <Dialog open={open} onClose={onClose} PaperProps={{ sx: { borderRadius: 3, m: 2 } }}>
        <DialogTitle>{t('channel.payment.title')}</DialogTitle>
        <DialogContent>
          <Typography color="text.secondary">{t('channel.payment.noPrice')}</Typography>
        </DialogContent>
      </Dialog>
    )
  }

  return (
    <Dialog open={open} onClose={onClose} PaperProps={{ sx: { borderRadius: 3, m: 2 } }}>
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', pr: 6 }}>
        {t('channel.payment.title')}
        <IconButton onClick={onClose} size="small"><CloseRoundedIcon /></IconButton>
      </DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          {t('channel.payment.description')}
        </Typography>
        {error && (
          <Typography color="error" sx={{ mb: 2 }}>{error}</Typography>
        )}
        <RadioGroup value={currency} onChange={(e) => setCurrency(e.target.value as 'stars' | 'usdt' | 'ton')}>
          {options.map((opt) => (
            <FormControlLabel
              key={opt.cur}
              value={opt.cur}
              control={<Radio />}
              label={
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Box component="img" src={opt.icon} alt="" sx={{ width: 20, height: 20, borderRadius: '50%' }} />
                  <Typography fontWeight={600}>{opt.label}</Typography>
                  <Typography variant="caption" color={opt.available >= opt.amount ? 'success.main' : 'error.main'}>
                    {t('channel.payment.available', { val: opt.available.toFixed(2) })}
                  </Typography>
                </Box>
              }
            />
          ))}
        </RadioGroup>
        <Box sx={{ mt: 2, display: 'flex', gap: 1, justifyContent: 'flex-end' }}>
          <Button variant="outlined" onClick={onClose}>{t('common.cancel')}</Button>
          <Button variant="contained" onClick={() => void handlePay()} disabled={!canPay || loading}>
            {loading ? t('channel.payment.processing') : t('channel.payment.pay')}
          </Button>
        </Box>
      </DialogContent>
    </Dialog>
  )
}
