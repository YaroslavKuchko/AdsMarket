import SettingsRoundedIcon from '@mui/icons-material/SettingsRounded'
import CloseRoundedIcon from '@mui/icons-material/CloseRounded'
import {
  Box,
  Drawer,
  FormControl,
  IconButton,
  InputLabel,
  MenuItem,
  Select,
  Typography,
} from '@mui/material'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAppTheme } from '../../app/providers/ThemeProvider'
import { useAuth } from '../../app/providers/AuthProvider'

export function ProfileSettingsDrawer() {
  const { t, i18n } = useTranslation()
  const { preference, setPreference } = useAppTheme()
  const auth = useAuth()
  const [open, setOpen] = useState(false)

  const themeLabelId = 'profile-settings-theme-label'
  const themeSelectId = 'profile-settings-theme'
  const langLabelId = 'profile-settings-language-label'
  const langSelectId = 'profile-settings-language'

  return (
    <>
      <IconButton
        aria-label={t('profile.settings.title')}
        onClick={() => setOpen(true)}
        size="small"
        sx={{ bgcolor: 'background.paper', border: 1, borderColor: 'divider' }}
      >
        <SettingsRoundedIcon fontSize="small" />
      </IconButton>

      <Drawer
        anchor="right"
        open={open}
        onClose={() => setOpen(false)}
        PaperProps={{
          sx: {
            height: 'auto',
            top: 'auto',
            bottom: 'auto',
            mt: 'env(safe-area-inset-top)',
            borderRadius: 3,
            m: 1.5,
          },
        }}
      >
        <Box sx={{ width: 280, p: 2 }}>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <Typography sx={{ fontWeight: 900 }}>{t('profile.settings.title')}</Typography>
            <IconButton aria-label="Close" onClick={() => setOpen(false)} size="small">
              <CloseRoundedIcon fontSize="small" />
            </IconButton>
          </Box>

          <Box sx={{ display: 'grid', gap: 1.5, mt: 2 }}>
            <FormControl size="small" fullWidth>
              <InputLabel id={themeLabelId}>{t('profile.settings.theme')}</InputLabel>
              <Select
                labelId={themeLabelId}
                id={themeSelectId}
                label={t('profile.settings.theme')}
                value={preference}
                onChange={(e) => setPreference(e.target.value as typeof preference)}
              >
                <MenuItem value="auto">{t('profile.settings.themeAuto')}</MenuItem>
                <MenuItem value="light">{t('profile.settings.themeLight')}</MenuItem>
                <MenuItem value="dark">{t('profile.settings.themeDark')}</MenuItem>
              </Select>
            </FormControl>

            <FormControl size="small" fullWidth>
              <InputLabel id={langLabelId}>{t('profile.settings.language')}</InputLabel>
              <Select
                labelId={langLabelId}
                id={langSelectId}
                label={t('profile.settings.language')}
                value={i18n.language}
                onChange={(e) => {
                  const next = String(e.target.value)
                  void i18n.changeLanguage(next)
                  void auth.setPreferredLanguage(next)
                }}
              >
                <MenuItem value="en">{t('profile.settings.languageEn')}</MenuItem>
                <MenuItem value="ru">{t('profile.settings.languageRu')}</MenuItem>
              </Select>
            </FormControl>
          </Box>
        </Box>
      </Drawer>
    </>
  )
}


