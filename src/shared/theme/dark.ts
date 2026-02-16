import { createTheme } from '@mui/material/styles'
import { tokens } from './tokens'

// Telegram dark-like neutrals (still keeping primary green)
const dark = {
  bg: '#0B1220',
  card: '#0F172A',
  border: 'rgba(226, 232, 240, 0.12)',
  textPrimary: '#E2E8F0',
  textSecondary: '#94A3B8',
} as const

export function createDarkTheme() {
  return createTheme({
    palette: {
      mode: 'dark',
      primary: {
        main: tokens.colors.primary,
      },
      background: {
        default: dark.bg,
        paper: dark.card,
      },
      divider: dark.border,
      text: {
        primary: dark.textPrimary,
        secondary: dark.textSecondary,
      },
      warning: { main: tokens.colors.warning },
      error: { main: tokens.colors.error },
    },
    shape: {
      borderRadius: tokens.radius.md,
    },
    typography: {
      fontFamily: tokens.typography.fontFamily,
      button: { textTransform: 'none', fontWeight: 600 },
    },
    components: {
      MuiPaper: {
        styleOverrides: {
          root: {
            backgroundImage: 'none',
          },
        },
      },
      MuiButton: {
        defaultProps: {
          disableElevation: true,
        },
        styleOverrides: {
          root: {
            borderRadius: tokens.radius.md,
          },
        },
      },
      MuiCard: {
        styleOverrides: {
          root: {
            borderRadius: tokens.radius.lg,
            border: `1px solid ${dark.border}`,
          },
        },
      },
      MuiChip: {
        styleOverrides: {
          root: {
            borderRadius: 999,
          },
        },
      },
    },
  })
}


