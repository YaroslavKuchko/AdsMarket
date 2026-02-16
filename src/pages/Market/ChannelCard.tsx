import CampaignRoundedIcon from '@mui/icons-material/CampaignRounded'
import VisibilityRoundedIcon from '@mui/icons-material/VisibilityRounded'
import { Avatar, Box, Chip, Typography } from '@mui/material'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import type { MarketChannel } from '../../shared/types/channel'
import { routes } from '../../app/router'
import { Card } from '../../shared/ui/Card'
import { formatNumberCompact } from '../../shared/utils/format'
import { getApiBase } from '../../shared/utils/apiBase'

export function ChannelCard({ channel }: { channel: MarketChannel }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const to = routes.channelDetails.replace(':channelId', String(channel.id))

  return (
    <Card
      clickable
      onClick={() => navigate(to)}
      sx={{ cursor: 'pointer' }}
    >
        <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'flex-start' }}>
        <Avatar
          src={`${getApiBase()}/api/media/channel-photo/${channel.id}`}
          sx={{
            width: 48,
            height: 48,
            bgcolor: 'primary.main',
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
              label={t('myChannels.status.active')}
              color="success"
              icon={<VisibilityRoundedIcon sx={{ fontSize: 14 }} />}
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
