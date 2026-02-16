import CloseRoundedIcon from '@mui/icons-material/CloseRounded'
import ContentCopyRoundedIcon from '@mui/icons-material/ContentCopyRounded'
import {
  Box,
  Dialog,
  DialogContent,
  DialogTitle,
  IconButton,
  TextField,
  Typography,
} from '@mui/material'
import { useEffect, useState } from 'react'
import { QRCodeSVG } from 'qrcode.react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../../app/providers/AuthProvider'
import { useTelegram } from '../../app/providers/TelegramProvider'
import { getApiBase } from '../../shared/utils/apiBase'
import { getJson } from '../../shared/utils/api'
import { usdtIcon } from '../../shared/assets/icons'
import logoPng from '../../shared/assets/logo.png'

type UsdtTopUpDialogProps = {
  open: boolean
  onClose: () => void
  onSuccess?: () => void
}

export function UsdtTopUpDialog({ open, onClose, onSuccess: _onSuccess }: UsdtTopUpDialogProps) {
  const { t } = useTranslation()
  const { token } = useAuth()
  const { webApp } = useTelegram()
  const [depositAddress, setDepositAddress] = useState('')
  const [memo, setMemo] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState<'address' | 'memo' | null>(null)

  useEffect(() => {
    if (open && token) {
      setError(null)
      setLoading(true)
      getJson<{ depositAddress: string; memo: string }>(
        `${getApiBase()}/api/wallet/usdt-deposit-info`,
        { headers: { Authorization: `Bearer ${token}` } }
      )
        .then((data) => {
          setDepositAddress(data.depositAddress || '')
          setMemo(data.memo || '')
        })
        .catch((e) => {
          console.error('USDT deposit info:', e)
          setError(t('profile.usdtTopUp.error'))
        })
        .finally(() => setLoading(false))
    }
  }, [open, token, t])

  const copy = (value: string, key: 'address' | 'memo') => {
    navigator.clipboard.writeText(value).then(() => {
      setCopied(key)
      webApp?.HapticFeedback?.notificationOccurred?.('success')
      setTimeout(() => setCopied(null), 1500)
    })
  }

  return (
    <Dialog open={open} onClose={onClose} PaperProps={{ sx: { borderRadius: 3, m: 2 } }}>
      <DialogTitle sx={{ fontWeight: 800, display: 'flex', alignItems: 'center', justifyContent: 'space-between', position: 'relative', pr: 6 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box component="img" src={usdtIcon} alt="" sx={{ width: 24, height: 24, borderRadius: '50%' }} />
          {t('profile.usdtTopUp.title')}
        </Box>
        <IconButton onClick={onClose} size="small" sx={{ position: 'absolute', top: 12, right: 8 }}>
          <CloseRoundedIcon fontSize="small" />
        </IconButton>
      </DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          {t('profile.usdtTopUp.description')}
        </Typography>

        {error && (
          <Typography variant="body2" color="error" sx={{ mb: 2 }}>
            {error}
          </Typography>
        )}

        {loading ? (
          <Typography variant="body2" color="text.secondary">{t('profile.usdtTopUp.loading')}</Typography>
        ) : depositAddress ? (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {/* QR code with logo — styled container */}
            <Box sx={{ display: 'flex', justifyContent: 'center', mb: 2 }}>
              <Box
                sx={{
                  p: 2,
                  borderRadius: 3,
                  background: 'linear-gradient(145deg, #f8fafc 0%, #f1f5f9 100%)',
                  boxShadow: '0 4px 20px rgba(0,0,0,0.08), inset 0 1px 0 rgba(255,255,255,0.9)',
                  border: '1px solid rgba(34,197,94,0.25)',
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <Box
                  sx={{
                    p: 1.5,
                    bgcolor: 'white',
                    borderRadius: 2,
                    boxShadow: '0 2px 12px rgba(0,0,0,0.06)',
                  }}
                >
                  <QRCodeSVG
                    value={
                      memo
                        ? `ton://transfer/${depositAddress}?text=${encodeURIComponent(memo)}`
                        : `ton://transfer/${depositAddress}`
                    }
                    size={220}
                    level="H"
                    includeMargin={false}
                    imageSettings={{
                      src: logoPng,
                      height: 52,
                      width: 52,
                      excavate: true,
                    }}
                  />
                </Box>
              </Box>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                {t('profile.usdtTopUp.addressLabel')}
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <TextField
                  fullWidth
                  size="small"
                  value={depositAddress}
                  InputProps={{ readOnly: true, sx: { fontFamily: 'monospace', fontSize: 12 } }}
                />
                <IconButton onClick={() => copy(depositAddress, 'address')} size="small">
                  <ContentCopyRoundedIcon fontSize="small" />
                </IconButton>
              </Box>
              {copied === 'address' && (
                <Typography variant="caption" color="success.main">{t('profile.usdtTopUp.copied')}</Typography>
              )}
            </Box>

            <Box>
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
                {t('profile.usdtTopUp.memoLabel')}
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <TextField
                  fullWidth
                  size="small"
                  value={memo}
                  InputProps={{ readOnly: true, sx: { fontFamily: 'monospace', fontWeight: 700 } }}
                />
                <IconButton onClick={() => copy(memo, 'memo')} size="small">
                  <ContentCopyRoundedIcon fontSize="small" />
                </IconButton>
              </Box>
              {copied === 'memo' && (
                <Typography variant="caption" color="success.main">{t('profile.usdtTopUp.copied')}</Typography>
              )}
            </Box>
          </Box>
        ) : null}
      </DialogContent>
    </Dialog>
  )
}
