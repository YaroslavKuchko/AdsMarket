import CancelRoundedIcon from '@mui/icons-material/CancelRounded'
import EditRoundedIcon from '@mui/icons-material/EditRounded'
import OpenInNewRoundedIcon from '@mui/icons-material/OpenInNewRounded'
import VisibilityRoundedIcon from '@mui/icons-material/VisibilityRounded'
import { useState } from 'react'
import { Box, Button, Typography } from '@mui/material'
import { useTranslation } from 'react-i18next'
import type { Order } from '../../shared/types/order'
import { Badge } from '../../shared/ui/Badge'
import { Card } from '../../shared/ui/Card'
import { formatMoney } from '../../shared/utils/format'
import { getApiBase } from '../../shared/utils/apiBase'
import { postJson } from '../../shared/utils/api'
import { useAuth } from '../../app/providers/AuthProvider'

function statusMeta(status: Order['status']) {
  switch (status) {
    case 'draft':
      return { color: 'default' as const }
    case 'writing_post':
      return { color: 'info' as const }
    case 'pending_seller':
      return { color: 'warning' as const }
    case 'pending':
      return { color: 'warning' as const }
    case 'in_progress':
      return { color: 'info' as const }
    case 'done':
      return { color: 'success' as const }
    case 'cancelled':
      return { color: 'error' as const }
    default:
      return { color: 'default' as const }
  }
}

type OrderCardProps = { order: Order; onCancelled?: () => void }

export function OrderCard({ order, onCancelled }: OrderCardProps) {
  const { t } = useTranslation()
  const { token } = useAuth()
  const [cancelling, setCancelling] = useState(false)
  const s = statusMeta(order.status)

  const openLink = (link: string) => {
    if (typeof window.Telegram?.WebApp?.openTelegramLink === 'function') {
      window.Telegram.WebApp.openTelegramLink(link)
    } else {
      window.open(link, '_blank')
    }
  }

  const openWritePost = () => {
    if (order.writePostLink) openLink(order.writePostLink)
  }

  const openSellerViewPost = () => {
    if (order.sellerViewPostLink) openLink(order.sellerViewPostLink)
  }

  const openPublishedPost = () => {
    if (order.publishedPostLink) openLink(order.publishedPostLink)
  }

  const priceLabel =
    order.total != null
      ? formatMoney(order.total)
      :     order.totalStars != null
        ? `${order.totalStars} Stars`
        : order.totalTon != null
          ? `${order.totalTon} TON`
          : '—'

  const isSeller = order.isSeller === true
  const canCancel = !isSeller && (order.status === 'writing_post' || order.status === 'pending_seller')

  const handleCancel = async () => {
    if (!token || !canCancel || cancelling) return
    const base = getApiBase()
    setCancelling(true)
    try {
      await postJson(`${base}/api/orders/${order.id}/cancel`, {}, { headers: { Authorization: `Bearer ${token}` } })
      onCancelled?.()
    } catch (e) {
      console.error('Cancel order:', e)
    } finally {
      setCancelling(false)
    }
  }

  return (
    <Card sx={{ mb: 1.5 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', gap: 2, mb: 0.5 }}>
        <Typography sx={{ fontWeight: 800 }}>{order.channelTitle}</Typography>
        <Badge label={t(`orders.status.${order.status}`)} color={s.color} variant="outlined" />
      </Box>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
        {order.formatTitle} • {new Date(order.createdAtIso).toLocaleDateString()}
      </Typography>
      {isSeller && order.status === 'pending_seller' && (
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          {t('orders.sellerConfirmPost')}
        </Typography>
      )}
      {isSeller && order.status === 'done' && (
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          {order.autopostEnabled ? t('orders.sellerDoneAutopost') : t('orders.sellerDone')}
        </Typography>
      )}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 1 }}>
        <Typography sx={{ fontWeight: 800 }}>{priceLabel}</Typography>
        {order.status === 'writing_post' && order.writePostLink && (
          <Button
            size="small"
            variant="outlined"
            startIcon={<EditRoundedIcon />}
            onClick={openWritePost}
          >
            {t('orders.writePost')}
          </Button>
        )}
        {canCancel && (
          <Button
            size="small"
            variant="text"
            color="error"
            startIcon={<CancelRoundedIcon />}
            onClick={() => void handleCancel()}
            disabled={cancelling}
          >
            {cancelling ? '...' : t('orders.cancel')}
          </Button>
        )}
        {isSeller && order.status === 'pending_seller' && order.sellerViewPostLink && (
          <Button
            size="small"
            variant="outlined"
            startIcon={<VisibilityRoundedIcon />}
            onClick={openSellerViewPost}
          >
            {t('orders.viewPost')}
          </Button>
        )}
        {order.status === 'done' && order.publishedPostLink && (
          <Button
            size="small"
            variant="outlined"
            startIcon={<OpenInNewRoundedIcon />}
            onClick={openPublishedPost}
          >
            {t('orders.goToPost')}
          </Button>
        )}
      </Box>
    </Card>
  )
}
