import StorefrontRoundedIcon from '@mui/icons-material/StorefrontRounded'
import { Box, Skeleton, Typography } from '@mui/material'
import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { MarketChannel } from '../../shared/types/channel'
import { getApiBase } from '../../shared/utils/apiBase'
import { getJson } from '../../shared/utils/api'
import { MarketFilters } from './MarketFilters'
import { ChannelCard } from './ChannelCard'

export function MarketPage() {
  const { t } = useTranslation()
  const [channels, setChannels] = useState<MarketChannel[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [search, setSearch] = useState('')
  const [selectedCategory, setSelectedCategory] = useState<string>('all')
  const [audienceMin, setAudienceMin] = useState<number | null>(null)
  const [audienceMax, setAudienceMax] = useState<number | null>(null)
  const [priceMin, setPriceMin] = useState<number | null>(null)
  const [priceMax, setPriceMax] = useState<number | null>(null)

  useEffect(() => {
    const fetchMarket = async () => {
      const base = getApiBase()
      if (!base) {
        setLoading(false)
        return
      }

      setLoading(true)
      setError(null)

      try {
        const data = await getJson<MarketChannel[]>(`${base}/api/channels/market`)
        setChannels(data)
      } catch (e) {
        // eslint-disable-next-line no-console
        console.error('Failed to load market channels:', e)
        setError('Failed to load market')
      } finally {
        setLoading(false)
      }
    }

    void fetchMarket()
  }, [])

  const categories = useMemo(
    () => Array.from(new Set(channels.map((c) => c.category).filter((c): c is string => Boolean(c)))),
    [channels],
  )

  const audienceBounds = useMemo(() => {
    if (!channels.length) return null
    const subs = channels.map((c) => c.subscriberCount)
    return {
      min: Math.min(...subs),
      max: Math.max(...subs),
    }
  }, [channels])

  const priceBounds = useMemo(() => {
    const prices = channels
      .map((c) => c.priceFromUsdt)
      .filter((v): v is number => v != null && !Number.isNaN(v))
    if (!prices.length) return null
    return {
      min: Math.min(...prices),
      max: Math.max(...prices),
    }
  }, [channels])

  const filtered = useMemo(() => {
    return channels.filter((c) => {
      if (search.trim()) {
        // Нормализуем запрос: убираем пробелы и ведущий '@'
        const q = search.trim().toLowerCase().replace(/^@/, '')
        const haystack = [c.title, c.username ?? '', c.description ?? ''].join(' ').toLowerCase()
        if (!haystack.includes(q)) return false
      }

      if (selectedCategory !== 'all') {
        if (!c.category || c.category !== selectedCategory) return false
      }

      if (audienceMin != null && c.subscriberCount < audienceMin) return false
      if (audienceMax != null && c.subscriberCount > audienceMax) return false

      const hasPriceFilter = priceMin != null || priceMax != null
      if (hasPriceFilter) {
        if (c.priceFromUsdt == null) return false
        if (priceMin != null && c.priceFromUsdt < priceMin) return false
        if (priceMax != null && c.priceFromUsdt > priceMax) return false
      }

      return true
    })
  }, [channels, search, selectedCategory, audienceMin, audienceMax, priceMin, priceMax])

  const handleReset = () => {
    setSearch('')
    setSelectedCategory('all')
    setAudienceMin(null)
    setAudienceMax(null)
    setPriceMin(null)
    setPriceMax(null)
  }

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1.5 }}>
        <StorefrontRoundedIcon sx={{ fontSize: 28, color: 'primary.main' }} />
        <Typography variant="h5" sx={{ fontWeight: 800 }}>
          {t('market.title')}
        </Typography>
      </Box>

      <Box sx={{ mb: 2 }}>
        <MarketFilters
          search={search}
          onSearchChange={setSearch}
          categories={categories}
          selectedCategory={selectedCategory}
          onCategoryChange={setSelectedCategory}
          audienceMin={audienceMin}
          audienceMax={audienceMax}
          audienceBounds={audienceBounds}
          priceMin={priceMin}
          priceMax={priceMax}
          priceBounds={priceBounds}
          onAudienceChange={(min, max) => {
            setAudienceMin(min)
            setAudienceMax(max)
          }}
          onPriceChange={(min, max) => {
            setPriceMin(min)
            setPriceMax(max)
          }}
          onReset={handleReset}
        />
      </Box>

      {loading ? (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
          <Skeleton variant="rounded" height={96} />
          <Skeleton variant="rounded" height={96} />
        </Box>
      ) : error ? (
        <Typography variant="body2" color="error">
          {error}
        </Typography>
      ) : (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
          {filtered.map((c) => (
            <ChannelCard key={c.id} channel={c} />
          ))}
        </Box>
      )}
    </Box>
  )
}


