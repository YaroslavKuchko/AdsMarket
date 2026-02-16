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
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../../app/providers/AuthProvider'
import { useTelegram } from '../../app/providers/TelegramProvider'
import { Button } from '../../shared/ui/Button'
import { getApiBase } from '../../shared/utils/apiBase'
import { postJson } from '../../shared/utils/api'
import { tonIcon } from '../../shared/assets/icons'

const WITHDRAW_FEE = 0.15
const MIN_WITHDRAW = 0.1

type TonWithdrawDialogProps = {
  open: boolean
  onClose: () => void
  onSuccess?: () => void
  tonBalance: number
}

export function TonWithdrawDialog({
  open,
  onClose,
  onSuccess,
  tonBalance,
}: TonWithdrawDialogProps) {
  const { t } = useTranslation()
  const { token } = useAuth()
  const { webApp } = useTelegram()
  const [amount, setAmount] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [submitted, setSubmitted] = useState(false)

  useEffect(() => {
    if (open && token) {
      setError(null)
      setSubmitted(false)
      setAmount('')
    }
  }, [open, token])

  const numAmount = parseFloat(amount.replace(',', '.')) || 0
  const netAmount = numAmount > 0 ? Math.max(0, numAmount - WITHDRAW_FEE) : 0

  const handleSubmit = async () => {
    if (!token) return
    const num = parseFloat(amount.replace(',', '.'))
    if (Number.isNaN(num) || num < MIN_WITHDRAW) {
      setError(t('profile.tonWithdraw.invalidAmount'))
      return
    }
    if (num > tonBalance) {
      setError(t('profile.tonWithdraw.insufficient'))
      return
    }

    setLoading(true)
    setError(null)
    try {
      await postJson(
        `${getApiBase()}/api/wallet/ton-withdraw`,
        { amount: num },
        { headers: { Authorization: `Bearer ${token}` } }
      )
      webApp?.HapticFeedback?.notificationOccurred?.('success')
      setSubmitted(true)
      onSuccess?.()
      setTimeout(() => onClose(), 2500)
    } catch (e: unknown) {
      console.error('TON withdraw:', e)
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail || ''
      setError(msg?.toLowerCase().includes('кошелёк') || msg?.toLowerCase().includes('wallet')
        ? t('profile.tonWithdraw.connectWalletRequired')
        : t('profile.tonWithdraw.error'))
      webApp?.HapticFeedback?.notificationOccurred?.('error')
    } finally {
      setLoading(false)
    }
  }

  const setAllBalance = () => {
    setAmount(Math.max(0, tonBalance).toFixed(2))
  }

  const inputSx = {
    '& .MuiOutlinedInput-root': {
      '&.Mui-focused .MuiOutlinedInput-notchedOutline': { borderColor: 'primary.main' },
      '&:hover .MuiOutlinedInput-notchedOutline': { borderColor: 'primary.main' },
    },
  }

  return (
    <Dialog open={open} onClose={onClose} PaperProps={{ sx: { borderRadius: 3, m: 2 } }}>
      <DialogTitle sx={{ fontWeight: 800, display: 'flex', alignItems: 'center', justifyContent: 'space-between', position: 'relative', pr: 6 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box component="img" src={tonIcon} alt="" sx={{ width: 24, height: 24, borderRadius: '50%' }} />
          {t('profile.tonWithdraw.title')}
        </Box>
        <IconButton onClick={onClose} size="small" sx={{ position: 'absolute', top: 12, right: 8 }}>
          <CloseRoundedIcon fontSize="small" />
        </IconButton>
      </DialogTitle>
      <DialogContent>
        {submitted ? (
          <Typography variant="body1" color="success.main" sx={{ py: 3, textAlign: 'center', fontWeight: 600 }}>
            {t('profile.tonWithdraw.submitted')}
          </Typography>
        ) : (
          <>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {t('profile.tonWithdraw.description')}
            </Typography>

            {error && (
              <Typography variant="body2" color="error" sx={{ mb: 2 }}>
                {error}
              </Typography>
            )}

            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <Box>
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                  {t('profile.tonWithdraw.amountLabel')}
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
                          {t('profile.tonWithdraw.allBalance')}
                        </Button>
                      </InputAdornment>
                    ),
                  }}
                />
                <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mt: 0.5 }}>
                  <Typography variant="caption" color="text.secondary">
                    {t('profile.tonWithdraw.balance', { balance: tonBalance.toFixed(2) })}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {t('profile.tonWithdraw.feeLabel')}
                  </Typography>
                </Box>
              </Box>

              {numAmount >= MIN_WITHDRAW && (
                <Typography variant="body2" color="text.secondary">
                  {t('profile.tonWithdraw.netAmount', {
                    gross: numAmount.toFixed(2),
                    net: netAmount.toFixed(2),
                    fee: WITHDRAW_FEE.toFixed(2),
                  })}
                </Typography>
              )}

              <Typography variant="caption" color="text.secondary" sx={{ mt: 0.5 }}>
                {t('profile.tonWithdraw.toConnectedWallet')}
              </Typography>
            </Box>
          </>
        )}
      </DialogContent>
      {!submitted && (
        <DialogActions sx={{ p: 2, pt: 0 }}>
          <Button variant="outlined" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button variant="contained" onClick={() => void handleSubmit()} disabled={loading || submitted}>
            {loading ? t('profile.tonWithdraw.processing') : t('profile.wallet.withdraw')}
          </Button>
        </DialogActions>
      )}
    </Dialog>
  )
}
