import { Box, Typography } from '@mui/material'
import type { ReactNode } from 'react'

export function EmptyState({
  title,
  description,
  icon,
}: {
  title: string
  description?: string
  icon?: ReactNode
}) {
  return (
    <Box
      sx={{
        py: 6,
        px: 2,
        textAlign: 'center',
        color: 'text.secondary',
      }}
    >
      {icon ? <Box sx={{ mb: 2, display: 'flex', justifyContent: 'center' }}>{icon}</Box> : null}
      <Typography variant="h6" sx={{ mb: 1, color: 'text.primary' }}>
        {title}
      </Typography>
      {description ? <Typography variant="body2">{description}</Typography> : null}
    </Box>
  )
}


