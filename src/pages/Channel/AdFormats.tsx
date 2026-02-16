import { Box, Divider, Typography } from '@mui/material'
import { useTranslation } from 'react-i18next'
import { Badge } from '../../shared/ui/Badge'

type Format = {
  id: string
  titleKey: string
  descriptionKey: string
  etaKey: string
}

const mockFormats: Format[] = [
  {
    id: 'post',
    titleKey: 'channel.formats.items.post.title',
    descriptionKey: 'channel.formats.items.post.description',
    etaKey: 'channel.formats.items.post.eta',
  },
  {
    id: 'story',
    titleKey: 'channel.formats.items.story.title',
    descriptionKey: 'channel.formats.items.story.description',
    etaKey: 'channel.formats.items.story.eta',
  },
  {
    id: 'pin',
    titleKey: 'channel.formats.items.pin.title',
    descriptionKey: 'channel.formats.items.pin.description',
    etaKey: 'channel.formats.items.pin.eta',
  },
]

export function AdFormats() {
  const { t } = useTranslation()

  return (
    <Box>
      <Typography variant="subtitle1" sx={{ fontWeight: 800, mb: 1 }}>
        {t('channel.formats.title')}
      </Typography>
      <Box sx={{ border: 1, borderColor: 'divider', borderRadius: 2, overflow: 'hidden' }}>
        {mockFormats.map((f, idx) => (
          <Box key={f.id}>
            <Box sx={{ p: 1.5 }}>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 1 }}>
                <Typography sx={{ fontWeight: 700 }}>{t(f.titleKey)}</Typography>
                <Badge label={t(f.etaKey)} variant="outlined" />
              </Box>
              <Typography variant="body2" color="text.secondary">
                {t(f.descriptionKey)}
              </Typography>
            </Box>
            {idx < mockFormats.length - 1 ? <Divider /> : null}
          </Box>
        ))}
      </Box>
    </Box>
  )
}


