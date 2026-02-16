import PersonRoundedIcon from '@mui/icons-material/PersonRounded'
import AlternateEmailRoundedIcon from '@mui/icons-material/AlternateEmailRounded'
import FingerprintRoundedIcon from '@mui/icons-material/FingerprintRounded'
import PhoneIphoneRoundedIcon from '@mui/icons-material/PhoneIphoneRounded'
import VerifiedRoundedIcon from '@mui/icons-material/VerifiedRounded'
import { Avatar, Box, Divider, Skeleton, Tooltip, Typography } from '@mui/material'
import { useTranslation } from 'react-i18next'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTelegram } from '../../app/providers/TelegramProvider'
import { useAuth } from '../../app/providers/AuthProvider'
import { BalanceBlock } from './BalanceBlock'
import { StarsTopUpDialog } from './StarsTopUpDialog'
import { StarsExchangeDialog } from './StarsExchangeDialog'
import { UsdtTopUpDialog } from './UsdtTopUpDialog'
import { UsdtWithdrawDialog } from './UsdtWithdrawDialog'
import { TonTopUpDialog } from './TonTopUpDialog'
import { TonWithdrawDialog } from './TonWithdrawDialog'
import { InviteBlock } from './InviteBlock'
import { Card } from '../../shared/ui/Card'
import { Badge } from '../../shared/ui/Badge'
import { Button } from '../../shared/ui/Button'
import { ProfileSettingsDrawer } from './ProfileSettingsDrawer'
import { ErrorBoundary } from '../../app/ErrorBoundary'
import { sleep } from '../../shared/utils/sleep'
import { getJson } from '../../shared/utils/api'
import { getApiBase } from '../../shared/utils/apiBase'

export function ProfilePage() {
  const { t } = useTranslation()
  const auth = useAuth()
  const {
    user,
    isTelegram,
    isReady,
    requestContact,
    webApp,
  } = useTelegram()

  const [phoneRequested, setPhoneRequested] = useState(false)
  const [phoneLoading, setPhoneLoading] = useState(false)
  const [starsTopUpOpen, setStarsTopUpOpen] = useState(false)
  const [starsExchangeOpen, setStarsExchangeOpen] = useState(false)
  const [usdtTopUpOpen, setUsdtTopUpOpen] = useState(false)
  const [usdtWithdrawOpen, setUsdtWithdrawOpen] = useState(false)
  const [tonTopUpOpen, setTonTopUpOpen] = useState(false)
  const [tonWithdrawOpen, setTonWithdrawOpen] = useState(false)
  const [balances, setBalances] = useState({ stars: 0, ton: 0, usdt: 0 })

  const fetchBalances = useCallback(async () => {
    if (!auth.token) return
    try {
      const data = await getJson<{ stars: number; ton: number; usdt: number }>(
        `${getApiBase()}/api/wallet/balance`,
        { headers: { Authorization: `Bearer ${auth.token}` } }
      )
      setBalances({
        stars: Number(data.stars ?? 0),
        ton: Number(data.ton ?? 0),
        usdt: Number(data.usdt ?? 0),
      })
    } catch (e) {
      console.error('Fetch balances:', e)
    }
  }, [auth.token])

  useEffect(() => {
    void fetchBalances()
  }, [fetchBalances])

  // Poll balance when USDT or TON top-up dialog is open (user waiting for deposit)
  useEffect(() => {
    if ((!usdtTopUpOpen && !tonTopUpOpen) || !auth.token) return
    void fetchBalances() // immediate fetch
    const id = setInterval(() => void fetchBalances(), 12_000) // every 12 sec
    return () => clearInterval(id)
  }, [usdtTopUpOpen, tonTopUpOpen, auth.token, fetchBalances])

  const effectiveUser = auth.user
    ? {
        id: auth.user.telegramId,
        first_name: auth.user.firstName ?? undefined,
        last_name: auth.user.lastName ?? undefined,
        username: auth.user.username ?? undefined,
        photo_url: auth.user.photoUrl ?? undefined,
      }
    : user

  const fullName = useMemo(() => {
    const first = effectiveUser?.first_name?.trim()
    const last = effectiveUser?.last_name?.trim()
    const combined = [last, first].filter(Boolean).join(' ')
    return combined || undefined
  }, [effectiveUser?.first_name, effectiveUser?.last_name])

  const username = effectiveUser?.username ? String(effectiveUser.username) : undefined
  const displayName = fullName ?? username ?? t('profile.guest')

  const canRequestPhone = Boolean(webApp?.requestContact)
  const phoneFromAuth = auth.user?.phoneNumber ?? undefined
  const phoneToShow = phoneFromAuth
  const isVerified = Boolean(phoneToShow)

  const showAlert = (message: string) => {
    webApp?.showAlert?.(message)
  }

  const haptic = (type: 'success' | 'error') => {
    webApp?.HapticFeedback?.notificationOccurred?.(type)
  }

  const handleRequestPhone = async () => {
    setPhoneLoading(true)
    setPhoneRequested(true)
    try {
      const shared = await requestContact()
      if (!shared) {
        showAlert(t('profile.header.verifyPhone'))
        return
      }

      // Phone arrives to bot asynchronously; refresh profile a few times.
      let next = undefined as Awaited<ReturnType<typeof auth.refreshUser>>
      for (let i = 0; i < 25 && !next?.phoneNumber; i += 1) {
        try {
          next = await auth.refreshUser()
        } catch (e) {
          // If auth isn't ready yet (no JWT), wait a bit and try again.
          if (e instanceof Error && e.message === 'not_authenticated') {
            if (i === 0) showAlert(t('profile.phone.authPending'))
            await sleep(700)
            continue
          }
          throw e
        }
        if (next?.phoneNumber) break
        await sleep(700)
      }

      if (next?.phoneNumber) {
        haptic('success')
        showAlert(t('profile.phone.linkedSuccess'))
      } else {
        haptic('error')
        showAlert(t('profile.phone.notArrived'))
      }
    } catch {
      haptic('error')
      showAlert(t('profile.phone.failed'))
    } finally {
      setPhoneLoading(false)
    }
  }

  // In Telegram environment we wait for provider bootstrap,
  // so the profile doesn't "flash" Guest before real user arrives.
  // Backend validation should NOT block rendering Telegram user info.
  if (isTelegram && !isReady) {
    return (
      <Box>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1.5 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <PersonRoundedIcon sx={{ fontSize: 28, color: 'primary.main' }} />
            <Typography variant="h5" sx={{ fontWeight: 800 }}>
              {t('profile.title')}
            </Typography>
          </Box>
          <ProfileSettingsDrawer />
        </Box>

        <Card sx={{ mb: 1.5 }}>
          <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'flex-start' }}>
            <Skeleton variant="circular" width={48} height={48} />
            <Box sx={{ flex: 1 }}>
              <Skeleton width="60%" height={28} />
              <Skeleton width="40%" height={20} />
              <Skeleton width="80%" height={18} />
              <Skeleton width="50%" height={18} />
            </Box>
          </Box>
        </Card>

        <Card sx={{ mb: 1.5 }}>
          <Skeleton width="35%" height={20} />
          <Skeleton width="100%" height={48} />
        </Card>
      </Box>
    )
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1.5 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <PersonRoundedIcon sx={{ fontSize: 28, color: 'primary.main' }} />
          <Typography variant="h5" sx={{ fontWeight: 800 }}>
            {t('profile.title')}
          </Typography>
        </Box>
        <ProfileSettingsDrawer />
      </Box>

      <Card sx={{ mb: 1.5 }}>
        <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'flex-start' }}>
          <Avatar
            src={effectiveUser?.photo_url}
            alt={displayName}
            sx={{ width: 48, height: 48, bgcolor: 'success.main' }}
          >
            <PersonRoundedIcon />
          </Avatar>

          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
              <Typography sx={{ fontWeight: 900, lineHeight: 1.2 }}>{displayName}</Typography>
              {isVerified ? (
                <Badge icon={<VerifiedRoundedIcon />} label={t('common.verified')} color="success" />
              ) : null}
            </Box>

            <Divider sx={{ my: 1 }} />

            {username ? (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <Tooltip title={t('profile.header.username')}>
                  <Box sx={{ color: 'text.secondary', display: 'flex', alignItems: 'center' }}>
                    <AlternateEmailRoundedIcon fontSize="small" />
                  </Box>
                </Tooltip>
                <Typography variant="body2" color="text.secondary" aria-label={t('profile.header.username')}>
                  {username}
                </Typography>
              </Box>
            ) : null}

            {effectiveUser?.id ? (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
                <Tooltip title={t('profile.header.id')}>
                  <Box sx={{ color: 'text.secondary', display: 'flex', alignItems: 'center' }}>
                    <FingerprintRoundedIcon fontSize="small" />
                  </Box>
                </Tooltip>
                <Typography variant="body2" color="text.secondary" aria-label={t('profile.header.id')}>
                  {String(effectiveUser.id)}
                </Typography>
              </Box>
            ) : null}

            {phoneToShow ? (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
                <Tooltip title={t('profile.header.phone')}>
                  <Box sx={{ color: 'text.secondary', display: 'flex', alignItems: 'center' }}>
                    <PhoneIphoneRoundedIcon fontSize="small" />
                  </Box>
                </Tooltip>
                <Typography variant="body2" color="text.secondary" aria-label={t('profile.header.phone')}>
                  {phoneToShow}
                </Typography>
              </Box>
            ) : isTelegram && auth.status === 'loading' ? (
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 0.5 }}>
                <Box sx={{ color: 'text.secondary', display: 'flex', alignItems: 'center' }}>
                  <PhoneIphoneRoundedIcon fontSize="small" />
                </Box>
                <Skeleton width="40%" height={20} />
              </Box>
            ) : (
              <Box sx={{ mt: 1, display: 'flex', gap: 1, alignItems: 'center' }}>
                <Button
                  size="small"
                  variant="outlined"
                  onClick={() => {
                    void handleRequestPhone()
                  }}
                  disabled={!canRequestPhone || phoneLoading}
                >
                  {t('profile.header.verifyPhone')}
                </Button>
              </Box>
            )}

            {!phoneToShow && phoneRequested ? (
              <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                {t('profile.phone.pendingHint')}
              </Typography>
            ) : null}
          </Box>
        </Box>
      </Card>

      <ErrorBoundary
        fallback={
          <Card sx={{ p: 2 }}>
            <Typography variant="body2" color="text.secondary">
              Блок кошелька временно недоступен. Обновите страницу.
            </Typography>
          </Card>
        }
      >
        <BalanceBlock
          onTopUp={(currency) => {
            if (currency === 'stars') setStarsTopUpOpen(true)
            else if (currency === 'usdt') setUsdtTopUpOpen(true)
            else if (currency === 'ton') setTonTopUpOpen(true)
            else console.log('Top up', currency)
          }}
          onWithdraw={(currency) => {
            if (currency === 'stars') setStarsExchangeOpen(true)
            else if (currency === 'usdt') setUsdtWithdrawOpen(true)
            else if (currency === 'ton') setTonWithdrawOpen(true)
            else console.log('Withdraw', currency)
          }}
          onBuyStars={() => {
            webApp?.openLink?.('https://t.me/premium')
          }}
          balances={balances}
        />
      </ErrorBoundary>

      <StarsTopUpDialog
        open={starsTopUpOpen}
        onClose={() => setStarsTopUpOpen(false)}
        onSuccess={() => void fetchBalances()}
      />

      <StarsExchangeDialog
        open={starsExchangeOpen}
        onClose={() => setStarsExchangeOpen(false)}
        onSuccess={() => void fetchBalances()}
        starsBalance={balances.stars}
      />

      <UsdtTopUpDialog
        open={usdtTopUpOpen}
        onClose={() => setUsdtTopUpOpen(false)}
        onSuccess={() => void fetchBalances()}
      />

      <UsdtWithdrawDialog
        open={usdtWithdrawOpen}
        onClose={() => setUsdtWithdrawOpen(false)}
        onSuccess={() => void fetchBalances()}
        usdtBalance={balances.usdt}
      />

      <TonTopUpDialog
        open={tonTopUpOpen}
        onClose={() => setTonTopUpOpen(false)}
        onSuccess={() => void fetchBalances()}
      />

      <TonWithdrawDialog
        open={tonWithdrawOpen}
        onClose={() => setTonWithdrawOpen(false)}
        onSuccess={() => void fetchBalances()}
        tonBalance={balances.ton}
      />

      <InviteBlock />
    </Box>
  )
}


