import AddRoundedIcon from '@mui/icons-material/AddRounded'
import CampaignRoundedIcon from '@mui/icons-material/CampaignRounded'
import GroupsRoundedIcon from '@mui/icons-material/GroupsRounded'
import { Box, Skeleton, Typography } from '@mui/material'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../../app/providers/AuthProvider'
import { useTelegram } from '../../app/providers/TelegramProvider'
import { Button } from '../../shared/ui/Button'
import { Card } from '../../shared/ui/Card'
import { ApiError, getJson, postJson } from '../../shared/utils/api'
import { getApiBase } from '../../shared/utils/apiBase'
import { AddChannelDialog } from './AddChannelDialog'
import { ChannelDetailDialog } from './ChannelDetailDialog'
import { ChannelSettingsDrawer } from './ChannelSettingsDrawer'
import { MyChannelCard } from './MyChannelCard'

export type ChannelData = {
  id: number
  telegramId: number
  chatType: string
  title: string
  username: string | null
  description: string | null
  photoUrl: string | null
  subscriberCount: number
  inviteLink: string | null
  status: 'pending' | 'active' | 'paused' | 'inactive' | 'removed'
  isVisible: boolean
  category: string | null
  language: string | null
  createdAt: string
  updatedAt: string
}

type ChannelsResponse = {
  channels: ChannelData[]
  total: number
}

export function MyChannelsPage() {
  const { t } = useTranslation()
  const { token } = useAuth()
  const { webApp } = useTelegram()

  const [channels, setChannels] = useState<ChannelData[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [addDialogOpen, setAddDialogOpen] = useState(false)
  const [selectedChannel, setSelectedChannel] = useState<ChannelData | null>(null)
  const [detailDialogOpen, setDetailDialogOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)

  const fetchChannels = useCallback(async () => {
    if (!token) return

    setLoading(true)
    setError(null)

    try {
      const base = getApiBase()
      const data = await getJson<ChannelsResponse>(`${base}/api/channels`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      setChannels(data.channels)
    } catch (e) {
      console.error('Failed to fetch channels:', e)
      setError('Failed to load channels')
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => {
    void fetchChannels()
  }, [fetchChannels])

  // Refetch channels when window regains focus (user may have added bot to channel)
  useEffect(() => {
    const handleFocus = () => {
      void fetchChannels()
    }

    window.addEventListener('focus', handleFocus)
    return () => {
      window.removeEventListener('focus', handleFocus)
    }
  }, [fetchChannels])

  // WebSocket for real-time channel updates
  useEffect(() => {
    if (!token) return

    const base = getApiBase()
    if (!base.startsWith('http')) return

    const wsUrl = base.replace(/^https?:/, 'wss:').replace(/^http:/, 'ws:') + `/ws?token=${encodeURIComponent(token)}`

    try {
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data as string) as {
            type: string
            channelId?: number
            telegramId?: number
            title?: string
            status?: string
            reason?: string
          }

          if (msg.type === 'channel_added' && msg.channelId) {
            // New channel added — refetch to get full data
            void fetchChannels()
            webApp?.HapticFeedback?.notificationOccurred?.('success')
          }

          if (msg.type === 'channel_inactive' && msg.channelId) {
            // Bot lost admin rights — mark as inactive
            setChannels((prev) =>
              prev.map((ch) =>
                ch.id === msg.channelId ? { ...ch, status: 'inactive' as const, isVisible: false } : ch
              )
            )
            webApp?.HapticFeedback?.notificationOccurred?.('warning')
          }

          if (msg.type === 'channel_removed' && msg.channelId) {
            // Bot removed from channel — mark as removed
            setChannels((prev) =>
              prev.map((ch) =>
                ch.id === msg.channelId ? { ...ch, status: 'removed' as const, isVisible: false } : ch
              )
            )
            webApp?.HapticFeedback?.notificationOccurred?.('error')
          }
        } catch {
          // Invalid message
        }
      }

      return () => {
        ws.close()
        wsRef.current = null
      }
    } catch {
      // WebSocket not available
    }
  }, [token, fetchChannels, webApp])

  const handleChannelClick = (channel: ChannelData) => {
    setSelectedChannel(channel)
    setDetailDialogOpen(true)
  }

  const handleOpenSettings = (channel: ChannelData) => {
    setSelectedChannel(channel)
    setSettingsOpen(true)
  }

  const handlePublishToMarket = async (channel: ChannelData) => {
    if (!token) return

    const base = getApiBase()
    const isPublished = channel.isVisible && channel.status === 'active'
    const endpoint = isPublished ? 'pause' : 'activate'

    try {
      const updated = await postJson<ChannelData>(`${base}/api/channels/${channel.id}/${endpoint}`, {}, {
        headers: { Authorization: `Bearer ${token}` },
      })

      webApp?.HapticFeedback?.notificationOccurred?.('success')

      // Локально обновляем выбранный канал, чтобы сразу поменялась кнопка
      setSelectedChannel((prev) => (prev && prev.id === updated.id ? updated : prev))

      // И обновляем общий список каналов
      void fetchChannels()
    } catch (e) {
      console.error('Failed to toggle market status:', e)
      webApp?.HapticFeedback?.notificationOccurred?.('error')
      if (e instanceof ApiError && e.status === 400 && !isPublished) {
        webApp?.showAlert?.(t('channelDetail.publishErrorNoFormats'))
      }
    }
  }

  if (loading) {
    return (
      <Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
          <CampaignRoundedIcon sx={{ fontSize: 28, color: 'primary.main' }} />
          <Typography variant="h5" sx={{ fontWeight: 800 }}>
            {t('myChannels.title')}
          </Typography>
        </Box>
        <Card sx={{ mb: 1.5 }}>
          <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'center' }}>
            <Skeleton variant="circular" width={48} height={48} />
            <Box sx={{ flex: 1 }}>
              <Skeleton width="60%" height={24} />
              <Skeleton width="40%" height={18} />
            </Box>
          </Box>
        </Card>
        <Card>
          <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'center' }}>
            <Skeleton variant="circular" width={48} height={48} />
            <Box sx={{ flex: 1 }}>
              <Skeleton width="50%" height={24} />
              <Skeleton width="35%" height={18} />
            </Box>
          </Box>
        </Card>
      </Box>
    )
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
        <CampaignRoundedIcon sx={{ fontSize: 28, color: 'primary.main' }} />
        <Typography variant="h5" sx={{ fontWeight: 800 }}>
          {t('myChannels.title')}
        </Typography>
      </Box>

      {error && (
        <Card sx={{ mb: 1.5, bgcolor: 'error.main', color: 'error.contrastText' }}>
          <Typography variant="body2">{error}</Typography>
          <Button
            variant="outlined"
            size="small"
            onClick={() => void fetchChannels()}
            sx={{ mt: 1, color: 'inherit', borderColor: 'inherit' }}
          >
            {t('common.retry')}
          </Button>
        </Card>
      )}

      {channels.length === 0 && !error ? (
        <Card
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            py: 4,
            textAlign: 'center',
          }}
        >
          <GroupsRoundedIcon sx={{ fontSize: 48, color: 'text.secondary', mb: 1.5 }} />
          <Typography sx={{ fontWeight: 700, mb: 0.5 }}>{t('myChannels.empty.title')}</Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2, maxWidth: 280 }}>
            {t('myChannels.empty.description')}
          </Typography>
          <Button
            variant="contained"
            startIcon={<AddRoundedIcon />}
            onClick={() => setAddDialogOpen(true)}
          >
            {t('myChannels.add')}
          </Button>
        </Card>
      ) : (
        <>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
            {channels.map((channel) => (
              <MyChannelCard
                key={channel.id}
                channel={channel}
                onClick={() => handleChannelClick(channel)}
              />
            ))}
          </Box>

          <Button
            fullWidth
            variant="contained"
            startIcon={<AddRoundedIcon />}
            onClick={() => setAddDialogOpen(true)}
            sx={{ mt: 2 }}
          >
            {t('myChannels.add')}
          </Button>
        </>
      )}

      <AddChannelDialog
        open={addDialogOpen}
        onClose={() => setAddDialogOpen(false)}
        onChannelAdded={() => {
          setAddDialogOpen(false)
          void fetchChannels()
        }}
      />

      <ChannelDetailDialog
        open={detailDialogOpen}
        onClose={() => {
          setDetailDialogOpen(false)
          setSelectedChannel(null)
        }}
        channel={selectedChannel}
        onOpenSettings={handleOpenSettings}
        onPublishToMarket={handlePublishToMarket}
        onChannelUpdated={() => {
          // Silently update channels list without visible refresh
          // Use a small delay to avoid blocking UI
          setTimeout(() => {
            void fetchChannels()
          }, 500)
        }}
      />

      {selectedChannel && (
        <ChannelSettingsDrawer
          open={settingsOpen}
          channel={selectedChannel}
          onClose={() => setSettingsOpen(false)}
          onSaved={() => {
            // Refresh channels list after saving settings
            void fetchChannels()
          }}
        />
      )}
    </Box>
  )
}
