import AddCircleRoundedIcon from '@mui/icons-material/AddCircleRounded'
import AdminPanelSettingsRoundedIcon from '@mui/icons-material/AdminPanelSettingsRounded'
import CloseRoundedIcon from '@mui/icons-material/CloseRounded'
import ContentCopyRoundedIcon from '@mui/icons-material/ContentCopyRounded'
import OpenInNewRoundedIcon from '@mui/icons-material/OpenInNewRounded'
import {
  Box,
  Dialog,
  DialogContent,
  DialogTitle,
  IconButton,
  Typography,
} from '@mui/material'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useTelegram } from '../../app/providers/TelegramProvider'
import { Button } from '../../shared/ui/Button'
import { getJson } from '../../shared/utils/api'
import { getApiBase } from '../../shared/utils/apiBase'

type AddChannelDialogProps = {
  open: boolean
  onClose: () => void
  onChannelAdded?: () => void
}

export function AddChannelDialog({ open, onClose }: AddChannelDialogProps) {
  const { t } = useTranslation()
  const { webApp } = useTelegram()
  const [copied, setCopied] = useState(false)
  const [botUsername, setBotUsername] = useState<string>('')

  useEffect(() => {
    if (!open) return
    const base = getApiBase()
    getJson<{ botUsername: string }>(`${base}/api/config`)
      .then((c) => setBotUsername(c.botUsername))
      .catch(() => setBotUsername(''))
  }, [open])

  const handleCopyUsername = async () => {
    if (!botUsername) return
    try {
      await navigator.clipboard.writeText(`@${botUsername}`)
      setCopied(true)
      webApp?.HapticFeedback?.notificationOccurred?.('success')
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Fallback
      const textArea = document.createElement('textarea')
      textArea.value = `@${botUsername}`
      document.body.appendChild(textArea)
      textArea.select()
      document.execCommand('copy')
      document.body.removeChild(textArea)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  const handleOpenBot = () => {
    if (!botUsername) return
    const url = `https://t.me/${botUsername}`
    if (webApp?.openTelegramLink) {
      webApp.openTelegramLink(url)
    } else {
      window.open(url, '_blank', 'noreferrer')
    }
  }

  const handleAddBotToChannel = () => {
    if (!botUsername) return
    const adminRights = 'change_info+post_messages+edit_messages+delete_messages+pin_messages'
    const url = `https://t.me/${botUsername}?startchannel&admin=${adminRights}`
    if (webApp?.openTelegramLink) {
      webApp.openTelegramLink(url)
    } else {
      window.open(url, '_blank', 'noreferrer')
    }
    webApp?.HapticFeedback?.notificationOccurred?.('success')
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="xs"
      fullWidth
      PaperProps={{
        sx: {
          borderRadius: 3,
          m: 2,
        },
      }}
    >
      <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', pb: 1 }}>
        <Typography sx={{ fontWeight: 800 }}>{t('myChannels.addDialog.title')}</Typography>
        <IconButton size="small" onClick={onClose}>
          <CloseRoundedIcon fontSize="small" />
        </IconButton>
      </DialogTitle>

      <DialogContent>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          {t('myChannels.addDialog.description')}
        </Typography>

        {/* Primary action - Add bot to channel button */}
        <Button
          fullWidth
          variant="contained"
          startIcon={<AddCircleRoundedIcon />}
          onClick={handleAddBotToChannel}
          disabled={!botUsername}
          sx={{ py: 1.5, mb: 3 }}
        >
          {t('myChannels.addDialog.addBotToChannel')}
        </Button>

        {/* Or manual instruction */}
        <Typography variant="body2" sx={{ fontWeight: 600, mb: 2 }}>
          {t('myChannels.addDialog.orManual')}
        </Typography>

        {/* Steps */}
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mb: 3 }}>
          {/* Step 1 */}
          <Box sx={{ display: 'flex', gap: 1.5 }}>
            <Box
              sx={{
                width: 28,
                height: 28,
                borderRadius: '50%',
                bgcolor: 'primary.main',
                color: 'primary.contrastText',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 13,
                fontWeight: 700,
                flexShrink: 0,
              }}
            >
              1
            </Box>
            <Box sx={{ flex: 1 }}>
              <Typography variant="body2" sx={{ fontWeight: 600 }}>
                {t('myChannels.addDialog.step1.title')}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {t('myChannels.addDialog.step1.description')}
              </Typography>
            </Box>
          </Box>

          {/* Step 2 */}
          <Box sx={{ display: 'flex', gap: 1.5 }}>
            <Box
              sx={{
                width: 28,
                height: 28,
                borderRadius: '50%',
                bgcolor: 'primary.main',
                color: 'primary.contrastText',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 13,
                fontWeight: 700,
                flexShrink: 0,
              }}
            >
              2
            </Box>
            <Box sx={{ flex: 1 }}>
              <Typography variant="body2" sx={{ fontWeight: 600 }}>
                {t('myChannels.addDialog.step2.title')}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {t('myChannels.addDialog.step2.description')}
              </Typography>
            </Box>
          </Box>

          {/* Step 3 */}
          <Box sx={{ display: 'flex', gap: 1.5 }}>
            <Box
              sx={{
                width: 28,
                height: 28,
                borderRadius: '50%',
                bgcolor: 'primary.main',
                color: 'primary.contrastText',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 13,
                fontWeight: 700,
                flexShrink: 0,
              }}
            >
              3
            </Box>
            <Box sx={{ flex: 1 }}>
              <Typography variant="body2" sx={{ fontWeight: 600 }}>
                {t('myChannels.addDialog.step3.title')}
              </Typography>
              <Typography variant="caption" color="text.secondary">
                {t('myChannels.addDialog.step3.description')}
              </Typography>
            </Box>
          </Box>
        </Box>

        {/* Bot username */}
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1,
            p: 1.5,
            bgcolor: 'action.hover',
            borderRadius: 2,
            mb: 2,
          }}
        >
          <AdminPanelSettingsRoundedIcon sx={{ color: 'primary.main' }} />
          <Typography sx={{ flex: 1, fontFamily: 'monospace', fontWeight: 600 }}>
            @{botUsername || '…'}
          </Typography>
          <IconButton
            size="small"
            onClick={handleCopyUsername}
            color={copied ? 'success' : 'default'}
            disabled={!botUsername}
          >
            <ContentCopyRoundedIcon sx={{ fontSize: 18 }} />
          </IconButton>
        </Box>

        {/* Open bot (for manual method) */}
        <Button
          fullWidth
          variant="outlined"
          startIcon={<OpenInNewRoundedIcon />}
          onClick={handleOpenBot}
          disabled={!botUsername}
        >
          {t('myChannels.addDialog.openBot')}
        </Button>

        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ display: 'block', textAlign: 'center', mt: 2 }}
        >
          {t('myChannels.addDialog.hint')}
        </Typography>
      </DialogContent>
    </Dialog>
  )
}

