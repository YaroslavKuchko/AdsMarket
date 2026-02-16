import { useEffect, useRef } from 'react'
import { postJson } from '../utils/api'
import { getApiBase } from '../utils/apiBase'

type WalletLike = { account?: { address?: string }; device?: { appName?: string; platform?: string } } | null

/**
 * Sync TON Connect wallet status with the backend.
 * Call with wallet from useTonWallet() to avoid duplicate hook calls.
 */
export function useTonWalletSync(wallet: WalletLike, token: string | undefined) {
  const previousAddressRef = useRef<string | null>(null)

  useEffect(() => {
    if (!token) {
      console.log('[WalletSync] No token, skipping sync')
      return
    }

    const currentAddress = wallet?.account?.address ?? null

    // Skip if address hasn't changed
    if (currentAddress === previousAddressRef.current) return

    const base = getApiBase()
    console.log('[WalletSync] API base:', base, 'Address:', currentAddress ? currentAddress.slice(0, 10) + '...' : 'null')
    console.log('[WalletSync] Token:', token ? `${token.slice(0, 20)}...` : 'null')

    const syncWallet = async () => {
      try {
        if (currentAddress && wallet) {
          // Wallet connected - notify backend
          // Log full wallet object to understand the structure
          console.log('[WalletSync] Full wallet object:', JSON.stringify(wallet, null, 2))
          
          const payload = {
            address: wallet?.account?.address || currentAddress,
            friendlyAddress: wallet?.account?.address || currentAddress,
            walletName: wallet?.device?.appName || wallet?.device?.platform || 'Unknown',
          }
          console.log('[WalletSync] Sending payload:', JSON.stringify(payload))
          
          try {
            const response = await postJson(`${base}/api/wallet/connect`, payload, {
              headers: { Authorization: `Bearer ${token}` },
            })
            console.log('[WalletSync] Wallet connected successfully:', response)
          } catch (apiError) {
            console.error('[WalletSync] API error:', apiError)
            // Try to get more details
            if (apiError instanceof Error) {
              console.error('[WalletSync] Error message:', apiError.message)
              // @ts-expect-error - bodyText is a custom property on ApiError
              console.error('[WalletSync] Error body:', apiError.bodyText)
            }
          }
        } else if (previousAddressRef.current) {
          // Wallet disconnected - notify backend
          console.log('[WalletSync] Disconnecting wallet from backend...')
          await postJson(`${base}/api/wallet/disconnect`, {}, {
            headers: { Authorization: `Bearer ${token}` },
          })
          console.log('[WalletSync] Wallet disconnected successfully')
        }
      } catch (e) {
        console.error('[WalletSync] Failed to sync wallet with backend:', e)
      }
    }

    previousAddressRef.current = currentAddress
    void syncWallet()
  }, [wallet, token])
}

