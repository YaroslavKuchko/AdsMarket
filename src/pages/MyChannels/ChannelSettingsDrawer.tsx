import CloseRoundedIcon from '@mui/icons-material/CloseRounded'
import AutoAwesomeMotionRoundedIcon from '@mui/icons-material/AutoAwesomeMotionRounded'
import CategoryRoundedIcon from '@mui/icons-material/CategoryRounded'
import PushPinRoundedIcon from '@mui/icons-material/PushPinRounded'
import TimerRoundedIcon from '@mui/icons-material/TimerRounded'
import {
  Box,
  Dialog,
  DialogContent,
  IconButton,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
  TextField,
  Switch,
  FormControlLabel,
  Chip,
  CircularProgress,
  useMediaQuery,
  useTheme,
} from '@mui/material'
import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../../app/providers/AuthProvider'
import { useTelegram } from '../../app/providers/TelegramProvider'
import { Button } from '../../shared/ui/Button'
import { Card } from '../../shared/ui/Card'
import { getApiBase } from '../../shared/utils/apiBase'
import { starsIcon, usdtIcon } from '../../shared/assets/icons'
import { getJson, putJson } from '../../shared/utils/api'
import type { ChannelData } from './MyChannelsPage'

type PostingMode = 'auto' | 'manual'

type AdFormatSettings = {
  pinned?: boolean
  postingMode?: PostingMode
}

type AdFormatDto = {
  id: number
  formatType: string
  isEnabled: boolean
  priceStars: number
  priceTon: number | null
  priceUsdt: number | null
  durationHours: number
  etaHours: number
  settings?: AdFormatSettings | null
}

type ChannelDetailResponse = ChannelData & {
  adFormats: AdFormatDto[]
}

type LocalFormat = {
  key: string
  labelKey: string
  durationHours: number
  isEnabled: boolean
  pinned: boolean
  priceStars: string
  priceUsdt: string
}

type ChannelSettingsDrawerProps = {
  open: boolean
  channel: ChannelData
  onClose: () => void
  onSaved?: () => void
}

export function ChannelSettingsDrawer({ open, channel, onClose, onSaved }: ChannelSettingsDrawerProps) {
  const { t } = useTranslation()
  const { token } = useAuth()
  const { webApp } = useTelegram()
  const theme = useTheme()
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'))

  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [formats, setFormats] = useState<LocalFormat[]>([])
  const [postingMode, setPostingMode] = useState<PostingMode>('auto')
  const [category, setCategory] = useState<string | null>(null)
  const [aiCategoryLabel, setAiCategoryLabel] = useState<string | null>(null)
  const [loadingAiCategory, setLoadingAiCategory] = useState(false)
  const [savedMessage, setSavedMessage] = useState<string | null>(null)
  const [starsPerUsd, setStarsPerUsd] = useState<number | null>(null)

  const base = useMemo(() => getApiBase(), [])

  // Load config for Stars/USD rate (for price field label)
  useEffect(() => {
    if (!open || !base) return
    getJson<{ starsPerUsd?: number }>(`${base}/api/config`)
      .then((c) => setStarsPerUsd(c.starsPerUsd ?? null))
      .catch(() => setStarsPerUsd(null))
  }, [open, base])

  // Base config for formats – easy to extend in future
  const baseFormatsConfig = useMemo(
    () => [
      {
        key: 'post_24h',
        labelKey: 'channelSettings.format24h',
        durationHours: 24,
      },
      {
        key: 'post_48h',
        labelKey: 'channelSettings.format48h',
        durationHours: 48,
      },
    ],
    [],
  )

  // Load existing formats from backend
  useEffect(() => {
    if (!open || !token || !base) return

    const fetchDetails = async () => {
      try {
        setLoading(true)
        const data = await getJson<ChannelDetailResponse>(`${base}/api/channels/${channel.id}`, {
          headers: { Authorization: `Bearer ${token}` },
        })

        const incoming = data.adFormats ?? []

        setCategory(data.category ?? null)

        // Derive global postingMode from first format that has it
        const modeFromSettings =
          (incoming.find((f) => f.settings?.postingMode)?.settings?.postingMode as PostingMode | undefined) ?? 'auto'
        setPostingMode(modeFromSettings)

        const mapped: LocalFormat[] = baseFormatsConfig.map((cfg) => {
          const existing = incoming.find((f) => f.durationHours === cfg.durationHours && f.formatType === 'post')
          const s = existing?.settings ?? {}

          return {
            key: cfg.key,
            labelKey: cfg.labelKey,
            durationHours: cfg.durationHours,
            isEnabled: existing?.isEnabled ?? false,
            pinned: Boolean(s.pinned),
            priceStars: existing ? String(existing.priceStars ?? 0) : '',
            priceUsdt: existing && existing.priceUsdt != null ? String(existing.priceUsdt) : '',
          }
        })

        setFormats(mapped)
      } catch (e) {
        // Silent in UI, log in console
        // eslint-disable-next-line no-console
        console.error('Failed to load channel formats:', e)
      } finally {
        setLoading(false)
      }
    }

    void fetchDetails()
  }, [open, token, base, channel.id, baseFormatsConfig])

  // Load AI suggested category (optional)
  useEffect(() => {
    if (!open || !token || !base) return

    const fetchAiCategory = async () => {
      try {
        setLoadingAiCategory(true)
        const res = await getJson<{ ok: boolean; data?: { category: string } }>(
          `${base}/api/channels/${channel.id}/ai-insights-structured`,
          { headers: { Authorization: `Bearer ${token}` } },
        )
        if (res.ok && res.data?.category) {
          // Сохраняем категорию от AI как есть (полный текст, например "Скидки и промокоды")
          setAiCategoryLabel(res.data.category)
        } else {
          setAiCategoryLabel(null)
        }
      } catch {
        // ignore errors, AI категория опциональна
        setAiCategoryLabel(null)
      } finally {
        setLoadingAiCategory(false)
      }
    }

    void fetchAiCategory()
  }, [open, token, base, channel.id])

  const handleChangeFormat = (key: string, patch: Partial<LocalFormat>) => {
    setFormats((prev) => prev.map((f) => (f.key === key ? { ...f, ...patch } : f)))
  }

  const handleUsdtChange = (key: string, value: string) => {
    setFormats((prev) =>
      prev.map((f) => {
        if (f.key !== key) return f
        const patch: Partial<LocalFormat> = { priceUsdt: value }
        if (starsPerUsd != null && value) {
          const usd = parseFloat(value)
          if (!Number.isNaN(usd) && usd >= 0) {
            patch.priceStars = String(Math.round(usd * starsPerUsd))
          }
        }
        return { ...f, ...patch }
      }),
    )
  }

  const handleSave = async () => {
    if (!token || !base || saving) return

    setSaving(true)
    try {
      const payload = formats.map((f) => ({
        formatType: 'post',
        isEnabled: f.isEnabled,
        priceStars: Number(f.priceStars) || 0,
        priceTon: null,
        priceUsdt: f.priceUsdt ? Number(f.priceUsdt) : null,
        durationHours: f.durationHours,
        etaHours: f.durationHours,
        settings: {
          pinned: f.pinned,
          postingMode,
        } as AdFormatSettings,
      }))

      await putJson<AdFormatDto[]>(`${base}/api/channels/${channel.id}/formats`, payload, {
        headers: { Authorization: `Bearer ${token}` },
      })

      if (category) {
        await putJson<ChannelData>(`${base}/api/channels/${channel.id}`, { category }, {
          headers: { Authorization: `Bearer ${token}` },
        })
      }

      webApp?.HapticFeedback?.notificationOccurred?.('success')

      setSavedMessage(t('channelSettings.savedMessage'))
      window.setTimeout(() => setSavedMessage(null), 3000)

      onSaved?.()
      onClose()
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error('Failed to save channel formats:', e)
    } finally {
      setSaving(false)
    }
  }

  return (
    <Dialog
      open={open}
      onClose={onClose}
      fullScreen={isMobile}
      fullWidth
      maxWidth="sm"
      PaperProps={{
        sx: {
          borderRadius: isMobile ? 0 : 3,
          maxHeight: isMobile ? '100%' : '90vh',
        },
      }}
    >
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          p: 2,
          borderBottom: 1,
          borderColor: 'divider',
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <IconButton onClick={onClose} size="small">
            <CloseRoundedIcon />
          </IconButton>
          <Box>
            <Typography sx={{ fontWeight: 800 }}>{t('channelSettings.title')}</Typography>
            <Typography variant="caption" color="text.secondary">
              {channel.title}
            </Typography>
          </Box>
        </Box>
      </Box>

      <DialogContent sx={{ p: 2 }}>
        {/* Category */}
        <Card sx={{ mb: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <CategoryRoundedIcon sx={{ fontSize: 20, color: 'primary.main' }} />
              <Typography sx={{ fontWeight: 700 }}>{t('channelSettings.category')}</Typography>
            </Box>
            {loadingAiCategory ? (
              <CircularProgress size={18} />
            ) : aiCategoryLabel ? (
              <Chip
                size="small"
                icon={<AutoAwesomeMotionRoundedIcon sx={{ fontSize: 16 }} />}
                label={aiCategoryLabel}
                onClick={() => setCategory(aiCategoryLabel)}
                color={category === aiCategoryLabel ? 'primary' : 'default'}
                variant={category === aiCategoryLabel ? 'filled' : 'outlined'}
                sx={{ fontSize: 11 }}
              />
            ) : null}
          </Box>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75 }}>
            {['news', 'tech', 'lifestyle', 'crypto', 'entertainment', 'education', 'other'].map((key) => (
              <Chip
                key={key}
                label={t(`categories.${key}`)}
                size="small"
                color={category === key ? 'primary' : 'default'}
                variant={category === key ? 'filled' : 'outlined'}
                onClick={() => setCategory(key)}
                sx={{ fontSize: 11 }}
              />
            ))}
          </Box>
        </Card>

        {/* Posting mode */}
        <Card
          sx={{
            mb: 2,
            p: 1.5,
            borderRadius: 3,
            background: theme.palette.mode === 'dark'
              ? 'linear-gradient(135deg, rgba(34,197,94,0.18) 0%, rgba(56,189,248,0.08) 100%)'
              : 'linear-gradient(135deg, rgba(34,197,94,0.12) 0%, rgba(56,189,248,0.05) 100%)',
            border: `1px solid ${theme.palette.divider}`,
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
            <AutoAwesomeMotionRoundedIcon sx={{ fontSize: 22, color: 'primary.main' }} />
            <Typography sx={{ fontWeight: 800 }}>{t('channelSettings.placementMode')}</Typography>
          </Box>
          <ToggleButtonGroup
            exclusive
            value={postingMode}
            onChange={(_, val: PostingMode | null) => val && setPostingMode(val)}
            size="small"
            sx={{
              display: 'flex',
              gap: 1,
              '& .MuiToggleButton-root': {
                flex: 1,
                textTransform: 'none',
                fontWeight: 600,
                borderRadius: 2,
                alignItems: 'flex-start',
                px: 1.5,
                py: 1,
                border: '1px solid',
                borderColor: 'divider',
                '&.Mui-selected': {
                  bgcolor: 'primary.main',
                  borderColor: 'primary.main',
                  color: 'primary.contrastText',
                },
              },
            }}
          >
            <ToggleButton value="auto">
              <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 0.25 }}>
                <Typography variant="body2" sx={{ fontWeight: 700 }}>
                  {t('channelSettings.placementModeAuto')}
                </Typography>
                <Typography variant="caption" sx={{ opacity: 0.8 }}>
                  {t('channelSettings.placementModeAuto')}
                </Typography>
              </Box>
            </ToggleButton>
            <ToggleButton value="manual">
              <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 0.25 }}>
                <Typography variant="body2" sx={{ fontWeight: 700 }}>
                  {t('channelSettings.placementModeManual')}
                </Typography>
                <Typography variant="caption" sx={{ opacity: 0.8 }}>
                  {t('channelSettings.placementModeManual')}
                </Typography>
              </Box>
            </ToggleButton>
          </ToggleButtonGroup>
        </Card>

        {/* Ad formats */}
        <Typography sx={{ fontWeight: 700, mb: 1 }}>
          {t('channelSettings.adFormats')}
        </Typography>

        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
          {formats.map((f) => (
            <Card key={f.key}>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <TimerRoundedIcon sx={{ fontSize: 20, color: 'primary.main' }} />
                  <Typography sx={{ fontWeight: 700 }}>{t(f.labelKey)}</Typography>
                </Box>
                <FormControlLabel
                  control={
                    <Switch
                      checked={f.isEnabled}
                      onChange={(e) => handleChangeFormat(f.key, { isEnabled: e.target.checked })}
                    />
                  }
                  label={t('channelSettings.enabled')}
                />
              </Box>

              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                <PushPinRoundedIcon sx={{ fontSize: 18, color: f.pinned ? 'warning.main' : 'text.disabled' }} />
                <FormControlLabel
                  control={
                    <Switch
                      checked={f.pinned}
                      onChange={(e) => handleChangeFormat(f.key, { pinned: e.target.checked })}
                      size="small"
                    />
                  }
                  label={t('channelSettings.pinned')}
                />
              </Box>

              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Box
                    component="img"
                    src={usdtIcon}
                    alt=""
                    sx={{ width: 18, height: 18, borderRadius: '50%' }}
                  />
                  <TextField
                    fullWidth
                    size="small"
                    type="number"
                    label={t('channelSettings.priceUsdt')}
                    value={f.priceUsdt}
                    onChange={(e) => handleUsdtChange(f.key, e.target.value)}
                    inputProps={{ min: 0, step: '0.01' }}
                  />
                </Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Box component="img" src={starsIcon} alt="" sx={{ width: 18, height: 18 }} />
                  <TextField
                    fullWidth
                    size="small"
                    type="number"
                    label={
                      starsPerUsd != null
                        ? t('channelSettings.priceStarsHint', { count: starsPerUsd })
                        : t('channelSettings.priceStars')
                    }
                    value={f.priceStars}
                    onChange={(e) => handleChangeFormat(f.key, { priceStars: e.target.value })}
                    inputProps={{ min: 0 }}
                  />
                </Box>
              </Box>
            </Card>
          ))}
        </Box>
      </DialogContent>

      <Box
        sx={{
          p: 2,
          borderTop: 1,
          borderColor: 'divider',
          bgcolor: 'background.paper',
        }}
      >
        {savedMessage && (
          <Typography
            variant="caption"
            color="success.main"
            sx={{ display: 'block', textAlign: 'center', mb: 1, fontWeight: 600 }}
          >
            {savedMessage}
          </Typography>
        )}
        <Button fullWidth variant="contained" onClick={handleSave} disabled={saving || loading}>
          {t('channelSettings.save')}
        </Button>
      </Box>
    </Dialog>
  )
}

