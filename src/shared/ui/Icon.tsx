import { Box, type SxProps, type Theme } from '@mui/material'

type IconProps = {
  /** Path to the icon (imported SVG or URL) */
  src: string
  /** Alt text for accessibility */
  alt?: string
  /** Size in pixels (default: 24) */
  size?: number
  /** Additional MUI sx props */
  sx?: SxProps<Theme>
  /** Optional className */
  className?: string
}

/**
 * Icon component for custom SVG icons.
 *
 * Usage:
 * ```tsx
 * import starsIcon from '@/shared/assets/icons/stars.svg'
 * <Icon src={starsIcon} alt="Stars" size={20} />
 * ```
 */
export function Icon({ src, alt = '', size = 24, sx, className }: IconProps) {
  return (
    <Box
      component="img"
      src={src}
      alt={alt}
      className={className}
      sx={{
        width: size,
        height: size,
        objectFit: 'contain',
        flexShrink: 0,
        ...sx,
      }}
    />
  )
}

