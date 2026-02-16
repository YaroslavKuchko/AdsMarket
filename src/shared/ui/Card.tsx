import { Card as MuiCard, CardActionArea, CardContent } from '@mui/material'
import type { CardProps as MuiCardProps } from '@mui/material'
import type { ReactNode } from 'react'

export type CardProps = MuiCardProps & {
  clickable?: boolean
  onClick?: () => void
  /** When true, CardContent has no padding (for full-width media) */
  disableContentPadding?: boolean
  children: ReactNode
}

export function Card({ clickable, onClick, disableContentPadding, children, ...props }: CardProps) {
  const contentSx = disableContentPadding ? { p: 0, '&:last-child': { pb: 0 } } : undefined
  if (clickable) {
    return (
      <MuiCard {...props}>
        <CardActionArea onClick={onClick}>
          <CardContent sx={contentSx}>{children}</CardContent>
        </CardActionArea>
      </MuiCard>
    )
  }

  return (
    <MuiCard {...props}>
      <CardContent sx={contentSx}>{children}</CardContent>
    </MuiCard>
  )
}


