import AccountBalanceWalletRoundedIcon from '@mui/icons-material/AccountBalanceWalletRounded'
import DevicesOtherRoundedIcon from '@mui/icons-material/DevicesOtherRounded'
import LinkOffRoundedIcon from '@mui/icons-material/LinkOffRounded'
import {
  Box,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  IconButton,
  ToggleButton,
  ToggleButtonGroup,
  Tooltip,
  Typography,
} from '@mui/material'
import { useTonConnectUI, useTonWallet } from '@tonconnect/ui-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../../app/providers/AuthProvider'
import { Card } from '../../shared/ui/Card'
import { Button } from '../../shared/ui/Button'
import { starsIcon, tonIcon, usdtIcon } from '../../shared/assets/icons'
import { useTonWalletSync } from '../../shared/hooks/useTonWalletSync'
import { getJson } from '../../shared/utils/api'
import { getApiBase } from '../../shared/utils/apiBase'

type BackendWalletInfo = {
  connected: boolean
  address?: string
  friendlyAddress?: string
  walletName?: string
}

type Currency = 'stars' | 'ton' | 'usdt'

type BalanceBlockProps = {
  onTopUp: (currency: Currency) => void
  onWithdraw: (currency: Currency) => void
  onBuyStars?: () => void
  balances?: {
    stars: number
    ton: number
    usdt: number
  }
}

/**
 * Shortens TON wallet address for display.
 * Example: UQB...abc
 */
function shortenAddress(address: string): string {
  if (address.length <= 10) return address
  return `${address.slice(0, 4)}...${address.slice(-4)}`
}

export function BalanceBlock({
  onTopUp,
  onWithdraw,
  onBuyStars: _onBuyStars,
  balances = { stars: 0, ton: 0, usdt: 0 },
}: BalanceBlockProps) {
  const { t } = useTranslation()
  const { token } = useAuth()
  const [currency, setCurrency] = useState<Currency>('stars')
  const [disconnectDialogOpen, setDisconnectDialogOpen] = useState(false)

  // TON Connect hooks (local state) - single useTonWallet to avoid hooks mismatch
  const [tonConnectUI] = useTonConnectUI()
  const localWallet = useTonWallet()

  // Backend wallet info (synced across devices)
  const [backendWallet, setBackendWallet] = useState<BackendWalletInfo | null>(null)

  // Sync wallet state with backend (pass wallet to avoid duplicate useTonWallet)
  useTonWalletSync(localWallet, token)

  // Fetch wallet info from backend on mount
  useEffect(() => {
    if (!token) return

    const fetchWalletInfo = async () => {
      try {
        const base = getApiBase()
        const info = await getJson<BackendWalletInfo>(`${base}/api/wallet/info`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        setBackendWallet(info)
      } catch (e) {
        console.error('Failed to fetch wallet info:', e)
      }
    }

    void fetchWalletInfo()
  }, [token, localWallet]) // Refetch when local wallet changes

  // Determine wallet state
  const isLocallyConnected = Boolean(localWallet)
  const isBackendConnected = backendWallet?.connected ?? false
  const isConnectedOnOtherDevice = isBackendConnected && !isLocallyConnected

  const walletAddress = localWallet?.account?.address ?? backendWallet?.friendlyAddress ?? backendWallet?.address ?? null
  const walletName = backendWallet?.walletName

  const handleConnectWallet = async () => {
    try {
      await tonConnectUI.openModal()
    } catch (e) {
      console.error('Failed to open TON Connect modal:', e)
    }
  }

  const handleDisconnectWallet = async () => {
    try {
      await tonConnectUI.disconnect()
    } catch (e) {
      console.error('Failed to disconnect wallet:', e)
    }
  }

  const formatBalance = (value: number, cur: Currency) => {
    if (cur === 'stars') return value.toLocaleString()
    return value.toFixed(2)
  }

  const currencyConfig = {
    stars: {
      icon: <Box component="img" src={starsIcon} alt="" sx={{ width: 18, height: 18 }} />,
      label: t('profile.balance.stars'),
      symbol: '⭐',
      color: '#FFB800',
    },
    ton: {
      icon: <Box component="img" src={tonIcon} alt="" sx={{ width: 18, height: 18, borderRadius: '50%' }} />,
      label: t('profile.balance.ton'),
      symbol: 'TON',
      color: '#0098EA',
    },
    usdt: {
      icon: <Box component="img" src={usdtIcon} alt="" sx={{ width: 18, height: 18, borderRadius: '50%' }} />,
      label: t('profile.balance.usdt'),
      symbol: 'USDT',
      color: '#22C55E',
    },
  } as const

  const currentConfig = currencyConfig[currency]
  const currentBalance = balances[currency]

  return (
    <Card sx={{ mb: 1.5 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mb: 1.5 }}>
        <AccountBalanceWalletRoundedIcon sx={{ fontSize: 20, color: 'primary.main' }} />
        <Typography sx={{ fontWeight: 800 }}>{t('profile.balance.title')}</Typography>
      </Box>

      {/* Currency Tabs */}
      <ToggleButtonGroup
        value={currency}
        exclusive
        onChange={(_, val: Currency | null) => val && setCurrency(val)}
        fullWidth
        size="small"
        sx={{
          mb: 1.5,
          gap: 0.75,
          '& .MuiToggleButton-root': {
            flex: 1,
            py: 0.75,
            gap: 0.5,
            textTransform: 'none',
            fontWeight: 600,
            fontSize: 13,
            borderRadius: '8px !important',
            border: '1px solid',
            borderColor: 'divider',
            '&.Mui-selected': {
              bgcolor: 'action.selected',
              borderColor: 'primary.main',
              color: 'primary.main',
            },
          },
          '& .MuiToggleButtonGroup-grouped': {
            '&:not(:first-of-type)': {
              borderLeft: '1px solid',
              borderLeftColor: 'divider',
              ml: 0,
            },
            '&.Mui-selected': {
              borderColor: 'primary.main',
            },
          },
        }}
      >
        <ToggleButton value="stars">
          {currencyConfig.stars.icon}
          {currencyConfig.stars.label}
        </ToggleButton>
        <ToggleButton value="ton">
          {currencyConfig.ton.icon}
          {currencyConfig.ton.label}
        </ToggleButton>
        <ToggleButton value="usdt">
          {currencyConfig.usdt.icon}
          {currencyConfig.usdt.label}
        </ToggleButton>
      </ToggleButtonGroup>

      {/* Balance Display */}
      <Box
        sx={{
          p: 1.5,
          border: 1,
          borderColor: 'divider',
          borderRadius: 2,
          mb: 1.5,
          background: (theme) =>
            theme.palette.mode === 'dark'
              ? `linear-gradient(135deg, ${currentConfig.color}15 0%, transparent 100%)`
              : `linear-gradient(135deg, ${currentConfig.color}10 0%, transparent 100%)`,
        }}
      >
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mb: 0.5 }}>
          {currentConfig.label}
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
          <Typography sx={{ fontWeight: 900, fontSize: 28, lineHeight: 1 }}>
            {formatBalance(currentBalance, currency)}
          </Typography>
          {currency === 'stars' && (
            <Box component="img" src={starsIcon} alt="Stars" sx={{ width: 24, height: 24 }} />
          )}
          {currency === 'ton' && (
            <Box component="img" src={tonIcon} alt="TON" sx={{ width: 24, height: 24, borderRadius: '50%' }} />
          )}
          {currency === 'usdt' && (
            <Box component="img" src={usdtIcon} alt="USDT" sx={{ width: 24, height: 24, borderRadius: '50%' }} />
          )}
        </Box>
      </Box>

      {/* Actions based on currency */}
      {currency === 'stars' && (
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button fullWidth variant="contained" onClick={() => onTopUp('stars')}>
            {t('profile.wallet.topUp')}
          </Button>
          <Button fullWidth variant="outlined" onClick={() => onWithdraw('stars')}>
            {t('profile.starsExchange.button')}
          </Button>
        </Box>
      )}

      {currency === 'ton' && (
        <>
          {isLocallyConnected ? (
            /* Wallet connected on THIS device */
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 1,
                  p: 1,
                  bgcolor: 'success.main',
                  color: 'success.contrastText',
                  borderRadius: 1.5,
                }}
              >
                <AccountBalanceWalletRoundedIcon sx={{ fontSize: 20 }} />
                <Typography variant="body2" sx={{ flex: 1, fontFamily: 'monospace' }}>
                  {walletAddress ? shortenAddress(walletAddress) : t('profile.wallet.connected')}
                </Typography>
                <Tooltip title={t('profile.wallet.disconnect')}>
                  <IconButton
                    size="small"
                    onClick={() => setDisconnectDialogOpen(true)}
                    sx={{ color: 'inherit', p: 0.5 }}
                  >
                    <LinkOffRoundedIcon sx={{ fontSize: 18 }} />
                  </IconButton>
                </Tooltip>
              </Box>

              <Box sx={{ display: 'flex', gap: 1 }}>
                <Button fullWidth variant="contained" onClick={() => onTopUp('ton')}>
                  {t('profile.wallet.topUp')}
                </Button>
                <Button fullWidth variant="outlined" onClick={() => onWithdraw('ton')}>
                  {t('profile.wallet.withdraw')}
                </Button>
              </Box>
            </Box>
          ) : isConnectedOnOtherDevice ? (
            /* Wallet connected on ANOTHER device */
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 1,
                  p: 1,
                  bgcolor: 'warning.main',
                  color: 'warning.contrastText',
                  borderRadius: 1.5,
                }}
              >
                <DevicesOtherRoundedIcon sx={{ fontSize: 20 }} />
                <Box sx={{ flex: 1 }}>
                  <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                    {walletAddress ? shortenAddress(walletAddress) : ''}
                  </Typography>
                  <Typography variant="caption" sx={{ opacity: 0.9 }}>
                    {walletName ? `${walletName} • ` : ''}{t('profile.wallet.connectedOtherDevice')}
                  </Typography>
                </Box>
              </Box>

              <Button fullWidth variant="contained" onClick={() => void handleConnectWallet()}>
                {t('profile.wallet.connectHere')}
              </Button>

              <Box sx={{ display: 'flex', gap: 1 }}>
                <Button fullWidth variant="outlined" onClick={() => onTopUp('ton')}>
                  {t('profile.wallet.topUp')}
                </Button>
                <Button fullWidth variant="outlined" onClick={() => onWithdraw('ton')}>
                  {t('profile.wallet.withdraw')}
                </Button>
              </Box>
            </Box>
          ) : (
            /* Wallet NOT connected anywhere */
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 1,
                  p: 1,
                  bgcolor: 'action.hover',
                  borderRadius: 1.5,
                }}
              >
                <AccountBalanceWalletRoundedIcon sx={{ color: 'text.secondary', fontSize: 20 }} />
                <Typography variant="body2" color="text.secondary" sx={{ flex: 1 }}>
                  {t('profile.wallet.notConnected')}
                </Typography>
              </Box>
              <Button fullWidth variant="contained" onClick={() => void handleConnectWallet()}>
                {t('profile.wallet.connect')}
              </Button>
            </Box>
          )}
        </>
      )}

      {currency === 'usdt' && (
        <Box sx={{ display: 'flex', gap: 1 }}>
          <Button fullWidth variant="contained" onClick={() => onTopUp('usdt')}>
            {t('profile.wallet.topUp')}
          </Button>
          <Button fullWidth variant="outlined" onClick={() => onWithdraw('usdt')}>
            {t('profile.wallet.withdraw')}
          </Button>
        </Box>
      )}

      {/* Disconnect confirmation dialog */}
      <Dialog
        open={disconnectDialogOpen}
        onClose={() => setDisconnectDialogOpen(false)}
        PaperProps={{
          sx: { borderRadius: 3, m: 2 },
        }}
      >
        <DialogTitle sx={{ fontWeight: 800 }}>
          {t('profile.wallet.disconnectConfirmTitle')}
        </DialogTitle>
        <DialogContent>
          <DialogContentText>
            {t('profile.wallet.disconnectConfirmText')}
          </DialogContentText>
          {walletAddress && (
            <Box
              sx={{
                mt: 1.5,
                p: 1,
                bgcolor: 'action.hover',
                borderRadius: 1,
                fontFamily: 'monospace',
                fontSize: 14,
              }}
            >
              {shortenAddress(walletAddress)}
            </Box>
          )}
        </DialogContent>
        <DialogActions sx={{ p: 2, pt: 0 }}>
          <Button variant="outlined" onClick={() => setDisconnectDialogOpen(false)}>
            {t('common.cancel')}
          </Button>
          <Button
            variant="contained"
            color="error"
            onClick={() => {
              setDisconnectDialogOpen(false)
              void handleDisconnectWallet()
            }}
          >
            {t('profile.wallet.disconnect')}
          </Button>
        </DialogActions>
      </Dialog>
    </Card>
  )
}
