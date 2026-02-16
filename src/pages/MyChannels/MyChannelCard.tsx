import BlockRoundedIcon from '@mui/icons-material/BlockRounded'
import CampaignRoundedIcon from '@mui/icons-material/CampaignRounded'
import PauseCircleRoundedIcon from '@mui/icons-material/PauseCircleRounded'
import PendingRoundedIcon from '@mui/icons-material/PendingRounded'
import VisibilityRoundedIcon from '@mui/icons-material/VisibilityRounded'
import WarningAmberRoundedIcon from '@mui/icons-material/WarningAmberRounded'
import { Avatar, Box, Chip, Typography } from '@mui/material'
import { useTranslation } from 'react-i18next'
import { Card } from '../../shared/ui/Card'
import { formatNumberCompact } from '../../shared/utils/format'
import { getApiBase } from '../../shared/utils/apiBase'
import type { ChannelData } from './MyChannelsPage'

type MyChannelCardProps = {
  channel: ChannelData
  onClick?: () => void
}

const statusConfig = {
  pending: {
    color: 'warning' as const,
    icon: <PendingRoundedIcon sx={{ fontSize: 14 }} />,
    labelKey: 'myChannels.status.pending',
    isDisabled: false,
  },
  active: {
    color: 'success' as const,
    icon: <VisibilityRoundedIcon sx={{ fontSize: 14 }} />,
    labelKey: 'myChannels.status.active',
    isDisabled: false,
  },
  paused: {
    color: 'default' as const,
    icon: <PauseCircleRoundedIcon sx={{ fontSize: 14 }} />,
    labelKey: 'myChannels.status.paused',
    isDisabled: false,
  },
  inactive: {
    color: 'warning' as const,
    icon: <WarningAmberRoundedIcon sx={{ fontSize: 14 }} />,
    labelKey: 'myChannels.status.inactive',
    isDisabled: true,
  },
  removed: {
    color: 'error' as const,
    icon: <BlockRoundedIcon sx={{ fontSize: 14 }} />,
    labelKey: 'myChannels.status.removed',
    isDisabled: true,
  },
}

export function MyChannelCard({ channel, onClick }: MyChannelCardProps) {
  const { t } = useTranslation()

  const config = statusConfig[channel.status] || statusConfig.pending
  const isDisabled = config.isDisabled

  return (
    <Card
      clickable
      onClick={onClick}
      sx={isDisabled ? { opacity: 0.6, filter: 'grayscale(40%)' } : undefined}
    >
      <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'flex-start' }}>
        <Avatar
          src={channel.photoUrl ? `${getApiBase()}/api/media/channel-photo/${channel.id}` : undefined}
          sx={{
            width: 48,
            height: 48,
            bgcolor: isDisabled ? 'action.disabled' : 'primary.main',
          }}
        >
          <CampaignRoundedIcon />
        </Avatar>

        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.25 }}>
            <Typography
              sx={{
                fontWeight: 800,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                color: isDisabled ? 'text.disabled' : 'text.primary',
              }}
            >
              {channel.title}
            </Typography>
          </Box>

          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
            {channel.username && (
              <Typography variant="body2" color="text.secondary">
                @{channel.username}
              </Typography>
            )}
            <Typography variant="body2" color="text.secondary">
              • {formatNumberCompact(channel.subscriberCount)} {t('common.subsShort')}
            </Typography>
          </Box>

          <Box sx={{ mt: 1 }}>
            <Chip
              size="small"
              label={t(config.labelKey)}
              color={config.color}
              icon={config.icon ?? undefined}
              sx={{
                height: 22,
                fontSize: 11,
                fontWeight: 600,
                '& .MuiChip-icon': { fontSize: 14 },
              }}
            />
            {channel.category && (
              <Chip
                size="small"
                label={
                  (() => {
                    const key = channel.category ?? ''
                    const translated = t(`categories.${key}`)
                    // Если перевода нет (вернулся сам ключ), показываем сырой текст категории
                    return translated === `categories.${key}` ? key : translated
                  })()
                }
                variant="outlined"
                sx={{
                  ml: 0.5,
                  height: 22,
                  fontSize: 11,
                }}
              />
            )}
          </Box>
        </Box>
      </Box>
    </Card>
  )
}
