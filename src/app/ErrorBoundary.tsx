import { Box, Button, Typography } from '@mui/material'
import { Component, type ErrorInfo, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

type Props = {
  children: ReactNode
  fallback?: ReactNode
}

type State = {
  hasError: boolean
  error?: Error
}

/**
 * Catches React errors (e.g. hooks violation #310) and shows a friendly message
 * instead of the minified production error.
 */
export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }
      return <ErrorFallback error={this.state.error} onRetry={() => this.setState({ hasError: false })} />
    }
    return this.props.children
  }
}

function ErrorFallback({ onRetry }: { error?: Error; onRetry: () => void }) {
  const { t } = useTranslation()
  return (
    <Box sx={{ p: 3, textAlign: 'center' }}>
      <Typography variant="h6" sx={{ mb: 1, fontWeight: 700 }}>
        {t('error.somethingWentWrong')}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t('error.tryAgainOrRestart')}
      </Typography>
      <Button variant="contained" onClick={onRetry}>
        {t('error.retry')}
      </Button>
    </Box>
  )
}
