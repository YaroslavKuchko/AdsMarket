import { Box, MenuItem, TextField, Typography } from '@mui/material'
import { useTranslation } from 'react-i18next'
import { Card } from '../../shared/ui/Card'
import { useAppTheme } from '../../app/providers/ThemeProvider'

export function SettingsBlock() {
  const { t, i18n } = useTranslation()
  const { preference, setPreference } = useAppTheme()

  return (
    <Card>
      <Typography sx={{ fontWeight: 800, mb: 1 }}>{t('profile.settings.title')}</Typography>

      <Box sx={{ display: 'grid', gap: 1 }}>
        <TextField
          size="small"
          select
          label={t('profile.settings.theme')}
          value={preference}
          onChange={(e) => setPreference(e.target.value as typeof preference)}
        >
          <MenuItem value="auto">{t('profile.settings.themeAuto')}</MenuItem>
          <MenuItem value="light">{t('profile.settings.themeLight')}</MenuItem>
          <MenuItem value="dark">{t('profile.settings.themeDark')}</MenuItem>
        </TextField>

        <TextField
          size="small"
          select
          label={t('profile.settings.language')}
          value={i18n.language}
          onChange={(e) => void i18n.changeLanguage(e.target.value)}
        >
          <MenuItem value="en">{t('profile.settings.languageEn')}</MenuItem>
          <MenuItem value="ru">{t('profile.settings.languageRu')}</MenuItem>
        </TextField>
      </Box>
    </Card>
  )
}


