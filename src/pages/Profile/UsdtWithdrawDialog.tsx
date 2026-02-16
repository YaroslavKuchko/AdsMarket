import {
  Box,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  IconButton,
  InputAdornment,
  TextField,
  Typography,
} from '@mui/material'
import CloseRoundedIcon from '@mui/icons-material/CloseRounded'
import ContentPasteRoundedIcon from '@mui/icons-material/ContentPasteRounded'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../../app/providers/AuthProvider'
import { useTelegram } from '../../app/providers/TelegramProvider'
import { Button } from '../../shared/ui/Button'
import { getApiBase } from '../../shared/utils/apiBase'
import { postJson } from '../../shared/utils/api'
import { usdtIcon } from '../../shared/assets/icons'

const WITHDRAW_FEE = 0.3
const MIN_WITHDRAW = 10

type UsdtWithdrawDialogProps = {
  open: boolean
  onClose: () => void
  onSuccess?: () => void
  usdtBalance: number
}

export function UsdtWithdrawDialog({
  open,
  onClose,
  onSuccess,
  usdtBalance,
}: UsdtWithdrawDialogProps) {
  const { t } = useTranslation()
  const { token } = useAuth()
  const { webApp } = useTelegram()
  const [amount, setAmount] = useState('')
  const [address, setAddress] = useState('')
  const [memo, setMemo] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [submitted, setSubmitted] = useState(false)

  useEffect(() => {
    if (open && token) {
      setError(null)
      setSubmitted(false)
      setAmount('')
      setAddress('')
      setMemo('')
    }
  }, [open, token])

  const numAmount = parseFloat(amount.replace(',', '.')) || 0
  const netAmount = numAmount > 0 ? Math.max(0, numAmount - WITHDRAW_FEE) : 0

  const handleSubmit = async () => {
    if (!token) return
    const num = parseFloat(amount.replace(',', '.'))
    if (Number.isNaN(num) || num < MIN_WITHDRAW) {
      setError(t('profile.usdtWithdraw.invalidAmount'))
      return
    }
    if (num > usdtBalance) {
      setError(t('profile.usdtWithdraw.insufficient'))
      return
    }
    const trimmedAddress = address.trim()
    if (!trimmedAddress || trimmedAddress.length < 40) {
      setError(t('profile.usdtWithdraw.invalidAddress'))
      return
    }

    setLoading(true)
    setError(null)
    try {
      await postJson(
        `${getApiBase()}/api/wallet/usdt-withdraw`,
        {
          amount: num,
          address: trimmedAddress,
          memo: memo.trim() || undefined,
        },
        { headers: { Authorization: `Bearer ${token}` } }
      )
      webApp?.HapticFeedback?.notificationOccurred?.('success')
      setSubmitted(true)
      onSuccess?.()
      setTimeout(() => {
        onClose()
      }, 2500)
    } catch (e) {
      console.error('USDT withdraw:', e)
      setError(t('profile.usdtWithdraw.error'))
      webApp?.HapticFeedback?.notificationOccurred?.('error')
    } finally {
      setLoading(false)
    }
  }

  const setAllBalance = () => {
    setAmount(Math.max(0, usdtBalance).toFixed(2))
  }

  const pasteFromClipboard = async (target: 'address' | 'memo') => {
    try {
      const text = await navigator.clipboard.readText()
      if (target === 'address') setAddress(text)
      else setMemo(text)
      webApp?.HapticFeedback?.notificationOccurred?.('success')
    } catch {
      webApp?.HapticFeedback?.notificationOccurred?.('error')
    }
  }

  const inputSx = {
    '& .MuiOutlinedInput-root': {
      '&.Mui-focused .MuiOutlinedInput-notchedOutline': { borderColor: 'primary.main' },
      '&:hover .MuiOutlinedInput-notchedOutline': { borderColor: 'primary.main' },
    },
  }
  const pasteIconSx = { color: 'primary.main' }

  return (
    <Dialog open={open} onClose={onClose} PaperProps={{ sx: { borderRadius: 3, m: 2 } }}>
      <DialogTitle sx={{ fontWeight: 800, display: 'flex', alignItems: 'center', justifyContent: 'space-between', position: 'relative', pr: 6 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box component="img" src={usdtIcon} alt="" sx={{ width: 24, height: 24, borderRadius: '50%' }} />
          {t('profile.usdtWithdraw.title')}
        </Box>
        <IconButton onClick={onClose} size="small" sx={{ position: 'absolute', top: 12, right: 8 }}>
          <CloseRoundedIcon fontSize="small" />
        </IconButton>
      </DialogTitle>
      <DialogContent>
        {submitted ? (
          <Typography variant="body1" color="success.main" sx={{ py: 3, textAlign: 'center', fontWeight: 600 }}>
            {t('profile.usdtWithdraw.submitted')}
          </Typography>
        ) : (
          <>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          {t('profile.usdtWithdraw.description')}
        </Typography>

        {error && (
          <Typography variant="body2" color="error" sx={{ mb: 2 }}>
            {error}
          </Typography>
        )}

        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <Box>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
              {t('profile.usdtWithdraw.amountLabel')}
            </Typography>
            <TextField
              fullWidth
              size="small"
              value={amount}
              onChange={(e) => setAmount(e.target.value.replace(/[^\d.,]/g, ''))}
              placeholder="0.00"
              inputProps={{ inputMode: 'decimal' }}
              sx={inputSx}
              InputProps={{
                endAdornment: (
                  <InputAdornment position="end">
                    <Button variant="text" size="small" onClick={setAllBalance} sx={{ minWidth: 0, px: 1 }}>
                      {t('profile.usdtWithdraw.allBalance')}
                    </Button>
                  </InputAdornment>
                ),
              }}
            />
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mt: 0.5 }}>
              <Typography variant="caption" color="text.secondary">
                {t('profile.usdtWithdraw.balance', { balance: usdtBalance.toFixed(2) })}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {t('profile.usdtWithdraw.feeLabel')}
              </Typography>
            </Box>
          </Box>

          {numAmount >= MIN_WITHDRAW && (
            <Typography variant="body2" color="text.secondary">
              {t('profile.usdtWithdraw.netAmount', {
                gross: numAmount.toFixed(2),
                net: netAmount.toFixed(2),
                fee: WITHDRAW_FEE.toFixed(1),
              })}
            </Typography>
          )}

          <Box>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
              {t('profile.usdtWithdraw.addressLabel')}
            </Typography>
            <TextField
              fullWidth
              size="small"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              placeholder="UQ..."
              sx={inputSx}
              inputProps={{ style: { fontFamily: 'monospace', fontSize: 12 } }}
              InputProps={{
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton onClick={() => pasteFromClipboard('address')} size="small" sx={pasteIconSx} aria-label={t('profile.usdtWithdraw.paste')}>
                      <ContentPasteRoundedIcon fontSize="small" />
                    </IconButton>
                  </InputAdornment>
                ),
              }}
            />
          </Box>

          <Box>
            <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
              {t('profile.usdtWithdraw.memoLabel')}
            </Typography>
            <TextField
              fullWidth
              size="small"
              value={memo}
              onChange={(e) => setMemo(e.target.value)}
              placeholder={t('profile.usdtWithdraw.memoPlaceholder')}
              sx={inputSx}
              InputProps={{
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton onClick={() => pasteFromClipboard('memo')} size="small" sx={pasteIconSx} aria-label={t('profile.usdtWithdraw.paste')}>
                      <ContentPasteRoundedIcon fontSize="small" />
                    </IconButton>
                  </InputAdornment>
                ),
              }}
            />
          </Box>
        </Box>
          </>
        )}
      </DialogContent>
      {!submitted && (
      <DialogActions sx={{ p: 2, pt: 0 }}>
        <Button variant="outlined" onClick={onClose}>
          {t('common.cancel')}
        </Button>
        <Button
          variant="contained"
          onClick={() => void handleSubmit()}
          disabled={loading || submitted}
        >
          {loading ? t('profile.usdtWithdraw.processing') : t('profile.wallet.withdraw')}
        </Button>
      </DialogActions>
      )}
    </Dialog>
  )
}
