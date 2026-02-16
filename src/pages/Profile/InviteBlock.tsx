import GroupAddRoundedIcon from '@mui/icons-material/GroupAddRounded'
import InfoOutlinedIcon from '@mui/icons-material/InfoOutlined'
import CloseRoundedIcon from '@mui/icons-material/CloseRounded'
import ContentCopyRoundedIcon from '@mui/icons-material/ContentCopyRounded'
import ShareRoundedIcon from '@mui/icons-material/ShareRounded'
import CardGiftcardRoundedIcon from '@mui/icons-material/CardGiftcardRounded'
import ChevronRightRoundedIcon from '@mui/icons-material/ChevronRightRounded'
import {
  Box,
  ButtonBase,
  CircularProgress,
  Dialog,
  DialogContent,
  DialogTitle,
  IconButton,
  Skeleton,
  Typography,
} from '@mui/material'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../../app/providers/AuthProvider'
import { useTelegram } from '../../app/providers/TelegramProvider'
import { Card } from '../../shared/ui/Card'
import { Button } from '../../shared/ui/Button'
import { getJson } from '../../shared/utils/api'
import { getApiBase } from '../../shared/utils/apiBase'

type ReferralLinkResponse = {
  referralCode: string
  referralLink: string
  webappUrl: string
}

type ReferralStatsResponse = {
  totalReferrals: number
  activeReferrals: number
  earnings: { stars: number; ton: number; usdt: number }
  pending: { stars: number; ton: number; usdt: number }
  referralCode: string
  referralLink: string
}

export function InviteBlock() {
  const { t } = useTranslation()
  const { token } = useAuth()
  const { webApp } = useTelegram()

  const [infoOpen, setInfoOpen] = useState(false)
  const [referralLink, setReferralLink] = useState<string | null>(null)
  const [stats, setStats] = useState<ReferralStatsResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [copied, setCopied] = useState(false)

  // Fetch referral link on mount
  useEffect(() => {
    if (!token) return

    const fetchReferralLink = async () => {
      setLoading(true)
      try {
        const base = getApiBase()
        const data = await getJson<ReferralLinkResponse>(`${base}/api/referral/link`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        setReferralLink(data.referralLink)

        // Also fetch stats
        const statsData = await getJson<ReferralStatsResponse>(`${base}/api/referral/stats`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        setStats(statsData)
      } catch (e) {
        console.error('Failed to fetch referral link:', e)
      } finally {
        setLoading(false)
      }
    }

    void fetchReferralLink()
  }, [token])

  const handleCopy = async () => {
    if (!referralLink) return
    try {
      await navigator.clipboard.writeText(referralLink)
      setCopied(true)
      webApp?.HapticFeedback?.notificationOccurred?.('success')
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Fallback for older browsers
      const textArea = document.createElement('textarea')
      textArea.value = referralLink
      document.body.appendChild(textArea)
      textArea.select()
      document.execCommand('copy')
      document.body.removeChild(textArea)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  const handleShare = () => {
    if (!referralLink) return

    const shareText = t('profile.invite.shareText')
    const shareUrl = `https://t.me/share/url?url=${encodeURIComponent(referralLink)}&text=${encodeURIComponent(shareText)}`

    if (webApp?.openTelegramLink) {
      webApp.openTelegramLink(shareUrl)
    } else if (webApp?.openLink) {
      webApp.openLink(shareUrl)
    } else {
      window.open(shareUrl, '_blank', 'noreferrer')
    }
  }

  const handleBonusClick = () => {
    setInfoOpen(false)
    handleShare()
  }

  return (
    <>
      <Card>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.25 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
            <GroupAddRoundedIcon sx={{ fontSize: 20, color: 'primary.main' }} />
            <Typography sx={{ fontWeight: 900 }}>{t('profile.invite.title')}</Typography>
          </Box>
          <IconButton
            size="small"
            onClick={() => setInfoOpen(true)}
            sx={{ color: 'text.secondary' }}
          >
            <InfoOutlinedIcon sx={{ fontSize: 20 }} />
          </IconButton>
        </Box>

        {/* Stats */}
        {stats && stats.totalReferrals > 0 && (
          <Box
            sx={{
              display: 'flex',
              gap: 2,
              mb: 1.25,
              p: 1,
              bgcolor: 'action.hover',
              borderRadius: 1.5,
            }}
          >
            <Box sx={{ textAlign: 'center', flex: 1 }}>
              <Typography sx={{ fontWeight: 900, fontSize: 18 }}>{stats.totalReferrals}</Typography>
              <Typography variant="caption" color="text.secondary">
                {t('profile.invite.referrals')}
              </Typography>
            </Box>
            <Box sx={{ textAlign: 'center', flex: 1 }}>
              <Typography sx={{ fontWeight: 900, fontSize: 18 }}>{stats.activeReferrals}</Typography>
              <Typography variant="caption" color="text.secondary">
                {t('profile.invite.active')}
              </Typography>
            </Box>
          </Box>
        )}

        {/* Referral Link */}
        {loading ? (
          <Skeleton width="100%" height={40} sx={{ mb: 1.25 }} />
        ) : referralLink ? (
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 1,
              p: 1,
              mb: 1.25,
              bgcolor: 'action.hover',
              borderRadius: 1.5,
              overflow: 'hidden',
            }}
          >
            <Typography
              variant="body2"
              sx={{
                flex: 1,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                fontFamily: 'monospace',
                fontSize: 12,
              }}
            >
              {referralLink}
            </Typography>
            <IconButton size="small" onClick={handleCopy} color={copied ? 'success' : 'default'}>
              <ContentCopyRoundedIcon sx={{ fontSize: 18 }} />
            </IconButton>
          </Box>
        ) : (
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1.25 }}>
            {t('profile.invite.subtitle')}
          </Typography>
        )}

        {/* Buttons */}
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button
            variant="contained"
            fullWidth
            onClick={handleShare}
            disabled={!referralLink || loading}
            startIcon={loading ? <CircularProgress size={16} color="inherit" /> : <ShareRoundedIcon />}
          >
            {t('profile.invite.share')}
          </Button>
        </Box>
      </Card>

      {/* Info Dialog */}
      <Dialog
        open={infoOpen}
        onClose={() => setInfoOpen(false)}
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
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <GroupAddRoundedIcon sx={{ color: 'primary.main' }} />
            <Typography sx={{ fontWeight: 800 }}>{t('profile.invite.infoTitle')}</Typography>
          </Box>
          <IconButton size="small" onClick={() => setInfoOpen(false)}>
            <CloseRoundedIcon fontSize="small" />
          </IconButton>
        </DialogTitle>
        <DialogContent>
          {/* Description */}
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {t('profile.invite.infoDescription')}
          </Typography>

          {/* Steps */}
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5, mb: 2 }}>
            {[1, 2, 3].map((step) => (
              <Box key={step} sx={{ display: 'flex', alignItems: 'flex-start', gap: 1.5 }}>
                <Box
                  sx={{
                    width: 24,
                    height: 24,
                    borderRadius: '50%',
                    bgcolor: 'primary.main',
                    color: 'primary.contrastText',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 12,
                    fontWeight: 700,
                    flexShrink: 0,
                  }}
                >
                  {step}
                </Box>
                <Typography variant="body2">
                  {t(`profile.invite.step${step}` as const)}
                </Typography>
              </Box>
            ))}
          </Box>

          {/* Bonus - Clickable */}
          <ButtonBase
            onClick={handleBonusClick}
            disabled={!referralLink}
            sx={{
              width: '100%',
              p: 1.5,
              bgcolor: 'success.main',
              borderRadius: 2,
              color: 'success.contrastText',
              display: 'flex',
              alignItems: 'center',
              gap: 1.5,
              transition: 'transform 0.15s, box-shadow 0.15s',
              '&:hover': {
                transform: 'scale(1.02)',
                boxShadow: 4,
              },
              '&:active': {
                transform: 'scale(0.98)',
              },
            }}
          >
            <CardGiftcardRoundedIcon sx={{ fontSize: 28 }} />
            <Box sx={{ flex: 1, textAlign: 'left' }}>
              <Typography variant="body2" sx={{ fontWeight: 700 }}>
                {t('profile.invite.bonus')}
              </Typography>
              <Typography variant="caption" sx={{ opacity: 0.85 }}>
                {t('profile.invite.bonusTap')}
              </Typography>
            </Box>
            <ChevronRightRoundedIcon />
          </ButtonBase>
        </DialogContent>
      </Dialog>
    </>
  )
}
