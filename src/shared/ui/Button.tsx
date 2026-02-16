import { Button as MuiButton } from '@mui/material'
import type { ButtonProps as MuiButtonProps } from '@mui/material'

/**
 * App-level Button wrapper.
 * Keep it thin: use MUI theming for most styling.
 */
export type ButtonProps = MuiButtonProps

export function Button(props: ButtonProps) {
  return <MuiButton {...props} />
}


