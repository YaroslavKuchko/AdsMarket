/**
 * Get the API base URL (always returns full URL, never empty).
 *
 * Hostname takes priority over VITE_API_BASE_URL so that when the app runs on
 * adsmarket.app it always uses that API, even if built with teamwb .env.
 */
export function getApiBase(): string {
  const hostname = window.location.hostname
  const origin = window.location.origin

  // Production: adsmarket.app — same origin (API at /api)
  if (hostname.endsWith('adsmarket.app') || hostname === 'adsmarket.app') {
    return origin || 'https://adsmarket.app'
  }

  // Check origin for Telegram WebApp (may be in iframe)
  if (origin.includes('adsmarket.app')) {
    return origin
  }

  // Production: teamwb.top -> api.teamwb.top
  if (hostname.endsWith('teamwb.top') || hostname === 'teamwb.top') {
    return 'https://api.teamwb.top'
  }
  if (origin.includes('teamwb.top')) {
    return 'https://api.teamwb.top'
  }

  // Local development
  if (hostname === 'localhost' || hostname === '127.0.0.1') {
    return 'http://localhost:3001'
  }

  // Fallback: env or same origin
  const envBase = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.trim() ?? ''
  return envBase || origin || 'https://adsmarket.app'
}

