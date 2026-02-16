import ArticleRoundedIcon from '@mui/icons-material/ArticleRounded'
import AutoAwesomeRoundedIcon from '@mui/icons-material/AutoAwesomeRounded'
import CampaignRoundedIcon from '@mui/icons-material/CampaignRounded'
import CategoryRoundedIcon from '@mui/icons-material/CategoryRounded'
import ChatBubbleOutlineRoundedIcon from '@mui/icons-material/ChatBubbleOutlineRounded'
import CheckCircleRoundedIcon from '@mui/icons-material/CheckCircleRounded'
import CloseRoundedIcon from '@mui/icons-material/CloseRounded'
import CollectionsRoundedIcon from '@mui/icons-material/CollectionsRounded'
import ErrorOutlineRoundedIcon from '@mui/icons-material/ErrorOutlineRounded'
import ExpandLessRoundedIcon from '@mui/icons-material/ExpandLessRounded'
import ExpandMoreRoundedIcon from '@mui/icons-material/ExpandMoreRounded'
import FavoriteRoundedIcon from '@mui/icons-material/FavoriteRounded'
import GroupsRoundedIcon from '@mui/icons-material/GroupsRounded'
import LightbulbRoundedIcon from '@mui/icons-material/LightbulbRounded'
import OpenInNewRoundedIcon from '@mui/icons-material/OpenInNewRounded'
import RefreshRoundedIcon from '@mui/icons-material/RefreshRounded'
import RocketLaunchRoundedIcon from '@mui/icons-material/RocketLaunchRounded'
import SettingsRoundedIcon from '@mui/icons-material/SettingsRounded'
import ShareRoundedIcon from '@mui/icons-material/ShareRounded'
import SpeedRoundedIcon from '@mui/icons-material/SpeedRounded'
import TrendingDownRoundedIcon from '@mui/icons-material/TrendingDownRounded'
import TrendingFlatRoundedIcon from '@mui/icons-material/TrendingFlatRounded'
import TrendingUpRoundedIcon from '@mui/icons-material/TrendingUpRounded'
import StarRoundedIcon from '@mui/icons-material/StarRounded'
import StorefrontRoundedIcon from '@mui/icons-material/StorefrontRounded'
import UpdateRoundedIcon from '@mui/icons-material/UpdateRounded'
import VisibilityRoundedIcon from '@mui/icons-material/VisibilityRounded'
import WarningAmberRoundedIcon from '@mui/icons-material/WarningAmberRounded'
import {
  Avatar,
  Box,
  Chip,
  CircularProgress,
  Collapse,
  Dialog,
  DialogContent,
  Divider,
  IconButton,
  LinearProgress,
  Skeleton,
  Slide,
  Tooltip,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material'
import type { TransitionProps } from '@mui/material/transitions'
import { forwardRef, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useAuth } from '../../app/providers/AuthProvider'
import { aiCornerIcon, aiIcon } from '../../shared/assets/icons'
import { Button } from '../../shared/ui/Button'
import { Card } from '../../shared/ui/Card'
import { getJson, postJson } from '../../shared/utils/api'
import { getApiBase } from '../../shared/utils/apiBase'
import { formatNumberCompact } from '../../shared/utils/format'
import type { ChannelData } from './MyChannelsPage'

type ChannelDetailDialogProps = {
  open: boolean
  onClose: () => void
  channel: ChannelData | null
  onOpenSettings: (channel: ChannelData) => void
  onPublishToMarket: (channel: ChannelData) => void
  onChannelUpdated?: () => void
}

const Transition = forwardRef(function Transition(
  props: TransitionProps & { children: React.ReactElement },
  ref: React.Ref<unknown>
) {
  return <Slide direction="up" ref={ref} {...props} />
})

type ChartPeriod = '7d' | '30d' | '90d'

type BestPost = {
  messageId: number | null
  views: number
  reactions: number
  comments: number
  shares: number
  text: string | null
  fullText: string | null
  hasMedia: boolean
  mediaUrl: string | null
  isAlbum?: boolean
  mediaCount?: number
}

type ChannelStatsData = {
  subscriberCount: number
  subscriberGrowth24h: number
  subscriberGrowth7d: number
  subscriberGrowth30d: number
  avgPostViews: number
  avgReach24h: number
  totalViews24h: number
  totalViews7d: number
  engagementRate: number
  avgReactions: number
  avgComments: number
  avgShares: number
  // Totals
  totalReactions: number
  totalComments: number
  totalShares: number
  // Posts by period
  posts24h: number
  posts7d: number
  posts30d: number
  posts90d: number
  avgPostsPerDay: number
  // Best post
  bestPost: BestPost | null
  dynamics: 'growing' | 'stable' | 'declining'
  dynamicsScore: number
  lastPostAt: string | null
  updatedAt: string
  // Collection status
  isCollecting: boolean
  collectionStartedAt: string | null
  collectionError: string | null
}

type StatsHistoryPoint = {
  date: string
  subscriberCount: number
  totalViews: number
  totalPosts: number
  avgPostViews: number
  engagementRate: number
  reactions: number
  comments: number
  shares: number
}

type StatsHistoryData = {
  channelId: number
  period: string
  data: StatsHistoryPoint[]
}

// AI Insights types
type AIRating = {
  score: number
  explanation: string
}

type AIGrowthForecast = {
  subscribers30d: string
  percentage: string
  explanation: string
}

type AIAdvertisingRecommendation = {
  whyBuyAds: string
  bestFor: string[]
  audienceQuality: 'высокая' | 'средняя' | 'низкая'
}

type AIInsightsData = {
  category: string
  targetAudience: string
  rating: AIRating
  strengths: string[]
  weaknesses: string[]
  growthForecast: AIGrowthForecast
  advertisingRecommendation: AIAdvertisingRecommendation
  contentTips: string[]
}

export function ChannelDetailDialog({
  open,
  onClose,
  channel,
  onOpenSettings,
  onPublishToMarket,
  onChannelUpdated,
}: ChannelDetailDialogProps) {
  const { t } = useTranslation()
  const { token } = useAuth()
  const theme = useTheme()
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'))

  const [chartPeriod, setChartPeriod] = useState<ChartPeriod>('30d')
  const [activeChart, setActiveChart] = useState<'subscribers' | 'views' | 'posts'>('subscribers')
  const [stats, setStats] = useState<ChannelStatsData | null>(null)
  const [history, setHistory] = useState<StatsHistoryData | null>(null)
  const [loadingStats, setLoadingStats] = useState(false)
  const [loadingChart, setLoadingChart] = useState(false)
  const [isInitialLoad, setIsInitialLoad] = useState(true)
  const [bestPostExpanded, setBestPostExpanded] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [localChannel, setLocalChannel] = useState<ChannelData | null>(channel)
  const [hasAnyEnabledFormats, setHasAnyEnabledFormats] = useState<boolean | null>(null)

  // AI Insights state
  const [aiInsights, setAiInsights] = useState<AIInsightsData | null>(null)
  const [loadingAI, setLoadingAI] = useState(false)
  const [aiError, setAiError] = useState<string | null>(null)
  const [showAI, setShowAI] = useState(false)
  
  // Update local channel when prop changes
  useEffect(() => {
    if (channel) {
      setLocalChannel({ ...channel }) // Create new object to trigger re-render
    }
  }, [channel?.id, channel?.title, channel?.username, channel?.photoUrl])

  // Reset initial load when dialog opens
  useEffect(() => {
    if (open) {
      setIsInitialLoad(true)
      setHasAnyEnabledFormats(null)
    }
  }, [open, channel?.id])

  // Fetch full channel (with adFormats) when dialog opens for non-published channel
  useEffect(() => {
    if (!open || !channel || !token) return
    const isPub = channel.isVisible && channel.status === 'active'
    if (isPub) {
      setHasAnyEnabledFormats(true) // already published, no need to check
      return
    }
    const fetchFormats = async () => {
      try {
        const base = getApiBase()
        if (!base) return
        const data = await getJson<{ adFormats: Array<{ isEnabled: boolean }> }>(
          `${base}/api/channels/${channel.id}`,
          { headers: { Authorization: `Bearer ${token}` } }
        )
        setHasAnyEnabledFormats((data.adFormats ?? []).some((f) => f.isEnabled))
      } catch {
        setHasAnyEnabledFormats(null)
      }
    }
    void fetchFormats()
  }, [open, channel, token])

  // Fetch stats when dialog opens or period changes
  useEffect(() => {
    if (!open || !channel || !token) return

    const fetchStats = async () => {
      // Only show loading skeleton on initial load
      if (isInitialLoad) {
        setLoadingStats(true)
      }
      try {
        const base = getApiBase()
        if (!base) return

        const statsData = await getJson<ChannelStatsData>(`${base}/api/channels/${channel.id}/stats?period=${chartPeriod}`, {
          headers: { Authorization: `Bearer ${token}` },
        })

        setStats(statsData)
      } catch (e) {
        console.error('Failed to fetch channel stats:', e)
      } finally {
        setLoadingStats(false)
        setIsInitialLoad(false)
      }
    }

    void fetchStats()
  }, [open, channel, token, chartPeriod, isInitialLoad])

  // Fetch chart history when dialog opens or period changes
  useEffect(() => {
    if (!open || !channel || !token) return

    const fetchHistory = async () => {
      // Only show loading skeleton on initial load
      if (isInitialLoad) {
        setLoadingChart(true)
      }
      try {
        const base = getApiBase()
        if (!base) return

        const historyData = await getJson<StatsHistoryData>(`${base}/api/channels/${channel.id}/stats/history?period=${chartPeriod}`, {
          headers: { Authorization: `Bearer ${token}` },
        })

        setHistory(historyData)
      } catch (e) {
        console.error('Failed to fetch channel history:', e)
      } finally {
        setLoadingChart(false)
      }
    }

    void fetchHistory()
  }, [open, channel, token, chartPeriod, isInitialLoad])

  // Fetch AI insights
  const fetchAIInsights = async () => {
    if (!channel || !token) return

    setLoadingAI(true)
    setAiError(null)
    
    try {
      const base = getApiBase()
      if (!base) return

      const response = await getJson<{ ok: boolean; data?: AIInsightsData; error?: string }>(
        `${base}/api/channels/${channel.id}/ai-insights-structured`,
        { headers: { Authorization: `Bearer ${token}` } }
      )

      if (response.ok && response.data) {
        setAiInsights(response.data)
        setShowAI(true)
      } else {
        setAiError(response.error || 'Failed to generate AI insights')
      }
    } catch (e) {
      console.error('Failed to fetch AI insights:', e)
      setAiError('Failed to connect to AI service')
    } finally {
      setLoadingAI(false)
    }
  }

  // Refresh channel stats
  const handleRefreshStats = async () => {
    if (!channel || !token || refreshing) return

    setRefreshing(true)
    
    try {
      const base = getApiBase()
      if (!base) return

      // Trigger stats refresh on backend (this also updates channel info: title, username, photo)
      await postJson(`${base}/api/channels/${channel.id}/stats/refresh`, {}, {
        headers: { Authorization: `Bearer ${token}` },
      })

      // Wait a bit for backend to finish updating
      await new Promise(resolve => setTimeout(resolve, 1000))
      
      // Refetch channel data to get updated title, username, photo
      const channelData = await getJson<ChannelData>(`${base}/api/channels/${channel.id}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      
      console.log('Before update - Channel:', {
        title: channel?.title,
        username: channel?.username,
        photoUrl: channel?.photoUrl?.substring(0, 50)
      })
      console.log('After update - Channel data:', {
        title: channelData.title,
        username: channelData.username,
        photoUrl: channelData.photoUrl?.substring(0, 50)
      })
      
      // Update local channel state (without triggering page refresh)
      if (channelData) {
        setLocalChannel({ ...channelData }) // Create new object to force re-render
      }
      
      // Silently update parent component's channel list (without visible refresh)
      if (onChannelUpdated) {
        // Use setTimeout to avoid blocking UI
        setTimeout(() => {
          onChannelUpdated()
        }, 100)
      }

      // Refetch stats and history after a short delay to get updated data
      setTimeout(async () => {
        try {
          const statsData = await getJson<ChannelStatsData>(`${base}/api/channels/${channel.id}/stats?period=${chartPeriod}`, {
            headers: { Authorization: `Bearer ${token}` },
          })
          setStats(statsData)

          const historyData = await getJson<StatsHistoryData>(`${base}/api/channels/${channel.id}/stats/history?period=${chartPeriod}`, {
            headers: { Authorization: `Bearer ${token}` },
          })
          setHistory(historyData)
        } catch (e) {
          console.error('Failed to refetch stats after refresh:', e)
        } finally {
          setRefreshing(false)
        }
      }, 2000)
    } catch (e) {
      console.error('Failed to refresh stats:', e)
      setRefreshing(false)
    }
  }

  // Format chart data from history
  const chartData = useMemo(() => {
    if (!history?.data?.length) return []

    return history.data.map((point) => ({
      date: new Date(point.date).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' }),
      subscribers: point.subscriberCount,
      views: point.totalViews,
      posts: point.totalPosts,
    }))
  }, [history])

  // Get growth based on period
  const getGrowth = () => {
    if (!stats) return 0
    switch (chartPeriod) {
      case '7d':
        return stats.subscriberGrowth7d
      case '30d':
        return stats.subscriberGrowth30d
      default:
        return stats.subscriberGrowth24h
    }
  }

  // Get posts count based on period (backend now returns for selected period)
  const getPostsCount = () => {
    if (!stats) return 0
    // Backend returns posts count for the selected period in posts90d field when period=90d
    // Otherwise use the period-specific field
    switch (chartPeriod) {
      case '7d':
        return stats.posts7d
      case '30d':
        return stats.posts30d
      case '90d':
        return stats.posts90d
      default:
        return stats.posts30d
    }
  }

  // Format updated time
  const formatUpdatedAt = () => {
    if (!stats?.updatedAt) return null
    const date = new Date(stats.updatedAt)
    return date.toLocaleString('ru-RU', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  // Format Telegram MarkdownV2 text to HTML
  const formatTelegramText = (text: string): string => {
    if (!text) return ''
    
    // Escape HTML first
    let html = text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
    
    // Bold: **text** or *text* (Telegram uses both)
    html = html.replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
    html = html.replace(/\*([^*]+)\*/g, '<b>$1</b>')
    
    // Italic: __text__ or _text_
    html = html.replace(/__([^_]+)__/g, '<i>$1</i>')
    html = html.replace(/_([^_]+)_/g, '<i>$1</i>')
    
    // Strikethrough: ~~text~~
    html = html.replace(/~~([^~]+)~~/g, '<del>$1</del>')
    
    // Code: `text`
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>')
    
    // Links: [text](url)
    html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
    
    // New lines
    html = html.replace(/\n/g, '<br/>')
    
    return html
  }

  if (!channel) return null

  const isPublished = channel.isVisible && channel.status === 'active'

  return (
    <Dialog
      open={open}
      onClose={onClose}
      fullScreen={isMobile}
      fullWidth
      maxWidth="sm"
      TransitionComponent={Transition}
      PaperProps={{
        sx: {
          borderRadius: isMobile ? 0 : 3,
          maxHeight: isMobile ? '100%' : '90vh',
        },
      }}
    >
      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          gap: 1.5,
          p: 2,
          borderBottom: 1,
          borderColor: 'divider',
          position: 'sticky',
          top: 0,
          bgcolor: 'background.paper',
          zIndex: 1,
        }}
      >
        <IconButton onClick={onClose} edge="start" size="small">
          <CloseRoundedIcon />
        </IconButton>

        <Avatar
          src={(localChannel?.photoUrl || channel?.photoUrl) ? `${getApiBase()}/api/media/channel-photo/${localChannel?.id || channel?.id}` : undefined}
          sx={{ width: 40, height: 40, bgcolor: 'primary.main' }}
        >
          {(localChannel?.title || channel?.title)?.[0] || '?'}
        </Avatar>

        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography
            sx={{
              fontWeight: 800,
              fontSize: 16,
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {localChannel?.title || channel?.title || ''}
          </Typography>
          {(localChannel?.username || channel?.username) && (
            <Typography variant="body2" color="text.secondary">
              @{localChannel?.username || channel?.username}
            </Typography>
          )}
        </Box>

        <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center' }}>
          {refreshing && (
            <Typography variant="caption" color="text.secondary" sx={{ mr: 0.5, fontSize: 11 }}>
              {t('channelDetail.collectingData')}
            </Typography>
          )}
          <IconButton
            onClick={handleRefreshStats}
            disabled={refreshing || stats?.isCollecting}
            title={t('channelDetail.refreshStats')}
            sx={{ 
              bgcolor: refreshing ? 'action.selected' : 'action.hover',
              animation: refreshing ? 'spin 1s linear infinite' : 'none',
              '@keyframes spin': {
                '0%': { transform: 'rotate(0deg)' },
                '100%': { transform: 'rotate(360deg)' },
              },
            }}
          >
            <RefreshRoundedIcon />
          </IconButton>
          <IconButton
            onClick={() => onOpenSettings(channel)}
            sx={{ bgcolor: 'action.hover' }}
          >
            <SettingsRoundedIcon />
          </IconButton>
        </Box>
      </Box>

      <DialogContent sx={{ p: 2 }}>
        {/* Collecting Banner */}
        {stats?.isCollecting && (
          <Card sx={{ mb: 2, bgcolor: 'info.main', color: 'info.contrastText' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
              <CircularProgress size={20} color="inherit" />
              <Box sx={{ flex: 1 }}>
                <Typography sx={{ fontWeight: 700 }}>
                  {t('channelDetail.collectingData')}
                </Typography>
                <Typography variant="body2" sx={{ opacity: 0.8 }}>
                  {t('channelDetail.collectingDescription')}
                </Typography>
              </Box>
            </Box>
            <LinearProgress 
              color="inherit" 
              sx={{ mt: 1, borderRadius: 1, opacity: 0.5 }} 
            />
          </Card>
        )}

        {loadingStats ? (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
            <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 1.5 }}>
              <Skeleton variant="rounded" height={90} />
              <Skeleton variant="rounded" height={90} />
              <Skeleton variant="rounded" height={90} />
            </Box>
            <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 1.5 }}>
              <Skeleton variant="rounded" height={90} />
              <Skeleton variant="rounded" height={90} />
              <Skeleton variant="rounded" height={90} />
            </Box>
            <Skeleton variant="rounded" height={200} />
          </Box>
        ) : (
          <>
            {/* Hero Stats - Main Metrics */}
            <Box
              sx={{
                p: 2,
                mb: 2,
                borderRadius: 3,
                background: theme.palette.mode === 'dark' 
                  ? 'linear-gradient(135deg, rgba(16,185,129,0.12) 0%, rgba(20,184,166,0.08) 100%)'
                  : 'linear-gradient(135deg, rgba(16,185,129,0.08) 0%, rgba(20,184,166,0.04) 100%)',
                border: `1px solid ${theme.palette.divider}`,
                position: 'relative',
              }}
            >
              {/* AI Button - Top Left */}
              <IconButton
                onClick={() => {
                  if (!loadingAI) {
                    if (!aiInsights) {
                      fetchAIInsights()
                    }
                    setShowAI(true)
                  }
                }}
                sx={{
                  position: 'absolute',
                  top: 20,
                  left: 20,
                  width: 60,
                  height: 60,
                  background: 'linear-gradient(135deg, #10b981 0%, #14b8a6 50%, #06b6d4 100%)',
                  borderRadius: 2,
                  '&:hover': {
                    background: 'linear-gradient(135deg, #059669 0%, #0d9488 50%, #0891b2 100%)',
                    transform: 'scale(1.05)',
                  },
                  transition: 'all 0.2s ease-out',
                }}
              >
                {loadingAI ? (
                  <CircularProgress size={20} sx={{ color: 'white' }} />
                ) : (
                  <Box
                    component="img"
                    src={aiIcon}
                    alt="AI"
                    sx={{ width: 24, height: 24, filter: 'brightness(0) invert(1)' }}
                  />
                )}
              </IconButton>

              {/* Main number - Subscribers */}
              <Box sx={{ textAlign: 'center', mb: 2 }}>
                <Typography 
                  sx={{ 
                    fontWeight: 900, 
                    fontSize: 42,
                    background: 'linear-gradient(135deg, #10b981 0%, #14b8a6 100%)',
                    WebkitBackgroundClip: 'text',
                    WebkitTextFillColor: 'transparent',
                    lineHeight: 1,
                  }}
                >
                  {formatNumberCompact(stats?.subscriberCount ?? channel.subscriberCount)}
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                  {t('channelDetail.subscribers')}
                </Typography>
              </Box>

              {/* Secondary stats row */}
              <Box sx={{ display: 'flex', justifyContent: 'space-around' }}>
                {/* Growth */}
                <Box sx={{ textAlign: 'center' }}>
                  {(() => {
                    const growth = getGrowth()
                    const color = growth > 0 ? '#10b981' : growth < 0 ? '#ef4444' : 'text.secondary'
                    return (
                      <>
                        <Typography 
                          sx={{ 
                            fontWeight: 800, 
                            fontSize: 20, 
                            color,
                            transition: 'all 0.4s ease-out',
                          }}
                        >
                          {growth >= 0 ? '+' : ''}{formatNumberCompact(growth)}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {t('channelDetail.growth')}
                        </Typography>
                      </>
                    )
                  })()}
                </Box>

                <Divider orientation="vertical" flexItem />

                {/* Avg Views */}
                <Box sx={{ textAlign: 'center' }}>
                  <Typography 
                    sx={{ 
                      fontWeight: 800, 
                      fontSize: 20, 
                      color: '#059669',
                      transition: 'all 0.4s ease-out',
                    }}
                  >
                    {formatNumberCompact(stats?.avgPostViews ?? 0)}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {t('channelDetail.avgViews')}
                  </Typography>
                </Box>

                <Divider orientation="vertical" flexItem />

                {/* ER */}
                <Box sx={{ textAlign: 'center' }}>
                  <Typography 
                    sx={{ 
                      fontWeight: 800, 
                      fontSize: 20, 
                      color: '#14b8a6',
                      transition: 'all 0.4s ease-out',
                    }}
                  >
                    {stats?.engagementRate?.toFixed(1) ?? '0'}%
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    ER
                  </Typography>
                </Box>
              </Box>
            </Box>

            {/* Activity Stats - Compact Row */}
            <Card 
              sx={{ 
                mb: 2, 
                p: 0, 
                overflow: 'hidden',
                border: `1px solid ${theme.palette.divider}`,
              }}
            >
              <Box sx={{ display: 'flex' }}>
                {/* Reach 24h */}
                <Box 
                  sx={{ 
                    flex: 1, 
                    py: 1.5, 
                    textAlign: 'center',
                    borderRight: `1px solid ${theme.palette.divider}`,
                  }}
                >
                  <VisibilityRoundedIcon sx={{ fontSize: 18, color: '#10b981', mb: 0.25 }} />
                  <Typography sx={{ fontWeight: 800, fontSize: 15, transition: 'all 0.4s ease-out' }}>
                    {formatNumberCompact(stats?.avgReach24h ?? 0)}
                  </Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ fontSize: 10 }}>
                    {t('channelDetail.reach24h')}
                  </Typography>
                </Box>

                {/* Posts per Day */}
                <Box 
                  sx={{ 
                    flex: 1, 
                    py: 1.5, 
                    textAlign: 'center',
                    borderRight: `1px solid ${theme.palette.divider}`,
                  }}
                >
                  <SpeedRoundedIcon sx={{ fontSize: 18, color: '#059669', mb: 0.25 }} />
                  <Typography sx={{ fontWeight: 800, fontSize: 15, transition: 'all 0.4s ease-out' }}>
                    {stats?.avgPostsPerDay?.toFixed(1) ?? '0'}
                  </Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ fontSize: 10 }}>
                    {t('channelDetail.postsPerDay')}
                  </Typography>
                </Box>

                {/* Total Posts */}
                <Box 
                  sx={{ 
                    flex: 1, 
                    py: 1.5, 
                    textAlign: 'center',
                    borderRight: `1px solid ${theme.palette.divider}`,
                  }}
                >
                  <ArticleRoundedIcon sx={{ fontSize: 18, color: '#047857', mb: 0.25 }} />
                  <Typography sx={{ fontWeight: 800, fontSize: 15, transition: 'all 0.4s ease-out' }}>
                    {getPostsCount()}
                  </Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ fontSize: 10 }}>
                    {t('channelDetail.posts')}
                  </Typography>
                </Box>

                {/* Dynamics */}
                <Box 
                  sx={{ 
                    flex: 1, 
                    py: 1.5, 
                    textAlign: 'center',
                  }}
                >
                  {stats?.dynamics === 'growing' ? (
                    <TrendingUpRoundedIcon sx={{ fontSize: 18, color: '#10b981', mb: 0.25 }} />
                  ) : stats?.dynamics === 'declining' ? (
                    <TrendingDownRoundedIcon sx={{ fontSize: 18, color: '#ef4444', mb: 0.25 }} />
                  ) : (
                    <TrendingFlatRoundedIcon sx={{ fontSize: 18, color: '#6b7280', mb: 0.25 }} />
                  )}
                  <Typography 
                    sx={{ 
                      fontWeight: 800, 
                      fontSize: 15,
                      color: stats?.dynamics === 'growing' ? '#10b981' : stats?.dynamics === 'declining' ? '#ef4444' : 'text.primary',
                      transition: 'all 0.4s ease-out',
                    }}
                  >
                    {t(`channelDetail.dynamics.${stats?.dynamics ?? 'stable'}`)}
                  </Typography>
                  <Typography variant="caption" color="text.secondary" sx={{ fontSize: 10 }}>
                    {t('channelDetail.dynamicsLabel')}
                  </Typography>
                </Box>
              </Box>
            </Card>

            {/* Engagement Row - Compact */}
            <Card 
              sx={{ 
                mb: 2, 
                p: 0, 
                overflow: 'hidden',
                border: `1px solid ${theme.palette.divider}`,
              }}
            >
              {/* Header */}
              <Box 
                sx={{ 
                  px: 1.5, 
                  py: 0.75, 
                  background: theme.palette.mode === 'dark' 
                    ? 'linear-gradient(90deg, rgba(16,185,129,0.15) 0%, rgba(20,184,166,0.1) 100%)'
                    : 'linear-gradient(90deg, rgba(16,185,129,0.1) 0%, rgba(20,184,166,0.05) 100%)',
                  borderBottom: `1px solid ${theme.palette.divider}`,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
              >
                <Typography variant="caption" sx={{ fontWeight: 700, color: '#059669' }}>
                  {t('channelDetail.engagementRate')}
                </Typography>
                <Chip 
                  label={`${stats?.engagementRate?.toFixed(1) ?? '0'}%`}
                  size="small"
                  sx={{ 
                    height: 20, 
                    fontSize: 11, 
                    fontWeight: 700,
                    bgcolor: '#10b981',
                    color: 'white',
                  }}
                />
              </Box>
              
              {/* Stats Row */}
              <Box sx={{ display: 'flex' }}>
                <Box 
                  sx={{ 
                    flex: 1, 
                    py: 1.5, 
                    textAlign: 'center',
                    borderRight: `1px solid ${theme.palette.divider}`,
                  }}
                >
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.5, mb: 0.25 }}>
                    <FavoriteRoundedIcon sx={{ fontSize: 14, color: '#10b981' }} />
                    <Typography sx={{ fontWeight: 800, fontSize: 14, transition: 'all 0.4s ease-out' }}>
                      {formatNumberCompact(stats?.totalReactions ?? 0)}
                    </Typography>
                  </Box>
                  <Typography variant="caption" color="text.secondary" sx={{ fontSize: 9 }}>
                    {t('channelDetail.reactions')}
                  </Typography>
                </Box>

                <Box 
                  sx={{ 
                    flex: 1, 
                    py: 1.5, 
                    textAlign: 'center',
                    borderRight: `1px solid ${theme.palette.divider}`,
                  }}
                >
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.5, mb: 0.25 }}>
                    <ChatBubbleOutlineRoundedIcon sx={{ fontSize: 14, color: '#14b8a6' }} />
                    <Typography sx={{ fontWeight: 800, fontSize: 14, transition: 'all 0.4s ease-out' }}>
                      {formatNumberCompact(stats?.totalComments ?? 0)}
                    </Typography>
                  </Box>
                  <Typography variant="caption" color="text.secondary" sx={{ fontSize: 9 }}>
                    {t('channelDetail.comments')}
                  </Typography>
                </Box>

                <Box 
                  sx={{ 
                    flex: 1, 
                    py: 1.5, 
                    textAlign: 'center',
                    borderRight: `1px solid ${theme.palette.divider}`,
                  }}
                >
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.5, mb: 0.25 }}>
                    <ShareRoundedIcon sx={{ fontSize: 14, color: '#059669' }} />
                    <Typography sx={{ fontWeight: 800, fontSize: 14, transition: 'all 0.4s ease-out' }}>
                      {formatNumberCompact(stats?.totalShares ?? 0)}
                    </Typography>
                  </Box>
                  <Typography variant="caption" color="text.secondary" sx={{ fontSize: 9 }}>
                    {t('channelDetail.shares')}
                  </Typography>
                </Box>

                <Box 
                  sx={{ 
                    flex: 1, 
                    py: 1.5, 
                    textAlign: 'center',
                  }}
                >
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.5, mb: 0.25 }}>
                    <VisibilityRoundedIcon sx={{ fontSize: 14, color: '#047857' }} />
                    <Typography sx={{ fontWeight: 800, fontSize: 14, transition: 'all 0.4s ease-out' }}>
                      {formatNumberCompact(stats?.totalViews24h ?? 0)}
                    </Typography>
                  </Box>
                  <Typography variant="caption" color="text.secondary" sx={{ fontSize: 9 }}>
                    24h
                  </Typography>
                </Box>
              </Box>
            </Card>

            {/* Chart Section */}
            <Box 
              sx={{ 
                mb: 2,
                p: 2,
                borderRadius: 3,
                bgcolor: theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.02)',
                border: `1px solid ${theme.palette.divider}`,
              }}
            >
              {/* Header with period selector */}
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  mb: 2,
                }}
              >
                <Typography sx={{ fontWeight: 700 }}>{t('channelDetail.analytics')}</Typography>
                <ToggleButtonGroup
                  value={chartPeriod}
                  exclusive
                  onChange={(_, val) => val && setChartPeriod(val)}
                  size="small"
                  sx={{
                    '& .MuiToggleButton-root': {
                      px: 1.5,
                      py: 0.25,
                      fontSize: 11,
                      borderRadius: '12px !important',
                      border: 'none',
                      '&.Mui-selected': {
                        bgcolor: 'primary.main',
                        color: 'white',
                        '&:hover': { bgcolor: 'primary.dark' },
                      },
                    },
                  }}
                >
                  <ToggleButton value="7d">7д</ToggleButton>
                  <ToggleButton value="30d">30д</ToggleButton>
                  <ToggleButton value="90d">90д</ToggleButton>
                </ToggleButtonGroup>
              </Box>

              {/* Chart Type Toggle */}
              <Box sx={{ display: 'flex', gap: 1, mb: 2, flexWrap: 'wrap', justifyContent: 'center' }}>
                <Chip
                  icon={<GroupsRoundedIcon sx={{ fontSize: 16 }} />}
                  label={t('channelDetail.subscribers')}
                  onClick={() => setActiveChart('subscribers')}
                  variant={activeChart === 'subscribers' ? 'filled' : 'outlined'}
                  size="small"
                  sx={{
                    bgcolor: activeChart === 'subscribers' ? '#6366f1' : 'transparent',
                    color: activeChart === 'subscribers' ? 'white' : 'text.primary',
                    borderColor: activeChart === 'subscribers' ? '#6366f1' : 'divider',
                    '&:hover': { bgcolor: activeChart === 'subscribers' ? '#4f46e5' : 'action.hover' },
                  }}
                />
                <Chip
                  icon={<VisibilityRoundedIcon sx={{ fontSize: 16 }} />}
                  label={t('channelDetail.views')}
                  onClick={() => setActiveChart('views')}
                  variant={activeChart === 'views' ? 'filled' : 'outlined'}
                  size="small"
                  sx={{
                    bgcolor: activeChart === 'views' ? '#f59e0b' : 'transparent',
                    color: activeChart === 'views' ? 'white' : 'text.primary',
                    borderColor: activeChart === 'views' ? '#f59e0b' : 'divider',
                    '&:hover': { bgcolor: activeChart === 'views' ? '#d97706' : 'action.hover' },
                  }}
                />
                <Chip
                  icon={<ArticleRoundedIcon sx={{ fontSize: 16 }} />}
                  label={t('channelDetail.posts')}
                  onClick={() => setActiveChart('posts')}
                  variant={activeChart === 'posts' ? 'filled' : 'outlined'}
                  size="small"
                  sx={{
                    bgcolor: activeChart === 'posts' ? '#10b981' : 'transparent',
                    color: activeChart === 'posts' ? 'white' : 'text.primary',
                    borderColor: activeChart === 'posts' ? '#10b981' : 'divider',
                    '&:hover': { bgcolor: activeChart === 'posts' ? '#059669' : 'action.hover' },
                  }}
                />
              </Box>

              {/* Chart */}
              <Box 
                sx={{ 
                  height: 180,
                  width: '100%',
                  minHeight: 180,
                  minWidth: 0,
                  position: 'relative',
                  transition: 'opacity 0.3s ease-out',
                  opacity: loadingChart ? 0.5 : 1,
                }}
              >
                {loadingChart ? (
                  <Skeleton variant="rounded" width="100%" height="100%" />
                ) : chartData.length > 0 ? (
                  <ResponsiveContainer width="100%" height="100%" minHeight={180} minWidth={0}>
                    <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                      <defs>
                        <linearGradient id="colorSubscribers" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                          <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                        </linearGradient>
                        <linearGradient id="colorViews" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.3} />
                          <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                        </linearGradient>
                        <linearGradient id="colorPosts" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                          <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke={theme.palette.divider} vertical={false} />
                      <XAxis
                        dataKey="date"
                        tick={{ fontSize: 9, fill: theme.palette.text.secondary }}
                        tickLine={false}
                        axisLine={false}
                      />
                      <YAxis
                        tick={{ fontSize: 9, fill: theme.palette.text.secondary }}
                        tickLine={false}
                        axisLine={false}
                        tickFormatter={(value: number) => formatNumberCompact(value)}
                      />
                      <RechartsTooltip
                        contentStyle={{
                          backgroundColor: theme.palette.background.paper,
                          borderColor: theme.palette.divider,
                          borderRadius: 8,
                          fontSize: 12,
                        }}
                        formatter={(value) => [
                          formatNumberCompact(value as number), 
                          activeChart === 'subscribers' 
                            ? t('channelDetail.subscribers') 
                            : activeChart === 'views' 
                              ? t('channelDetail.views') 
                              : t('channelDetail.posts')
                        ]}
                      />
                      {activeChart === 'subscribers' && (
                        <Area
                          type="monotone"
                          dataKey="subscribers"
                          stroke="#6366f1"
                          strokeWidth={2}
                          fillOpacity={1}
                          fill="url(#colorSubscribers)"
                          animationDuration={600}
                          animationEasing="ease-out"
                        />
                      )}
                      {activeChart === 'views' && (
                        <Area
                          type="monotone"
                          dataKey="views"
                          stroke="#f59e0b"
                          strokeWidth={2}
                          fillOpacity={1}
                          fill="url(#colorViews)"
                          animationDuration={600}
                          animationEasing="ease-out"
                        />
                      )}
                      {activeChart === 'posts' && (
                        <Area
                          type="monotone"
                          dataKey="posts"
                          stroke="#10b981"
                          strokeWidth={2}
                          fillOpacity={1}
                          fill="url(#colorPosts)"
                          animationDuration={600}
                          animationEasing="ease-out"
                        />
                      )}
                    </AreaChart>
                  </ResponsiveContainer>
                ) : (
                  <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%' }}>
                    <Typography variant="body2" color="text.secondary">
                      {t('channelDetail.noData')}
                    </Typography>
                  </Box>
                )}
              </Box>
            </Box>

            {/* Best Post */}
            {stats?.bestPost && (
              <Card
                clickable
                onClick={() => setBestPostExpanded((prev) => !prev)}
                disableContentPadding
                sx={{
                  mb: 2,
                  p: 0,
                  overflow: 'hidden',
                  border: `1px solid ${theme.palette.divider}`,
                  transition: 'all 0.2s',
                  '&:hover': { 
                    boxShadow: theme.shadows[2],
                  },
                }}
              >
                {/* Media at top (if exists and collapsed) */}
                {stats.bestPost.mediaUrl && !bestPostExpanded && (
                  <Box
                    sx={{
                      position: 'relative',
                      height: 120,
                      overflow: 'hidden',
                    }}
                  >
                    <Box
                      component="img"
                      src={`${getApiBase()}${stats.bestPost.mediaUrl}`}
                      alt="Post media"
                      sx={{
                        width: '100%',
                        height: '100%',
                        objectFit: 'cover',
                      }}
                      onError={(e) => {
                        (e.target as HTMLImageElement).style.display = 'none'
                      }}
                    />
                    {/* Gradient overlay */}
                    <Box
                      sx={{
                        position: 'absolute',
                        bottom: 0,
                        left: 0,
                        right: 0,
                        height: 60,
                        background: 'linear-gradient(transparent, rgba(0,0,0,0.6))',
                      }}
                    />
                    {/* Views badge on image */}
                    <Box
                      sx={{
                        position: 'absolute',
                        top: 8,
                        right: 8,
                        display: 'flex',
                        alignItems: 'center',
                        gap: 0.5,
                        px: 1,
                        py: 0.25,
                        borderRadius: 1,
                        bgcolor: 'rgba(0,0,0,0.6)',
                        backdropFilter: 'blur(4px)',
                      }}
                    >
                      <VisibilityRoundedIcon sx={{ fontSize: 14, color: 'white' }} />
                      <Typography sx={{ fontSize: 12, fontWeight: 700, color: 'white' }}>
                        {formatNumberCompact(stats.bestPost.views)}
                      </Typography>
                    </Box>
                    {/* Best post badge */}
                    <Box
                      sx={{
                        position: 'absolute',
                        top: 8,
                        left: 8,
                        display: 'flex',
                        alignItems: 'center',
                        gap: 0.5,
                        px: 1,
                        py: 0.25,
                        borderRadius: 1,
                        bgcolor: '#f59e0b',
                      }}
                    >
                      <AutoAwesomeRoundedIcon sx={{ fontSize: 12, color: 'white' }} />
                      <Typography sx={{ fontSize: 10, fontWeight: 700, color: 'white' }}>
                        {t('channelDetail.bestPost')}
                      </Typography>
                    </Box>
                    {/* Album badge */}
                    {stats.bestPost.isAlbum && (
                      <Box
                        sx={{
                          position: 'absolute',
                          bottom: 8,
                          right: 8,
                          display: 'flex',
                          alignItems: 'center',
                          gap: 0.5,
                          px: 1,
                          py: 0.25,
                          borderRadius: 1,
                          bgcolor: 'rgba(0,0,0,0.6)',
                          backdropFilter: 'blur(4px)',
                        }}
                      >
                        <CollectionsRoundedIcon sx={{ fontSize: 12, color: 'white' }} />
                        <Typography sx={{ fontSize: 10, fontWeight: 600, color: 'white' }}>
                          {stats.bestPost.mediaCount || 1}
                        </Typography>
                      </Box>
                    )}
                  </Box>
                )}

                {/* Header when no media or expanded */}
                {(!stats.bestPost.mediaUrl || bestPostExpanded) && (
                  <Box
                    sx={{
                      px: 2,
                      py: 1.5,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      borderBottom: bestPostExpanded ? 1 : 0,
                      borderColor: 'divider',
                      bgcolor: theme.palette.mode === 'dark' ? 'rgba(245,158,11,0.1)' : 'rgba(245,158,11,0.05)',
                    }}
                  >
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <AutoAwesomeRoundedIcon sx={{ color: '#f59e0b', fontSize: 18 }} />
                      <Typography variant="body2" sx={{ fontWeight: 700, color: '#f59e0b' }}>
                        {t('channelDetail.bestPost')}
                      </Typography>
                      {/* Album indicator in header */}
                      {stats.bestPost.isAlbum && (
                        <Chip
                          icon={<CollectionsRoundedIcon sx={{ fontSize: 12 }} />}
                          label={stats.bestPost.mediaCount || 1}
                          size="small"
                          sx={{ 
                            height: 20, 
                            fontSize: 10,
                            '& .MuiChip-icon': { fontSize: 12 },
                          }}
                        />
                      )}
                    </Box>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, color: 'text.secondary' }}>
                        <VisibilityRoundedIcon sx={{ fontSize: 16 }} />
                        <Typography sx={{ fontWeight: 700, fontSize: 14 }}>
                          {formatNumberCompact(stats.bestPost.views)}
                        </Typography>
                      </Box>
                      {bestPostExpanded ? (
                        <ExpandLessRoundedIcon sx={{ fontSize: 20, color: 'text.secondary' }} />
                      ) : (
                        <ExpandMoreRoundedIcon sx={{ fontSize: 20, color: 'text.secondary' }} />
                      )}
                    </Box>
                  </Box>
                )}

                {/* Content */}
                <Box sx={{ p: 2 }}>
                  {/* Preview text (collapsed) */}
                  <Collapse in={!bestPostExpanded}>
                    <Typography
                      variant="body2"
                      color="text.secondary"
                      sx={{
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        display: '-webkit-box',
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: 'vertical',
                        lineHeight: 1.6,
                      }}
                    >
                      {stats.bestPost.text?.replace(/\*\*/g, '').replace(/\*/g, '') || t('channelDetail.mediaPost')}
                    </Typography>
                  </Collapse>

                  {/* Expanded content */}
                  <Collapse in={bestPostExpanded}>
                    {/* Media in expanded view */}
                    {stats.bestPost.mediaUrl && (
                      <Box
                        component="img"
                        src={`${getApiBase()}${stats.bestPost.mediaUrl}`}
                        alt="Post media"
                        sx={{
                          width: '100%',
                          maxHeight: 250,
                          objectFit: 'cover',
                          borderRadius: 2,
                          mb: 2,
                        }}
                        onError={(e) => {
                          (e.target as HTMLImageElement).style.display = 'none'
                        }}
                      />
                    )}
                    
                    <Typography
                      variant="body2"
                      component="div"
                      sx={{
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word',
                        lineHeight: 1.7,
                        '& b': { fontWeight: 700 },
                        '& i': { fontStyle: 'italic' },
                        '& del': { textDecoration: 'line-through' },
                        '& code': { 
                          bgcolor: 'action.hover', 
                          px: 0.5, 
                          borderRadius: 0.5,
                          fontFamily: 'monospace',
                        },
                      }}
                      dangerouslySetInnerHTML={{
                        __html: formatTelegramText(stats.bestPost.fullText || stats.bestPost.text || t('channelDetail.mediaPost'))
                      }}
                    />

                    {/* Go to post link */}
                    {channel.username && stats.bestPost.messageId && (
                      <Box sx={{ mt: 2 }}>
                        <Chip
                          icon={<OpenInNewRoundedIcon sx={{ fontSize: 14 }} />}
                          label={t('channelDetail.goToPost')}
                          size="small"
                          clickable
                          component="a"
                          href={`https://t.me/${channel.username}/${stats.bestPost.messageId}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          onClick={(e: React.MouseEvent) => e.stopPropagation()}
                          sx={{
                            bgcolor: '#f59e0b',
                            color: 'white',
                            '&:hover': { bgcolor: '#d97706' },
                          }}
                        />
                      </Box>
                    )}
                  </Collapse>

                  {/* Stats row at bottom */}
                  <Box sx={{ display: 'flex', gap: 2, mt: 1.5, pt: 1.5, borderTop: 1, borderColor: 'divider' }}>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      <FavoriteRoundedIcon sx={{ fontSize: 14, color: 'error.main' }} />
                      <Typography variant="caption" sx={{ fontWeight: 600 }}>
                        {formatNumberCompact(stats.bestPost.reactions)}
                      </Typography>
                    </Box>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      <ChatBubbleOutlineRoundedIcon sx={{ fontSize: 14, color: 'info.main' }} />
                      <Typography variant="caption" sx={{ fontWeight: 600 }}>
                        {formatNumberCompact(stats.bestPost.comments)}
                      </Typography>
                    </Box>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      <ShareRoundedIcon sx={{ fontSize: 14, color: 'success.main' }} />
                      <Typography variant="caption" sx={{ fontWeight: 600 }}>
                        {formatNumberCompact(stats.bestPost.shares)}
                      </Typography>
                    </Box>
                  </Box>
                </Box>
              </Card>
            )}

            {/* AI Analytics Button */}
            <Box
              onClick={() => {
                if (!loadingAI) {
                  if (!aiInsights) {
                    fetchAIInsights()
                  }
                  setShowAI(true)
                }
              }}
              sx={{
                mb: 2,
                p: '2px', // Padding for gradient border
                borderRadius: 3,
                cursor: loadingAI ? 'wait' : 'pointer',
                position: 'relative',
                overflow: 'hidden',
                background: 'linear-gradient(135deg, #10b981 0%, #14b8a6 50%, #06b6d4 100%)',
                transition: 'all 0.3s ease',
                '&:hover': {
                  transform: 'translateY(-2px)',
                  boxShadow: '0 8px 25px rgba(16,185,129,0.35)',
                },
                '&:active': {
                  transform: 'translateY(0)',
                },
              }}
            >
              {/* Inner content with background */}
              <Box
                sx={{
                  p: 2,
                  borderRadius: 2.5,
                  bgcolor: 'background.paper',
                }}
              >
                {/* AI Corner Badge Icon */}
                <Box
                  sx={{
                    position: 'absolute',
                    top: 0,
                    right: 0,
                    width: 44,
                    height: 44,
                    background: 'linear-gradient(135deg, #10b981 0%, #14b8a6 50%, #06b6d4 100%)',
                    borderRadius: '0 10px 0 100%',
                    boxShadow: '0 2px 8px rgba(16,185,129,0.3)',
                  }}
                >
                  <Box
                    component="img"
                    src={aiCornerIcon}
                    alt="AI"
                    sx={{
                      position: 'absolute',
                      top: 10,
                      right: 10,
                      width: 20,
                      height: 20,
                      filter: 'brightness(0) invert(1)',
                    }}
                  />
                </Box>

                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                  {/* AI Icon */}
                  <Box
                    sx={{
                      width: 56,
                      height: 56,
                      borderRadius: 2.5,
                      background: 'linear-gradient(135deg, #10b981 0%, #14b8a6 50%, #06b6d4 100%)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0,
                    }}
                  >
                    {loadingAI ? (
                      <CircularProgress size={30} sx={{ color: 'white' }} />
                    ) : (
                      <Box
                        component="img"
                        src={aiIcon}
                        alt="AI"
                        sx={{ width: 40, height: 40, filter: 'brightness(0) invert(1)' }}
                      />
                    )}
                  </Box>

                  {/* Text */}
                  <Box sx={{ flex: 1 }}>
                    <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 0.25 }}>
                      {t('channelDetail.aiAnalytics')}
                    </Typography>
                    <Typography variant="body2" sx={{ color: 'text.primary', opacity: 0.7 }}>
                      {loadingAI ? t('channelDetail.aiAnalyzing') : t('channelDetail.aiDescription')}
                    </Typography>
                  </Box>

                  {/* Arrow */}
                  <ExpandMoreRoundedIcon 
                    sx={{ 
                      color: 'text.secondary',
                      transform: 'rotate(-90deg)',
                    }} 
                  />
                </Box>
              </Box>
            </Box>

            {/* AI Error inline */}
            {aiError && !showAI && (
              <Card sx={{ mb: 2, bgcolor: 'error.main', color: 'white' }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <ErrorOutlineRoundedIcon />
                  <Typography variant="body2">{aiError}</Typography>
                </Box>
              </Card>
            )}

            {/* AI Insights Dialog */}
            <Dialog
              open={showAI && (!!aiInsights || loadingAI || !!aiError)}
              onClose={() => setShowAI(false)}
              fullWidth
              maxWidth="sm"
              TransitionComponent={Transition}
            >
              <Box sx={{ p: 2 }}>
                {/* Header */}
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                    <Box
                      sx={{
                        width: 40,
                        height: 40,
                        borderRadius: 2,
                        background: 'linear-gradient(135deg, #10b981 0%, #14b8a6 50%, #06b6d4 100%)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                    >
                      <Box
                        component="img"
                        src={aiIcon}
                        alt="AI"
                        sx={{ width: 26, height: 26, filter: 'brightness(0) invert(1)' }}
                      />
                    </Box>
                    <Typography variant="h6" fontWeight={700}>
                      {t('channelDetail.aiAnalytics')}
                    </Typography>
                  </Box>
                  <IconButton onClick={() => setShowAI(false)} size="small">
                    <CloseRoundedIcon />
                  </IconButton>
                </Box>

                {/* Loading state */}
                {loadingAI && (
                  <Box sx={{ textAlign: 'center', py: 4 }}>
                    <CircularProgress size={40} />
                    <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
                      {t('channelDetail.aiAnalyzing')}
                    </Typography>
                  </Box>
                )}

                {/* Error state */}
                {aiError && (
                  <Box sx={{ textAlign: 'center', py: 4 }}>
                    <ErrorOutlineRoundedIcon sx={{ fontSize: 48, color: 'error.main', mb: 1 }} />
                    <Typography color="error">{aiError}</Typography>
                    <Button onClick={fetchAIInsights} sx={{ mt: 2 }}>
                      {t('profile.auth.retry')}
                    </Button>
                  </Box>
                )}

                {/* AI Insights Content */}
                {aiInsights && !loadingAI && (
                  <Box>
                    {/* Category Badge + Rating */}
                    <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
                      <Chip
                        icon={<CategoryRoundedIcon />}
                        label={aiInsights.category}
                        color="primary"
                        variant="outlined"
                      />
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                        <StarRoundedIcon sx={{ color: 'warning.main', fontSize: 20 }} />
                        <Typography variant="h6" fontWeight={700}>
                          {aiInsights.rating.score}
                        </Typography>
                        <Typography variant="body2" color="text.secondary">/10</Typography>
                      </Box>
                    </Box>

                    {/* Target Audience */}
                    <Box sx={{ mb: 2, p: 1.5, bgcolor: 'action.hover', borderRadius: 2 }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                        <GroupsRoundedIcon sx={{ fontSize: 18, color: 'text.secondary' }} />
                        <Typography variant="caption" color="text.secondary" fontWeight={600}>
                          {t('channelDetail.aiTargetAudience')}
                        </Typography>
                      </Box>
                      <Typography variant="body2">{aiInsights.targetAudience}</Typography>
                    </Box>

                    {/* Rating explanation */}
                    <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                      {aiInsights.rating.explanation}
                    </Typography>

                    <Divider sx={{ my: 2 }} />

                    {/* Strengths & Weaknesses side by side on desktop */}
                    <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: 2, mb: 2 }}>
                      {/* Strengths */}
                      <Box>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                          <CheckCircleRoundedIcon sx={{ color: 'success.main', fontSize: 20 }} />
                          <Typography variant="subtitle2" fontWeight={600}>
                            {t('channelDetail.aiStrengths')}
                          </Typography>
                        </Box>
                        {aiInsights.strengths.map((s, i) => (
                          <Typography key={i} variant="body2" color="text.secondary" sx={{ mb: 0.5, pl: 3.5 }}>
                            • {s}
                          </Typography>
                        ))}
                      </Box>

                      {/* Weaknesses */}
                      <Box>
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                          <WarningAmberRoundedIcon sx={{ color: 'warning.main', fontSize: 20 }} />
                          <Typography variant="subtitle2" fontWeight={600}>
                            {t('channelDetail.aiWeaknesses')}
                          </Typography>
                        </Box>
                        {aiInsights.weaknesses.map((w, i) => (
                          <Typography key={i} variant="body2" color="text.secondary" sx={{ mb: 0.5, pl: 3.5 }}>
                            • {w}
                          </Typography>
                        ))}
                      </Box>
                    </Box>

                    <Divider sx={{ my: 2 }} />

                    {/* Growth Forecast */}
                    <Box sx={{ mb: 2 }}>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                        <RocketLaunchRoundedIcon sx={{ color: 'primary.main', fontSize: 20 }} />
                        <Typography variant="subtitle2" fontWeight={600}>
                          {t('channelDetail.aiGrowthForecast')}
                        </Typography>
                        <Chip label={aiInsights.growthForecast.percentage} size="small" color="primary" sx={{ ml: 'auto' }} />
                      </Box>
                      <Typography variant="body2" color="text.secondary">
                        {aiInsights.growthForecast.explanation}
                      </Typography>
                    </Box>

                    <Divider sx={{ my: 2 }} />

                    {/* Advertising Recommendation */}
                    <Box 
                      sx={{ 
                        mb: 2, 
                        p: 2, 
                        borderRadius: 2, 
                        color: 'white',
                        background: 'linear-gradient(135deg, #10b981 0%, #14b8a6 50%, #06b6d4 100%)',
                      }}
                    >
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                        <CampaignRoundedIcon sx={{ fontSize: 20 }} />
                        <Typography variant="subtitle2" fontWeight={600}>
                          {t('channelDetail.aiAdvertising')}
                        </Typography>
                      </Box>
                      <Typography variant="body2" sx={{ mb: 1.5, opacity: 0.95 }}>
                        {aiInsights.advertisingRecommendation.whyBuyAds}
                      </Typography>
                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 1.5 }}>
                        {aiInsights.advertisingRecommendation.bestFor.map((b, i) => (
                          <Chip key={i} label={b} size="small" sx={{ bgcolor: 'rgba(255,255,255,0.2)', color: 'inherit' }} />
                        ))}
                      </Box>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Typography variant="caption" sx={{ opacity: 0.85 }}>
                          {t('channelDetail.aiAudienceQuality')}:
                        </Typography>
                        <Chip
                          label={aiInsights.advertisingRecommendation.audienceQuality}
                          size="small"
                          sx={{ 
                            bgcolor: 'rgba(255,255,255,0.25)', 
                            color: 'inherit',
                            fontWeight: 600,
                          }}
                        />
                      </Box>
                    </Box>

                    {/* Content Tips */}
                    <Box>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                        <LightbulbRoundedIcon sx={{ color: 'warning.main', fontSize: 20 }} />
                        <Typography variant="subtitle2" fontWeight={600}>
                          {t('channelDetail.aiContentTips')}
                        </Typography>
                      </Box>
                      {aiInsights.contentTips.map((tip, i) => (
                        <Typography key={i} variant="body2" color="text.secondary" sx={{ mb: 0.5, pl: 3.5 }}>
                          • {tip}
                        </Typography>
                      ))}
                    </Box>
                  </Box>
                )}
              </Box>
            </Dialog>

            {/* Channel Info Section */}
            {(channel.description || channel.category) && (
              <Box 
                sx={{ 
                  mb: 2,
                  p: 2,
                  borderRadius: 3,
                  bgcolor: theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.02)',
                  border: `1px solid ${theme.palette.divider}`,
                }}
              >
                {channel.category && (
                  <Box sx={{ mb: channel.description ? 1.5 : 0 }}>
                    <Chip
                      icon={<CategoryRoundedIcon sx={{ fontSize: 16 }} />}
                      label={
                        (() => {
                          const key = channel.category ?? ''
                          const translated = t(`categories.${key}`)
                          return translated === `categories.${key}` ? key : translated
                        })()
                      }
                      size="small"
                      color="primary"
                      variant="outlined"
                    />
                  </Box>
                )}
                {channel.description && (
                  <Typography 
                    variant="body2" 
                    color="text.secondary"
                    sx={{ lineHeight: 1.6 }}
                  >
                    {channel.description}
                  </Typography>
                )}
              </Box>
            )}

            {/* Updated At */}
            {stats?.updatedAt && (
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 0.5,
                  mb: 2,
                  color: 'text.secondary',
                }}
              >
                <UpdateRoundedIcon sx={{ fontSize: 16 }} />
                <Typography variant="caption">
                  {t('channelDetail.updatedAt')}: {formatUpdatedAt()}
                </Typography>
              </Box>
            )}

            {/* Market Status */}
            <Card
              sx={{
                mb: 2,
                bgcolor: isPublished ? 'success.main' : 'action.hover',
                color: isPublished ? 'success.contrastText' : 'text.primary',
              }}
            >
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                <StorefrontRoundedIcon />
                <Box sx={{ flex: 1 }}>
                  <Typography sx={{ fontWeight: 700 }}>
                    {isPublished ? t('channelDetail.onMarket') : t('channelDetail.notOnMarket')}
                  </Typography>
                  <Typography variant="body2" sx={{ opacity: 0.8 }}>
                    {isPublished
                      ? t('channelDetail.onMarketDescription')
                      : t('channelDetail.notOnMarketDescription')}
                  </Typography>
                </Box>
              </Box>
            </Card>
          </>
        )}
      </DialogContent>

      {/* Bottom Action */}
      <Box
        sx={{
          p: 2,
          borderTop: 1,
          borderColor: 'divider',
          bgcolor: 'background.paper',
          position: 'sticky',
          bottom: 0,
        }}
      >
        <Tooltip
          title={!isPublished && hasAnyEnabledFormats === false ? t('channelDetail.publishErrorNoFormats') : ''}
        >
          <span>
            <Button
              fullWidth
              variant={isPublished ? 'outlined' : 'contained'}
              color={isPublished ? 'error' : 'primary'}
              startIcon={<StorefrontRoundedIcon />}
              onClick={() => onPublishToMarket(channel)}
              disabled={!isPublished && hasAnyEnabledFormats === false}
            >
              {isPublished ? t('channelDetail.unpublishFromMarket') : t('channelDetail.publishToMarket')}
            </Button>
          </span>
        </Tooltip>
      </Box>
    </Dialog>
  )
}

// Loading skeleton for channel detail
export function ChannelDetailSkeleton() {
  return (
    <Box sx={{ p: 2 }}>
      <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'center', mb: 2 }}>
        <Skeleton variant="circular" width={48} height={48} />
        <Box sx={{ flex: 1 }}>
          <Skeleton width="60%" height={24} />
          <Skeleton width="40%" height={18} />
        </Box>
      </Box>
      <Box sx={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 1.5, mb: 2 }}>
        <Skeleton variant="rounded" height={80} />
        <Skeleton variant="rounded" height={80} />
        <Skeleton variant="rounded" height={80} />
      </Box>
      <Skeleton variant="rounded" height={200} />
    </Box>
  )
}

