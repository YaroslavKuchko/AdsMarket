import ReceiptLongRoundedIcon from '@mui/icons-material/ReceiptLongRounded'
import { Box, Button, CircularProgress, Tab, Tabs, Typography } from '@mui/material'
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useAuth } from '../../app/providers/AuthProvider'
import { getApiBase } from '../../shared/utils/apiBase'
import { ApiError, getJson } from '../../shared/utils/api'
import type { Order } from '../../shared/types/order'
import { OrderCard } from './OrderCard'

const STORAGE_KEY = 'orders_tab_last_seen'

type OrderTab = 'active' | 'done' | 'all'

function filterOrders(orders: Order[], tab: OrderTab): Order[] {
  if (tab === 'all') return orders
  if (tab === 'done') return orders.filter((o) => o.status === 'done')
  return orders.filter(
    (o) =>
      o.status === 'writing_post' ||
      o.status === 'pending_seller' ||
      o.status === 'pending' ||
      o.status === 'in_progress'
  )
}

function getLastSeen(tab: OrderTab): number {
  try {
    const raw = localStorage.getItem(`${STORAGE_KEY}_${tab}`)
    return raw ? parseInt(raw, 10) || 0 : 0
  } catch {
    return 0
  }
}

function setLastSeen(tab: OrderTab) {
  try {
    localStorage.setItem(`${STORAGE_KEY}_${tab}`, String(Date.now()))
  } catch {
    // ignore
  }
}

function countNewSince(orders: Order[], sinceMs: number): number {
  if (sinceMs <= 0) return 0
  const since = new Date(sinceMs).toISOString()
  return orders.filter((o) => o.createdAtIso >= since).length
}

export function OrdersPage() {
  const { t } = useTranslation()
  const { token } = useAuth()
  const [orders, setOrders] = useState<Order[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState<OrderTab>('active')

  const load = useCallback(async () => {
    if (!token) {
      setLoading(false)
      return
    }
    const base = getApiBase()
    setLoading(true)
    setError(null)
    try {
      const data = await getJson<Order[]>(`${base}/api/orders`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      setOrders(Array.isArray(data) ? data : [])
    } catch (e) {
      console.error('Failed to load orders:', e)
      let message = t('common.retry')
      if (e instanceof ApiError && e.bodyText) {
        try {
          const body = JSON.parse(e.bodyText) as { detail?: string }
          if (typeof body.detail === 'string') message = body.detail
        } catch {
          // keep default
        }
      }
      setError(message)
    } finally {
      setLoading(false)
    }
  }, [token, t])

  useEffect(() => {
    void load()
  }, [load])

  const filteredOrders = useMemo(() => filterOrders(orders, tab), [orders, tab])

  const handleTabChange = (_: React.SyntheticEvent, value: OrderTab) => {
    setTab(value)
    setLastSeen(value)
  }

  const activeTabOrders = useMemo(() => filterOrders(orders, 'active'), [orders])
  const doneTabOrders = useMemo(() => filterOrders(orders, 'done'), [orders])
  const allTabOrders = orders

  const newInActive = countNewSince(activeTabOrders, getLastSeen('active'))
  const newInDone = countNewSince(doneTabOrders, getLastSeen('done'))
  const newInAll = countNewSince(allTabOrders, getLastSeen('all'))

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
        <ReceiptLongRoundedIcon sx={{ fontSize: 28, color: 'primary.main' }} />
        <Typography variant="h5" sx={{ fontWeight: 800 }}>
          {t('orders.title')}
        </Typography>
      </Box>
      <Tabs
        value={tab}
        onChange={handleTabChange}
        variant="fullWidth"
        sx={{
          mb: 2,
          minHeight: 40,
          '& .MuiTab-root': { minHeight: 40, py: 1 },
        }}
      >
        <Tab
          label={
            <Box component="span" sx={{ position: 'relative', pr: newInAll > 0 ? 2 : 0 }}>
              {t('orders.tabAll')}
              {newInAll > 0 && (
                <Box
                  sx={{
                    position: 'absolute',
                    top: -2,
                    right: -4,
                    width: 8,
                    height: 8,
                    borderRadius: '50%',
                    bgcolor: 'error.main',
                  }}
                />
              )}
            </Box>
          }
          value="all"
        />
        <Tab
          label={
            <Box component="span" sx={{ position: 'relative', pr: newInActive > 0 ? 2 : 0 }}>
              {t('orders.tabActive')}
              {newInActive > 0 && (
                <Box
                  sx={{
                    position: 'absolute',
                    top: -2,
                    right: -4,
                    width: 8,
                    height: 8,
                    borderRadius: '50%',
                    bgcolor: 'error.main',
                  }}
                />
              )}
            </Box>
          }
          value="active"
        />
        <Tab
          label={
            <Box component="span" sx={{ position: 'relative', pr: newInDone > 0 ? 2 : 0 }}>
              {t('orders.tabDone')}
              {newInDone > 0 && (
                <Box
                  sx={{
                    position: 'absolute',
                    top: -2,
                    right: -4,
                    width: 8,
                    height: 8,
                    borderRadius: '50%',
                    bgcolor: 'error.main',
                  }}
                />
              )}
            </Box>
          }
          value="done"
        />
      </Tabs>
      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
          <CircularProgress size={28} />
        </Box>
      ) : error ? (
        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: 1 }}>
          <Typography color="error">{error}</Typography>
          <Button variant="outlined" size="small" onClick={() => void load()}>
            {t('common.retry')}
          </Button>
        </Box>
      ) : filteredOrders.length === 0 ? (
        <Typography variant="body2" color="text.secondary">
          {t('orders.empty')}
        </Typography>
      ) : (
        filteredOrders.map((o) => <OrderCard key={o.id} order={o} onCancelled={load} />)
      )}
    </Box>
  )
}
