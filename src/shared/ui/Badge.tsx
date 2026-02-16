import { Chip } from '@mui/material'
import type { ChipProps } from '@mui/material'

/**
 * Telegram-like badge/pill.
 */
export type BadgeProps = ChipProps

export function Badge(props: BadgeProps) {
  return <Chip size="small" {...props} />
}


