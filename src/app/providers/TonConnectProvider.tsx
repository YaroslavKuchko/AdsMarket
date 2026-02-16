import { TonConnectUIProvider } from '@tonconnect/ui-react'
import type { ReactNode } from 'react'

// Manifest URL - use current origin so it works on adsmarket.app and teamwb.top
const getManifestUrl = () => {
  const origin = typeof window !== 'undefined' ? window.location.origin : ''
  if (origin) {
    return `${origin}/tonconnect-manifest.json`
  }
  return 'https://adsmarket.app/tonconnect-manifest.json'
}

type TonConnectProviderProps = {
  children: ReactNode
}

export function TonConnectProvider({ children }: TonConnectProviderProps) {
  return (
    <TonConnectUIProvider
      manifestUrl={getManifestUrl()}
      actionsConfiguration={{
        twaReturnUrl: 'https://t.me/ads_marketplacebot/adsmarket',
      }}
    >
      {children}
    </TonConnectUIProvider>
  )
}

