import AutoAwesomeRoundedIcon from '@mui/icons-material/AutoAwesomeRounded'
import ArrowBackIosNewRoundedIcon from '@mui/icons-material/ArrowBackIosNewRounded'
import CategoryRoundedIcon from '@mui/icons-material/CategoryRounded'
import ChatBubbleOutlineRoundedIcon from '@mui/icons-material/ChatBubbleOutlineRounded'
import CloseRoundedIcon from '@mui/icons-material/CloseRounded'
import CollectionsRoundedIcon from '@mui/icons-material/CollectionsRounded'
import ErrorOutlineRoundedIcon from '@mui/icons-material/ErrorOutlineRounded'
import ExpandLessRoundedIcon from '@mui/icons-material/ExpandLessRounded'
import ExpandMoreRoundedIcon from '@mui/icons-material/ExpandMoreRounded'
import FavoriteRoundedIcon from '@mui/icons-material/FavoriteRounded'
import LightbulbRoundedIcon from '@mui/icons-material/LightbulbRounded'
import OpenInNewRoundedIcon from '@mui/icons-material/OpenInNewRounded'
import ShareRoundedIcon from '@mui/icons-material/ShareRounded'
import SpeedRoundedIcon from '@mui/icons-material/SpeedRounded'
import StorefrontRoundedIcon from '@mui/icons-material/StorefrontRounded'
import ArticleRoundedIcon from '@mui/icons-material/ArticleRounded'
import TrendingUpRoundedIcon from '@mui/icons-material/TrendingUpRounded'
import TrendingDownRoundedIcon from '@mui/icons-material/TrendingDownRounded'
import TrendingFlatRoundedIcon from '@mui/icons-material/TrendingFlatRounded'
import UpdateRoundedIcon from '@mui/icons-material/UpdateRounded'
import GroupsRoundedIcon from '@mui/icons-material/GroupsRounded'
import StarRoundedIcon from '@mui/icons-material/StarRounded'
import CampaignRoundedIcon from '@mui/icons-material/CampaignRounded'
import RocketLaunchRoundedIcon from '@mui/icons-material/RocketLaunchRounded'
import VisibilityRoundedIcon from '@mui/icons-material/VisibilityRounded'
import WarningAmberRoundedIcon from '@mui/icons-material/WarningAmberRounded'
import CheckCircleRoundedIcon from '@mui/icons-material/CheckCircleRounded'
import type { TransitionProps } from '@mui/material/transitions'
import {
  Avatar,
  Box,
  Chip,
  CircularProgress,
  Collapse,
  Dialog,
  Divider,
  IconButton,
  Slide,
  Skeleton,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material'
import { forwardRef, useEffect, useMemo, useState } from 'react'
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useTheme } from '@mui/material/styles'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'
import { Button } from '../../shared/ui/Button'
import { Card } from '../../shared/ui/Card'
import { useAuth } from '../../app/providers/AuthProvider'
import { getApiBase } from '../../shared/utils/apiBase'
import { getJson } from '../../shared/utils/api'
import { aiCornerIcon, aiIcon } from '../../shared/assets/icons'
import { formatMoney, formatNumberCompact } from '../../shared/utils/format'
import { OrderPaymentDialog } from './OrderPaymentDialog'

const Transition = forwardRef(function Transition(
  props: TransitionProps & { children: React.ReactElement },
  ref: React.Ref<unknown>
) {
  return <Slide direction="up" ref={ref} {...props} />
})

type AdFormatDto = {
  id: number
  formatType: string
  isEnabled: boolean
  priceStars: number
  priceTon: number | null
  priceUsdt: number | null
  durationHours: number
  etaHours: number
  settings?: Record<string, unknown> | null
}

type ChannelDetailResponse = {
  id: number
  telegramId: number
  chatType: string
  title: string
  username: string | null
  description: string | null
  photoUrl: string | null
  subscriberCount: number
  inviteLink: string | null
  status: string
  isVisible: boolean
  category: string | null
  language: string | null
  createdAt: string
  updatedAt: string
  adFormats: AdFormatDto[]
  /** true if the current user is the channel owner (cannot buy ads on own channel) */
  isOwnChannel?: boolean | null
}

type BestPostResponse = {
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

type TopPostResponse = {
  messageId: number
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
  postedAt: string | null
}

type ChannelStatsResponse = {
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
  totalReactions: number
  totalComments: number
  totalShares: number
  posts24h: number
  posts7d: number
  posts30d: number
  posts90d: number
  avgPostsPerDay: number
  dynamics: string
  dynamicsScore: number
  lastPostAt: string | null
  bestPost?: BestPostResponse | null
  updatedAt?: string | null
}

type ChartPeriod = '7d' | '30d' | '90d'

type StatsHistoryPoint = {
  date: string
  subscriberCount: number
  totalViews: number
  totalPosts: number
}

type StatsHistoryResponse = {
  channelId: number
  period: string
  data: StatsHistoryPoint[]
}

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

function formatTelegramText(text: string): string {
  if (!text) return ''
  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  html = html.replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
  html = html.replace(/\*([^*]+)\*/g, '<b>$1</b>')
  html = html.replace(/__([^_]+)__/g, '<i>$1</i>')
  html = html.replace(/_([^_]+)_/g, '<i>$1</i>')
  html = html.replace(/~~([^~]+)~~/g, '<del>$1</del>')
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>')
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')
  html = html.replace(/\n/g, '<br/>')
  return html
}

function PopularPostCard({
  post,
  channelUsername,
  rank,
  isBestPost,
  t,
  getApiBase,
}: {
  post: TopPostResponse
  channelUsername: string | null
  rank: number
  isBestPost?: boolean
  t: (key: string) => string
  getApiBase: () => string
}) {
  const [expanded, setExpanded] = useState(false)
  const theme = useTheme()

  return (
    <Card
      clickable
      onClick={() => setExpanded((prev) => !prev)}
      disableContentPadding
      sx={{
        mb: 2,
        p: 0,
        overflow: 'hidden',
        border: `1px solid ${theme.palette.divider}`,
        transition: 'all 0.2s',
        '&:hover': { boxShadow: theme.shadows[2] },
      }}
    >
      {/* Media at top (if exists and collapsed) */}
      {post.mediaUrl && !expanded && (
        <Box sx={{ position: 'relative', height: 120, overflow: 'hidden' }}>
          <Box
            component="img"
            src={`${getApiBase()}${post.mediaUrl}`}
            alt=""
            sx={{ width: '100%', height: '100%', objectFit: 'cover' }}
            onError={(e) => {
              (e.target as HTMLImageElement).style.display = 'none'
            }}
          />
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
              {formatNumberCompact(post.views)}
            </Typography>
          </Box>
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
              {isBestPost ? t('channelDetail.bestPost') : `#${rank}`}
            </Typography>
          </Box>
          {post.isAlbum && (
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
                {post.mediaCount || 1}
              </Typography>
            </Box>
          )}
        </Box>
      )}

      {/* Header when no media or expanded */}
      {(!post.mediaUrl || expanded) && (
        <Box
          sx={{
            px: 2,
            py: 1.5,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderBottom: expanded ? 1 : 0,
            borderColor: 'divider',
            bgcolor: theme.palette.mode === 'dark' ? 'rgba(245,158,11,0.1)' : 'rgba(245,158,11,0.05)',
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <AutoAwesomeRoundedIcon sx={{ color: '#f59e0b', fontSize: 18 }} />
            <Typography variant="body2" sx={{ fontWeight: 700, color: '#f59e0b' }}>
              {isBestPost ? t('channelDetail.bestPost') : `#${rank}`}
            </Typography>
            {post.isAlbum && (
              <Chip
                icon={<CollectionsRoundedIcon sx={{ fontSize: 12 }} />}
                label={post.mediaCount || 1}
                size="small"
                sx={{ height: 20, fontSize: 10, '& .MuiChip-icon': { fontSize: 12 } }}
              />
            )}
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, color: 'text.secondary' }}>
              <VisibilityRoundedIcon sx={{ fontSize: 16 }} />
              <Typography sx={{ fontWeight: 700, fontSize: 14 }}>
                {formatNumberCompact(post.views)}
              </Typography>
            </Box>
            {expanded ? (
              <ExpandLessRoundedIcon sx={{ fontSize: 20, color: 'text.secondary' }} />
            ) : (
              <ExpandMoreRoundedIcon sx={{ fontSize: 20, color: 'text.secondary' }} />
            )}
          </Box>
        </Box>
      )}

      {/* Content */}
      <Box sx={{ p: 2 }}>
        <Collapse in={!expanded}>
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
            {post.text?.replace(/\*\*/g, '').replace(/\*/g, '') || post.fullText || t('channelDetail.mediaPost')}
          </Typography>
        </Collapse>

        <Collapse in={expanded}>
          {post.mediaUrl && (
            <Box
              component="img"
              src={`${getApiBase()}${post.mediaUrl}`}
              alt=""
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
              '& code': { bgcolor: 'action.hover', px: 0.5, borderRadius: 0.5, fontFamily: 'monospace' },
            }}
            dangerouslySetInnerHTML={{
              __html: formatTelegramText(post.fullText || post.text || t('channelDetail.mediaPost')),
            }}
          />
          {channelUsername && post.messageId && (
            <Box sx={{ mt: 2 }}>
              <Chip
                icon={<OpenInNewRoundedIcon sx={{ fontSize: 14 }} />}
                label={t('channelDetail.goToPost')}
                size="small"
                clickable
                component="a"
                href={`https://t.me/${channelUsername}/${post.messageId}`}
                target="_blank"
                rel="noopener noreferrer"
                onClick={(e: React.MouseEvent) => e.stopPropagation()}
                sx={{ bgcolor: '#f59e0b', color: 'white', '&:hover': { bgcolor: '#d97706' } }}
              />
            </Box>
          )}
        </Collapse>

        {/* Stats row */}
        <Box sx={{ display: 'flex', gap: 2, mt: 1.5, pt: 1.5, borderTop: 1, borderColor: 'divider' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <FavoriteRoundedIcon sx={{ fontSize: 14, color: 'error.main' }} />
            <Typography variant="caption" sx={{ fontWeight: 600 }}>
              {formatNumberCompact(post.reactions)}
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <ChatBubbleOutlineRoundedIcon sx={{ fontSize: 14, color: 'info.main' }} />
            <Typography variant="caption" sx={{ fontWeight: 600 }}>
              {formatNumberCompact(post.comments)}
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
            <ShareRoundedIcon sx={{ fontSize: 14, color: 'success.main' }} />
            <Typography variant="caption" sx={{ fontWeight: 600 }}>
              {formatNumberCompact(post.shares)}
            </Typography>
          </Box>
        </Box>
      </Box>
    </Card>
  )
}

export function ChannelDetailsPage() {
  const { t } = useTranslation()
  const theme = useTheme()
  const { channelId } = useParams()
  const navigate = useNavigate()
  const { token } = useAuth()

  const [channel, setChannel] = useState<ChannelDetailResponse | null>(null)
  const [stats, setStats] = useState<ChannelStatsResponse | null>(null)
  const [history, setHistory] = useState<StatsHistoryResponse | null>(null)
  const [ai, setAi] = useState<AIInsightsData | null>(null)
  const [showAI, setShowAI] = useState(false)
  const [aiError, setAiError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadingChart, setLoadingChart] = useState(false)
  const [aiLoading, setAiLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [selectedFormatId, setSelectedFormatId] = useState<number | null>(null)
  const [orderWritePostLink, setOrderWritePostLink] = useState<string | null>(null)
  const [chartPeriod, setChartPeriod] = useState<ChartPeriod>('30d')
  const [activeChart, setActiveChart] = useState<'subscribers' | 'views' | 'posts'>('subscribers')
  const [descriptionExpanded, setDescriptionExpanded] = useState(false)
  const [formatModalOpen, setFormatModalOpen] = useState(false)

  useEffect(() => {
    const load = async () => {
      if (!channelId) {
        setLoading(false)
        return
      }
      const base = getApiBase()
      if (!base) {
        setLoading(false)
        return
      }

      setLoading(true)
      setError(null)

      try {
        const detail = await getJson<ChannelDetailResponse>(
          `${base}/api/channels/market/${channelId}`,
          token ? { headers: { Authorization: `Bearer ${token}` } } : {},
        )
        setChannel(detail)

        try {
          const statsResp = await getJson<ChannelStatsResponse>(
            `${base}/api/channels/market/${channelId}/stats`,
          )
          setStats(statsResp)
        } catch {
          // stats are optional
        }
      } catch (e) {
        // eslint-disable-next-line no-console
        console.error('Failed to load channel details:', e)
        setError('Failed to load channel')
      } finally {
        setLoading(false)
      }
    }

    void load()
  }, [channelId, token])

  const fetchAIInsights = async () => {
    if (!channelId) return

    setAiLoading(true)
    setAiError(null)
    try {
      const base = getApiBase()
      if (!base) return

      const res = await getJson<{ ok: boolean; data?: AIInsightsData; error?: string }>(
        `${base}/api/channels/market/${channelId}/ai-insights-structured`,
      )
      if (res.ok && res.data) {
        setAi(res.data)
        setShowAI(true)
      } else {
        setAiError(res.error ?? 'Failed to generate AI insights')
      }
    } catch (e) {
      console.error('Failed to load AI insights:', e)
      setAiError('Failed to connect to AI service')
    } finally {
      setAiLoading(false)
    }
  }

  // Fetch stats history for charts
  useEffect(() => {
    const loadHistory = async () => {
      if (!channelId) return
      const base = getApiBase()
      if (!base) return

      setLoadingChart(true)
      try {
        const res = await getJson<StatsHistoryResponse>(
          `${base}/api/channels/market/${channelId}/stats/history?period=${chartPeriod}`,
        )
        setHistory(res)
      } catch {
        setHistory(null)
      } finally {
        setLoadingChart(false)
      }
    }

    void loadHistory()
  }, [channelId, chartPeriod])

  const chartData = useMemo(() => {
    if (!history?.data?.length) return []
    return history.data.map((point) => ({
      date: new Date(point.date).toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit' }),
      subscribers: point.subscriberCount,
      views: point.totalViews,
      posts: point.totalPosts,
    }))
  }, [history])

  // Инициализируем выбранный формат при загрузке канала
  useEffect(() => {
    if (!channel) return
    const firstEnabled = channel.adFormats.find((f) => f.isEnabled)
    setSelectedFormatId(firstEnabled ? firstEnabled.id : null)
  }, [channel])

  if (loading) {
    return (
      <Box>
        <Typography variant="h5" sx={{ fontWeight: 800, mb: 1 }}>
          {t('channel.title')}
        </Typography>
        <Card>
          <Box sx={{ p: 2 }}>
            <Typography variant="body2" color="text.secondary">
              ...
            </Typography>
          </Box>
        </Card>
      </Box>
    )
  }

  if (error || !channel) {
    return (
      <Box>
        <Typography variant="h5" sx={{ fontWeight: 800, mb: 1 }}>
          {t('channel.title')}
        </Typography>
        <Typography variant="body2" color="error">
          {error || 'Channel not found'}
        </Typography>
      </Box>
    )
  }

  const subs = stats?.subscriberCount ?? channel.subscriberCount
  const growth30d = stats?.subscriberGrowth30d ?? 0

  const selectedFormat = selectedFormatId
    ? channel.adFormats.find((f) => f.id === selectedFormatId) ?? null
    : null

  const [paymentDialogOpen, setPaymentDialogOpen] = useState(false)

  const handleBuy = () => {
    if (!selectedFormat || !channel || !token) return
    if (!selectedFormat.priceStars && (selectedFormat.priceUsdt == null || selectedFormat.priceUsdt <= 0)) {
      setError(t('channel.payment.noPrice'))
      return
    }
    setError(null)
    setPaymentDialogOpen(true)
  }

  const handlePaymentSuccess = (writePostLink: string) => {
    setOrderWritePostLink(writePostLink)
    setPaymentDialogOpen(false)
  }

  const openWritePost = () => {
    if (orderWritePostLink) {
      if (typeof window.Telegram?.WebApp?.openTelegramLink === 'function') {
        window.Telegram.WebApp.openTelegramLink(orderWritePostLink)
      } else {
        window.open(orderWritePostLink, '_blank')
      }
    }
  }

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

  const openChannelLink = (e: React.MouseEvent) => {
    if (!channel.username) return
    e.stopPropagation()
    const url = `https://t.me/${channel.username}`
    if (typeof window.Telegram?.WebApp?.openTelegramLink === 'function') {
      window.Telegram.WebApp.openTelegramLink(url)
    } else {
      window.open(url, '_blank', 'noopener,noreferrer')
    }
  }

  return (
    <Box sx={{ pb: 10 }}>
      {/* Back button */}
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 1.5 }}>
        <IconButton onClick={() => navigate(-1)} size="small" sx={{ mr: 0.5 }}>
          <ArrowBackIosNewRoundedIcon sx={{ fontSize: 16 }} />
        </IconButton>
      </Box>

      {/* Channel header card - compact: icon, name, username (link), category */}
      <Card
        onClick={() => channel.description && setDescriptionExpanded((prev) => !prev)}
        sx={{
          mb: 1.5,
          p: 1.25,
          cursor: channel.description ? 'pointer' : 'default',
          borderRadius: 2,
          border: `1px solid ${theme.palette.divider}`,
          transition: 'all 0.2s',
          '&:hover': channel.description
            ? { boxShadow: theme.shadows[2], bgcolor: theme.palette.action.hover }
            : {},
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25, flexWrap: 'wrap' }}>
          <Avatar
            src={`${getApiBase()}/api/media/channel-photo/${channel.id}`}
            sx={{ width: 40, height: 40, flexShrink: 0, bgcolor: 'primary.main' }}
          >
            {channel.title?.[0] || '?'}
          </Avatar>
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Typography
              sx={{
                fontWeight: 800,
                fontSize: 15,
                lineHeight: 1.2,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                display: '-webkit-box',
                WebkitLineClamp: 2,
                WebkitBoxOrient: 'vertical',
              }}
            >
              {channel.title}
            </Typography>
            {channel.username && (
              <Typography
                component="button"
                variant="body2"
                onClick={openChannelLink}
                sx={{
                  mt: 0.25,
                  color: 'primary.main',
                  fontWeight: 600,
                  fontSize: 13,
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  padding: 0,
                  textAlign: 'left',
                  '&:hover': { textDecoration: 'underline' },
                }}
              >
                @{channel.username}
              </Typography>
            )}
          </Box>
          {channel.category && (
            <Chip
              icon={<CategoryRoundedIcon sx={{ fontSize: 12 }} />}
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
              sx={{ height: 22, fontSize: 11, flexShrink: 0, '& .MuiChip-icon': { fontSize: 12 } }}
            />
          )}
          {channel.description && (
            <Box sx={{ color: 'text.secondary', flexShrink: 0 }}>
              {descriptionExpanded ? (
                <ExpandLessRoundedIcon sx={{ fontSize: 20 }} />
              ) : (
                <ExpandMoreRoundedIcon sx={{ fontSize: 20 }} />
              )}
            </Box>
          )}
        </Box>

        {/* Expandable description */}
        {channel.description && (
          <Collapse in={descriptionExpanded}>
            <Box
              sx={{
                mt: 1.5,
                pt: 1.5,
                borderTop: 1,
                borderColor: 'divider',
              }}
              onClick={(e) => e.stopPropagation()}
            >
              <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
                {channel.description}
              </Typography>
            </Box>
          </Collapse>
        )}
      </Card>

      {/* Ad format button - opens modal with format selection */}
      {channel.adFormats.some((f) => f.isEnabled) && (
        <Button
          fullWidth
          variant="outlined"
          startIcon={<StorefrontRoundedIcon />}
          onClick={() => setFormatModalOpen(true)}
          sx={{
            mb: 2,
            py: 1.5,
            borderRadius: 2,
            borderWidth: 2,
            '&:hover': { borderWidth: 2 },
            fontWeight: 700,
          }}
        >
          {selectedFormatId
            ? (() => {
                const f = channel.adFormats.find((x) => x.id === selectedFormatId)
                if (!f) return t('channel.formats.title')
                const type = f.formatType === 'post' ? 'Пост' : f.formatType
                const price = f.priceUsdt != null ? formatMoney(f.priceUsdt) : f.priceStars != null ? `${f.priceStars} Stars` : ''
                return `${type} · ${f.durationHours}ч${price ? ` · ${price}` : ''}`
              })()
            : t('channel.formats.title')}
        </Button>
      )}

      {/* Hero stats - same layout as My Channels with AI button top-left */}
      {stats && (
        <>
          <Box
            sx={{
              p: 2,
              mb: 2,
              borderRadius: 3,
              background:
                theme.palette.mode === 'dark'
                  ? 'linear-gradient(135deg, rgba(16,185,129,0.12) 0%, rgba(20,184,166,0.08) 100%)'
                  : 'linear-gradient(135deg, rgba(16,185,129,0.08) 0%, rgba(20,184,166,0.04) 100%)',
              border: `1px solid ${theme.palette.divider}`,
              position: 'relative',
            }}
          >
            {/* AI Button - top left, same as My Channels */}
            <IconButton
              onClick={() => {
                if (!aiLoading) {
                  if (!ai) fetchAIInsights()
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
              {aiLoading ? (
                <CircularProgress size={20} sx={{ color: 'white' }} />
              ) : (
                <Box component="img" src={aiIcon} alt="AI" sx={{ width: 24, height: 24, filter: 'brightness(0) invert(1)' }} />
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
                {formatNumberCompact(subs)}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 0.5 }}>
                {t('channelDetail.subscribers')}
              </Typography>
            </Box>
            <Box sx={{ display: 'flex', justifyContent: 'space-around' }}>
              <Box sx={{ textAlign: 'center' }}>
                {(() => {
                  const color = growth30d > 0 ? '#10b981' : growth30d < 0 ? '#ef4444' : 'text.secondary'
                  return (
                    <>
                      <Typography sx={{ fontWeight: 800, fontSize: 20, color }}>
                        {growth30d >= 0 ? '+' : ''}{formatNumberCompact(growth30d)}
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {t('channelDetail.growth')}
                      </Typography>
                    </>
                  )
                })()}
              </Box>
              <Divider orientation="vertical" flexItem />
              <Box sx={{ textAlign: 'center' }}>
                <Typography sx={{ fontWeight: 800, fontSize: 20, color: '#059669' }}>
                  {formatNumberCompact(stats.avgPostViews)}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {t('channelDetail.avgViews')}
                </Typography>
              </Box>
              <Divider orientation="vertical" flexItem />
              <Box sx={{ textAlign: 'center' }}>
                <Typography sx={{ fontWeight: 800, fontSize: 20, color: '#14b8a6' }}>
                  {stats.engagementRate?.toFixed(1) ?? '0'}%
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  ER
                </Typography>
              </Box>
            </Box>
          </Box>

          {/* Activity row - Reach 24h, Posts/day, Posts, Dynamics */}
          <Card sx={{ mb: 2, p: 0, overflow: 'hidden', border: `1px solid ${theme.palette.divider}` }}>
            <Box sx={{ display: 'flex' }}>
              <Box sx={{ flex: 1, py: 1.5, textAlign: 'center', borderRight: `1px solid ${theme.palette.divider}` }}>
                <VisibilityRoundedIcon sx={{ fontSize: 18, color: '#10b981', mb: 0.25 }} />
                <Typography sx={{ fontWeight: 800, fontSize: 15 }}>
                  {formatNumberCompact(stats.avgReach24h)}
                </Typography>
                <Typography variant="caption" color="text.secondary" sx={{ fontSize: 10 }}>
                  {t('channelDetail.reach24h')}
                </Typography>
              </Box>
              <Box sx={{ flex: 1, py: 1.5, textAlign: 'center', borderRight: `1px solid ${theme.palette.divider}` }}>
                <SpeedRoundedIcon sx={{ fontSize: 18, color: '#059669', mb: 0.25 }} />
                <Typography sx={{ fontWeight: 800, fontSize: 15 }}>
                  {stats.avgPostsPerDay.toFixed(1)}
                </Typography>
                <Typography variant="caption" color="text.secondary" sx={{ fontSize: 10 }}>
                  {t('channelDetail.postsPerDay')}
                </Typography>
              </Box>
              <Box sx={{ flex: 1, py: 1.5, textAlign: 'center', borderRight: `1px solid ${theme.palette.divider}` }}>
                <ArticleRoundedIcon sx={{ fontSize: 18, color: '#047857', mb: 0.25 }} />
                <Typography sx={{ fontWeight: 800, fontSize: 15 }}>
                  {formatNumberCompact(stats.posts30d)}
                </Typography>
                <Typography variant="caption" color="text.secondary" sx={{ fontSize: 10 }}>
                  {t('channelDetail.posts')}
                </Typography>
              </Box>
              <Box sx={{ flex: 1, py: 1.5, textAlign: 'center' }}>
                {stats.dynamics === 'growing' ? (
                  <TrendingUpRoundedIcon sx={{ fontSize: 18, color: '#10b981', mb: 0.25 }} />
                ) : stats.dynamics === 'declining' ? (
                  <TrendingDownRoundedIcon sx={{ fontSize: 18, color: '#ef4444', mb: 0.25 }} />
                ) : (
                  <TrendingFlatRoundedIcon sx={{ fontSize: 18, color: '#6b7280', mb: 0.25 }} />
                )}
                <Typography
                  sx={{
                    fontWeight: 800,
                    fontSize: 15,
                    color:
                      stats.dynamics === 'growing'
                        ? '#10b981'
                        : stats.dynamics === 'declining'
                          ? '#ef4444'
                          : 'text.primary',
                  }}
                >
                  {t(`channelDetail.dynamics.${stats.dynamics ?? 'stable'}`)}
                </Typography>
                <Typography variant="caption" color="text.secondary" sx={{ fontSize: 10 }}>
                  {t('channelDetail.dynamicsLabel')}
                </Typography>
              </Box>
            </Box>
          </Card>

          {/* Engagement row - same as My Channels */}
          <Card sx={{ mb: 2, p: 0, overflow: 'hidden', border: `1px solid ${theme.palette.divider}` }}>
            <Box
              sx={{
                px: 1.5,
                py: 0.75,
                background:
                  theme.palette.mode === 'dark'
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
                label={`${stats.engagementRate?.toFixed(1) ?? '0'}%`}
                size="small"
                sx={{ height: 20, fontSize: 11, fontWeight: 700, bgcolor: '#10b981', color: 'white' }}
              />
            </Box>
            <Box sx={{ display: 'flex' }}>
              <Box sx={{ flex: 1, py: 1.5, textAlign: 'center', borderRight: `1px solid ${theme.palette.divider}` }}>
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.5, mb: 0.25 }}>
                  <FavoriteRoundedIcon sx={{ fontSize: 14, color: '#10b981' }} />
                  <Typography sx={{ fontWeight: 800, fontSize: 14 }}>
                    {formatNumberCompact(stats.totalReactions)}
                  </Typography>
                </Box>
                <Typography variant="caption" color="text.secondary" sx={{ fontSize: 9 }}>
                  {t('channelDetail.reactions')}
                </Typography>
              </Box>
              <Box sx={{ flex: 1, py: 1.5, textAlign: 'center', borderRight: `1px solid ${theme.palette.divider}` }}>
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.5, mb: 0.25 }}>
                  <ChatBubbleOutlineRoundedIcon sx={{ fontSize: 14, color: '#14b8a6' }} />
                  <Typography sx={{ fontWeight: 800, fontSize: 14 }}>
                    {formatNumberCompact(stats.totalComments)}
                  </Typography>
                </Box>
                <Typography variant="caption" color="text.secondary" sx={{ fontSize: 9 }}>
                  {t('channelDetail.comments')}
                </Typography>
              </Box>
              <Box sx={{ flex: 1, py: 1.5, textAlign: 'center', borderRight: `1px solid ${theme.palette.divider}` }}>
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.5, mb: 0.25 }}>
                  <ShareRoundedIcon sx={{ fontSize: 14, color: '#059669' }} />
                  <Typography sx={{ fontWeight: 800, fontSize: 14 }}>
                    {formatNumberCompact(stats.totalShares)}
                  </Typography>
                </Box>
                <Typography variant="caption" color="text.secondary" sx={{ fontSize: 9 }}>
                  {t('channelDetail.shares')}
                </Typography>
              </Box>
              <Box sx={{ flex: 1, py: 1.5, textAlign: 'center' }}>
                <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.5, mb: 0.25 }}>
                  <VisibilityRoundedIcon sx={{ fontSize: 14, color: '#047857' }} />
                  <Typography sx={{ fontWeight: 800, fontSize: 14 }}>
                    {formatNumberCompact(stats.totalViews24h)}
                  </Typography>
                </Box>
                <Typography variant="caption" color="text.secondary" sx={{ fontSize: 9 }}>
                  24h
                </Typography>
              </Box>
            </Box>
          </Card>
        </>
      )}

      {/* Charts - show when channel (history loaded separately) */}
      <Card
            sx={{
              mb: 2,
              p: 2,
              borderRadius: 3,
              bgcolor: theme.palette.mode === 'dark' ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.02)',
              border: '1px solid',
              borderColor: 'divider',
            }}
          >
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
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
                }}
              />
            </Box>

            <Box sx={{ height: 180, width: '100%', minHeight: 180, position: 'relative' }}>
              {loadingChart ? (
                <Skeleton variant="rounded" width="100%" height="100%" />
              ) : chartData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <defs>
                      <linearGradient id="marketColorSubscribers" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="marketColorViews" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="marketColorPosts" x1="0" y1="0" x2="0" y2="1">
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
                            : t('channelDetail.posts'),
                      ]}
                    />
                    {activeChart === 'subscribers' && (
                      <Area
                        type="monotone"
                        dataKey="subscribers"
                        stroke="#6366f1"
                        strokeWidth={2}
                        fillOpacity={1}
                        fill="url(#marketColorSubscribers)"
                      />
                    )}
                    {activeChart === 'views' && (
                      <Area
                        type="monotone"
                        dataKey="views"
                        stroke="#f59e0b"
                        strokeWidth={2}
                        fillOpacity={1}
                        fill="url(#marketColorViews)"
                      />
                    )}
                    {activeChart === 'posts' && (
                      <Area
                        type="monotone"
                        dataKey="posts"
                        stroke="#10b981"
                        strokeWidth={2}
                        fillOpacity={1}
                        fill="url(#marketColorPosts)"
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
          </Card>

          {/* Best post - only one, like in My Channels */}
          {stats?.bestPost && (
            <Box sx={{ mb: 2 }}>
              <PopularPostCard
                post={{
                  messageId: stats.bestPost.messageId ?? 0,
                  views: stats.bestPost.views,
                  reactions: stats.bestPost.reactions,
                  comments: stats.bestPost.comments,
                  shares: stats.bestPost.shares,
                  text: stats.bestPost.text,
                  fullText: stats.bestPost.fullText,
                  hasMedia: stats.bestPost.hasMedia,
                  mediaUrl: stats.bestPost.mediaUrl,
                  isAlbum: stats.bestPost.isAlbum,
                  mediaCount: stats.bestPost.mediaCount,
                  postedAt: null,
                }}
                channelUsername={channel.username}
                rank={1}
                isBestPost
                t={t}
                getApiBase={getApiBase}
              />
            </Box>
          )}

      {/* AI Analytics Button */}
      <Box
        onClick={() => {
          if (!aiLoading) {
            if (!ai) {
              fetchAIInsights()
            } else {
              setShowAI(true)
            }
          }
        }}
        sx={{
          mb: 2,
          p: '2px',
          borderRadius: 3,
          cursor: aiLoading ? 'wait' : 'pointer',
          position: 'relative',
          overflow: 'hidden',
          background: 'linear-gradient(135deg, #10b981 0%, #14b8a6 50%, #06b6d4 100%)',
          transition: 'all 0.3s ease',
          '&:hover': {
            transform: 'translateY(-2px)',
            boxShadow: '0 8px 25px rgba(16,185,129,0.35)',
          },
          '&:active': { transform: 'translateY(0)' },
        }}
      >
        <Box sx={{ p: 2, borderRadius: 2.5, bgcolor: 'background.paper', position: 'relative' }}>
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
              sx={{ position: 'absolute', top: 10, right: 10, width: 20, height: 20, filter: 'brightness(0) invert(1)' }}
            />
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
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
              {aiLoading ? (
                <CircularProgress size={30} sx={{ color: 'white' }} />
              ) : (
                <Box component="img" src={aiIcon} alt="AI" sx={{ width: 40, height: 40, filter: 'brightness(0) invert(1)' }} />
              )}
            </Box>
            <Box sx={{ flex: 1 }}>
              <Typography variant="subtitle1" fontWeight={700} sx={{ mb: 0.25 }}>
                {t('channelDetail.aiAnalytics')}
              </Typography>
              <Typography variant="body2" sx={{ color: 'text.primary', opacity: 0.7 }}>
                {aiLoading ? t('channelDetail.aiAnalyzing') : t('channelDetail.aiDescription')}
              </Typography>
            </Box>
            <ExpandMoreRoundedIcon sx={{ color: 'text.secondary', transform: 'rotate(-90deg)' }} />
          </Box>
        </Box>
      </Box>

      {aiError && !showAI && (
        <Card sx={{ mb: 2, bgcolor: 'error.main', color: 'white' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <ErrorOutlineRoundedIcon />
            <Typography variant="body2">{aiError}</Typography>
          </Box>
        </Card>
      )}

      {/* Updated At - same as My Channels */}
      {stats?.updatedAt && (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mb: 2, color: 'text.secondary' }}>
          <UpdateRoundedIcon sx={{ fontSize: 16 }} />
          <Typography variant="caption">
            {t('channelDetail.updatedAt')}: {formatUpdatedAt()}
          </Typography>
        </Box>
      )}

      {/* AI Insights Dialog */}
      <Dialog
        open={showAI && (!!ai || aiLoading || !!aiError)}
        onClose={() => setShowAI(false)}
        fullWidth
        maxWidth="sm"
        TransitionComponent={Transition}
      >
        <Box sx={{ p: 2 }}>
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
                <Box component="img" src={aiIcon} alt="AI" sx={{ width: 26, height: 26, filter: 'brightness(0) invert(1)' }} />
              </Box>
              <Typography variant="h6" fontWeight={700}>
                {t('channelDetail.aiAnalytics')}
              </Typography>
            </Box>
            <IconButton onClick={() => setShowAI(false)} size="small">
              <CloseRoundedIcon />
            </IconButton>
          </Box>

          {aiLoading && (
            <Box sx={{ textAlign: 'center', py: 4 }}>
              <CircularProgress size={40} />
              <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
                {t('channelDetail.aiAnalyzing')}
              </Typography>
            </Box>
          )}

          {aiError && (
            <Box sx={{ textAlign: 'center', py: 4 }}>
              <ErrorOutlineRoundedIcon sx={{ fontSize: 48, color: 'error.main', mb: 1 }} />
              <Typography color="error">{aiError}</Typography>
              <Button variant="outlined" onClick={fetchAIInsights} sx={{ mt: 2 }}>
                {t('common.retry')}
              </Button>
            </Box>
          )}

          {ai && !aiLoading && (
            <Box>
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
                <Chip icon={<CategoryRoundedIcon />} label={ai.category} color="primary" variant="outlined" />
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                  <StarRoundedIcon sx={{ color: 'warning.main', fontSize: 20 }} />
                  <Typography variant="h6" fontWeight={700}>{ai.rating.score}</Typography>
                  <Typography variant="body2" color="text.secondary">/10</Typography>
                </Box>
              </Box>

              <Box sx={{ mb: 2, p: 1.5, bgcolor: 'action.hover', borderRadius: 2 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
                  <GroupsRoundedIcon sx={{ fontSize: 18, color: 'text.secondary' }} />
                  <Typography variant="caption" color="text.secondary" fontWeight={600}>
                    {t('channelDetail.aiTargetAudience')}
                  </Typography>
                </Box>
                <Typography variant="body2">{ai.targetAudience}</Typography>
              </Box>

              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                {ai.rating.explanation}
              </Typography>

              <Divider sx={{ my: 2 }} />

              <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: 2, mb: 2 }}>
                <Box>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                    <CheckCircleRoundedIcon sx={{ color: 'success.main', fontSize: 20 }} />
                    <Typography variant="subtitle2" fontWeight={600}>
                      {t('channelDetail.aiStrengths')}
                    </Typography>
                  </Box>
                  {ai.strengths.map((s, i) => (
                    <Typography key={i} variant="body2" color="text.secondary" sx={{ mb: 0.5, pl: 3.5 }}>
                      • {s}
                    </Typography>
                  ))}
                </Box>
                <Box>
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                    <WarningAmberRoundedIcon sx={{ color: 'warning.main', fontSize: 20 }} />
                    <Typography variant="subtitle2" fontWeight={600}>
                      {t('channelDetail.aiWeaknesses')}
                    </Typography>
                  </Box>
                  {ai.weaknesses.map((w, i) => (
                    <Typography key={i} variant="body2" color="text.secondary" sx={{ mb: 0.5, pl: 3.5 }}>
                      • {w}
                    </Typography>
                  ))}
                </Box>
              </Box>

              <Divider sx={{ my: 2 }} />

              <Box sx={{ mb: 2 }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                  <RocketLaunchRoundedIcon sx={{ color: 'primary.main', fontSize: 20 }} />
                  <Typography variant="subtitle2" fontWeight={600}>
                    {t('channelDetail.aiGrowthForecast')}
                  </Typography>
                  <Chip label={ai.growthForecast.percentage} size="small" color="primary" sx={{ ml: 'auto' }} />
                </Box>
                <Typography variant="body2" color="text.secondary">
                  {ai.growthForecast.explanation}
                </Typography>
              </Box>

              <Divider sx={{ my: 2 }} />

              <Box sx={{ mb: 2, p: 2, borderRadius: 2, color: 'white', background: 'linear-gradient(135deg, #10b981 0%, #14b8a6 50%, #06b6d4 100%)' }}>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                  <CampaignRoundedIcon sx={{ fontSize: 20 }} />
                  <Typography variant="subtitle2" fontWeight={600}>
                    {t('channelDetail.aiAdvertising')}
                  </Typography>
                </Box>
                <Typography variant="body2" sx={{ mb: 1.5, opacity: 0.95 }}>
                  {ai.advertisingRecommendation.whyBuyAds}
                </Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 1.5 }}>
                  {ai.advertisingRecommendation.bestFor.map((b, i) => (
                    <Chip key={i} label={b} size="small" sx={{ bgcolor: 'rgba(255,255,255,0.2)', color: 'inherit' }} />
                  ))}
                </Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                  <Typography variant="caption" sx={{ opacity: 0.85 }}>
                    {t('channelDetail.aiAudienceQuality')}:
                  </Typography>
                  <Chip
                    label={ai.advertisingRecommendation.audienceQuality}
                    size="small"
                    sx={{ bgcolor: 'rgba(255,255,255,0.25)', color: 'inherit', fontWeight: 600 }}
                  />
                </Box>
              </Box>

              <Box>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                  <LightbulbRoundedIcon sx={{ color: 'warning.main', fontSize: 20 }} />
                  <Typography variant="subtitle2" fontWeight={600}>
                    {t('channelDetail.aiContentTips')}
                  </Typography>
                </Box>
                {ai.contentTips.map((tip, i) => (
                  <Typography key={i} variant="body2" color="text.secondary" sx={{ mb: 0.5, pl: 3.5 }}>
                    • {tip}
                  </Typography>
                ))}
              </Box>
            </Box>
          )}
        </Box>
      </Dialog>

      {/* Ad format selection modal */}
      <Dialog
        open={formatModalOpen}
        onClose={() => setFormatModalOpen(false)}
        fullWidth
        maxWidth="sm"
        TransitionComponent={Transition}
      >
        <Box sx={{ p: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
            <Typography variant="h6" sx={{ fontWeight: 700 }}>
              {t('channel.formats.title')}
            </Typography>
            <IconButton onClick={() => setFormatModalOpen(false)} size="small">
              <CloseRoundedIcon />
            </IconButton>
          </Box>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
            {channel.adFormats
              .filter((f) => f.isEnabled)
              .map((f) => (
                <Box
                  key={f.id}
                  sx={{
                    px: 1.5,
                    py: 1.25,
                    borderBottom: '1px solid',
                    borderColor: 'divider',
                    cursor: 'pointer',
                    borderRadius: 1,
                    bgcolor: f.id === selectedFormatId ? 'action.selected' : 'transparent',
                    '&:hover': { bgcolor: 'action.hover' },
                    '&:last-of-type': { borderBottom: 'none' },
                  }}
                  onClick={() => {
                    setSelectedFormatId(f.id)
                    setFormatModalOpen(false)
                  }}
                >
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Box>
                      <Typography sx={{ fontWeight: 700 }}>
                        {f.formatType === 'post' ? 'Пост' : f.formatType} · {f.durationHours}ч
                      </Typography>
                      <Typography variant="caption" color="text.secondary">
                        {f.settings?.pinned ? 'с закрепом' : 'без закрепа'}
                      </Typography>
                    </Box>
                    <Box sx={{ textAlign: 'right' }}>
                      {f.priceUsdt != null && (
                        <Typography sx={{ fontWeight: 700 }}>
                          {formatMoney(f.priceUsdt).replace('$', '')}{' '}
                          <Box
                            component="span"
                            sx={{
                              fontSize: 11,
                              fontWeight: 700,
                              px: 0.75,
                              py: 0.25,
                              borderRadius: 999,
                              bgcolor: 'rgba(45, 211, 111, 0.1)',
                              color: '#22c55e',
                            }}
                          >
                            USDT
                          </Box>
                        </Typography>
                      )}
                      {f.priceStars != null && (
                        <Typography variant="caption" color="text.secondary">
                          {f.priceStars} Stars
                        </Typography>
                      )}
                      {f.priceUsdt == null && f.priceStars == null && (
                        <Typography variant="caption" color="text.secondary" sx={{ fontStyle: 'italic' }}>
                          {t('common.comingSoon')}
                        </Typography>
                      )}
                    </Box>
                  </Box>
                </Box>
              ))}
          </Box>
        </Box>
      </Dialog>

      {/* CTA - always visible above bottom bar, content scrolls under */}
      <Box
        sx={{
          position: 'fixed',
          left: 0,
          right: 0,
          bottom: 64,
          px: 2,
          pb: 1.5,
          pt: 1,
          bgcolor: 'background.paper',
          boxShadow: '0 -6px 18px rgba(15,23,42,0.18)',
          zIndex: 1200,
        }}
      >
        {orderWritePostLink ? (
          <Button
            variant="contained"
            fullWidth
            startIcon={<StorefrontRoundedIcon />}
            onClick={openWritePost}
          >
            {t('orders.writePost')}
          </Button>
        ) : channel.isOwnChannel ? (
          <Typography variant="body2" color="text.secondary" sx={{ py: 1, textAlign: 'center' }}>
            {t('channel.ownChannelNoBuy')}
          </Typography>
        ) : (
          <Button
            variant="contained"
            fullWidth
            startIcon={<StorefrontRoundedIcon />}
            disabled={!selectedFormat}
            onClick={handleBuy}
          >
            {t('common.buy')}
          </Button>
        )}
      </Box>

      {selectedFormat && channel && (
        <OrderPaymentDialog
          open={paymentDialogOpen}
          onClose={() => setPaymentDialogOpen(false)}
          onSuccess={handlePaymentSuccess}
          format={selectedFormat}
          channelId={channel.id}
        />
      )}
    </Box>
  )
}

