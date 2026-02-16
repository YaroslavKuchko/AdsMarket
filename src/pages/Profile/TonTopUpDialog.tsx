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
import { tonIcon } from '../../shared/assets/icons'
import logoPng from '../../shared/assets/logo.png'

type TonTopUpDialogProps = {
  open: boolean
  onClose: () => void
  onSuccess?: () => void
}

export function TonTopUpDialog({ open, onClose, onSuccess: _onSuccess }: TonTopUpDialogProps) {
  const { t } = useTranslation()
  const { token } = useAuth()
  const { webApp } = useTelegram()
  const [depositAddress, setDepositAddress] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (open && token) {
      setError(null)
      setLoading(true)
      getJson<{ depositAddress: string; instruction?: string }>(
        `${getApiBase()}/api/wallet/ton-deposit-info`,
        { headers: { Authorization: `Bearer ${token}` } }
      )
        .then((data) => {
          setDepositAddress(data.depositAddress || '')
        })
        .catch((e) => {
          console.error('TON deposit info:', e)
          const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
          setError(msg || t('profile.tonTopUp.error'))
        })
        .finally(() => setLoading(false))
    }
  }, [open, token, t])

  const copyAddress = () => {
    navigator.clipboard.writeText(depositAddress).then(() => {
      setCopied(true)
      webApp?.HapticFeedback?.notificationOccurred?.('success')
      setTimeout(() => setCopied(false), 1500)
    })
  }

  return (
    <Dialog open={open} onClose={onClose} PaperProps={{ sx: { borderRadius: 3, m: 2 } }}>
      <DialogTitle sx={{ fontWeight: 800, display: 'flex', alignItems: 'center', justifyContent: 'space-between', position: 'relative', pr: 6 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Box component="img" src={tonIcon} alt="" sx={{ width: 24, height: 24, borderRadius: '50%' }} />
          {t('profile.tonTopUp.title')}
        </Box>
        <IconButton onClick={onClose} size="small" sx={{ position: 'absolute', top: 12, right: 8 }}>
          <CloseRoundedIcon fontSize="small" />
        </IconButton>
      </DialogTitle>
      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          {t('profile.tonTopUp.description')}
        </Typography>

        {error && (
          <Typography variant="body2" color="error" sx={{ mb: 2 }}>
            {error}
          </Typography>
        )}

        {loading ? (
          <Typography variant="body2" color="text.secondary">{t('profile.tonTopUp.loading')}</Typography>
        ) : depositAddress ? (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            <Box sx={{ display: 'flex', justifyContent: 'center', mb: 2 }}>
              <Box
                sx={{
                  p: 2,
                  borderRadius: 3,
                  background: 'linear-gradient(145deg, #e0f2fe 0%, #bae6fd 100%)',
                  boxShadow: '0 4px 20px rgba(0,152,234,0.15)',
                  border: '1px solid rgba(0,152,234,0.3)',
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <Box sx={{ p: 1.5, bgcolor: 'white', borderRadius: 2, boxShadow: '0 2px 12px rgba(0,0,0,0.06)' }}>
                  <QRCodeSVG
                    value={`ton://transfer/${depositAddress}`}
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
                {t('profile.tonTopUp.addressLabel')}
              </Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                <TextField
                  fullWidth
                  size="small"
                  value={depositAddress}
                  InputProps={{ readOnly: true, sx: { fontFamily: 'monospace', fontSize: 12 } }}
                />
                <IconButton onClick={copyAddress} size="small">
                  <ContentCopyRoundedIcon fontSize="small" />
                </IconButton>
              </Box>
              {copied && (
                <Typography variant="caption" color="success.main">{t('profile.tonTopUp.copied')}</Typography>
              )}
            </Box>
          </Box>
        ) : null}
      </DialogContent>
    </Dialog>
  )
}
