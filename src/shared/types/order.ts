export type OrderStatus =
  | 'draft'
  | 'writing_post'
  | 'pending_seller'
  | 'pending'
  | 'in_progress'
  | 'done'
  | 'cancelled'

export type Order = {
  id: number
  orderId: number
  channelId: number
  channelTitle: string
  formatTitle: string
  createdAtIso: string
  status: OrderStatus
  total: number | null
  totalStars: number | null
  totalTon?: number | null
  writePostLink?: string | null
  /** Seller: link to view/approve post in bot (pending_seller only) */
  sellerViewPostLink?: string | null
  /** True if current user is the seller */
  isSeller?: boolean
  /** When order was completed (seller approved) */
  doneAtIso?: string | null
  /** Format has autopost: seller sees "money after X time" message */
  autopostEnabled?: boolean
  /** Link to published post in channel (when done) */
  publishedPostLink?: string | null
}
