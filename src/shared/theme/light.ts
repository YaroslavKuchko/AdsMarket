import { createTheme } from '@mui/material/styles'
import { tokens } from './tokens'

export function createLightTheme() {
  return createTheme({
    palette: {
      mode: 'light',
      primary: {
        main: tokens.colors.primary,
      },
      background: {
        default: tokens.colors.bg,
        paper: tokens.colors.card,
      },
      divider: tokens.colors.border,
      text: {
        primary: tokens.colors.textPrimary,
        secondary: tokens.colors.textSecondary,
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
            border: `1px solid ${tokens.colors.border}`,
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


