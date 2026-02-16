import {
  Box,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  TextField,
  Typography,
} from '@mui/material'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '../../shared/ui/Button'

type MarketFiltersProps = {
  search: string
  onSearchChange: (value: string) => void
  categories: string[]
  selectedCategory: string
  onCategoryChange: (value: string) => void
  audienceMin: number | null
  audienceMax: number | null
  audienceBounds: { min: number; max: number } | null
  priceMin: number | null
  priceMax: number | null
  priceBounds: { min: number; max: number } | null
  onAudienceChange: (min: number | null, max: number | null) => void
  onPriceChange: (min: number | null, max: number | null) => void
  onReset: () => void
}

export function MarketFilters({
  search,
  onSearchChange,
  categories,
  selectedCategory,
  onCategoryChange,
  audienceMin,
  audienceMax,
  audienceBounds,
  priceMin,
  priceMax,
  priceBounds,
  onAudienceChange,
  onPriceChange,
  onReset,
}: MarketFiltersProps) {
  const { t } = useTranslation()

  const categoryLabelId = 'market-filters-category-label'
  const categorySelectId = 'market-filters-category'

  const [audDialogOpen, setAudDialogOpen] = useState(false)
  const [audMinLocal, setAudMinLocal] = useState<string>('')
  const [audMaxLocal, setAudMaxLocal] = useState<string>('')

  const [priceDialogOpen, setPriceDialogOpen] = useState(false)
  const [priceMinLocal, setPriceMinLocal] = useState<string>('')
  const [priceMaxLocal, setPriceMaxLocal] = useState<string>('')

  const resolveCategoryLabel = (key: string) => {
    const translated = t(`categories.${key}`)
    return translated === `categories.${key}` ? key : translated
  }

  const openAudienceDialog = () => {
    setAudMinLocal(audienceMin != null ? String(audienceMin) : '')
    setAudMaxLocal(audienceMax != null ? String(audienceMax) : '')
    setAudDialogOpen(true)
  }

  const applyAudience = () => {
    const min = audMinLocal ? Number(audMinLocal) || null : null
    const max = audMaxLocal ? Number(audMaxLocal) || null : null
    onAudienceChange(min, max)
    setAudDialogOpen(false)
  }

  const openPriceDialog = () => {
    setPriceMinLocal(priceMin != null ? String(priceMin) : '')
    setPriceMaxLocal(priceMax != null ? String(priceMax) : '')
    setPriceDialogOpen(true)
  }

  const applyPrice = () => {
    const min = priceMinLocal ? Number(priceMinLocal) || null : null
    const max = priceMaxLocal ? Number(priceMaxLocal) || null : null
    onPriceChange(min, max)
    setPriceDialogOpen(false)
  }

  const audienceLabel = (() => {
    if (!audienceMin && !audienceMax) return t('market.filters.options.audience.any')
    return `${audienceMin ?? audienceBounds?.min ?? ''} — ${audienceMax ?? audienceBounds?.max ?? ''}`
  })()

  const priceLabel = (() => {
    if (!priceMin && !priceMax) return t('market.filters.options.price.any')
    return `${priceMin ?? priceBounds?.min ?? ''} — ${priceMax ?? priceBounds?.max ?? ''} USD`
  })()

  return (
    <>
      <Box
        sx={{
          display: 'grid',
          gap: 1,
          gridTemplateColumns: '1fr 1fr',
        }}
      >
        <TextField
          size="small"
          label={t('common.search')}
          placeholder={t('market.filters.searchPlaceholder')}
          fullWidth
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
        />
        <FormControl size="small" fullWidth>
          <InputLabel id={categoryLabelId}>{t('market.filters.category')}</InputLabel>
          <Select
            labelId={categoryLabelId}
            id={categorySelectId}
            label={t('market.filters.category')}
            value={selectedCategory}
            onChange={(e) => onCategoryChange(e.target.value)}
          >
            <MenuItem value="all">{t('market.filters.options.category.all')}</MenuItem>
            {categories.map((c) => (
              <MenuItem key={c} value={c}>
                {resolveCategoryLabel(c)}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        <Button
          variant="outlined"
          fullWidth
          size="small"
          onClick={openAudienceDialog}
          sx={{ justifyContent: 'flex-start' }}
        >
          {t('market.filters.audience')}: {audienceLabel}
        </Button>

        <Button
          variant="outlined"
          fullWidth
          size="small"
          onClick={openPriceDialog}
          sx={{ justifyContent: 'flex-start' }}
        >
          {t('market.filters.price')}: {priceLabel}
        </Button>

        <Box sx={{ display: 'flex', gap: 1, gridColumn: '1 / -1' }}>
          <Button variant="contained" fullWidth onClick={() => { /* фильтры применяются сразу */ }}>
            {t('common.apply')}
          </Button>
          <Button
            variant="outlined"
            fullWidth
            onClick={() => {
              onReset()
            }}
          >
            {t('common.reset')}
          </Button>
        </Box>
      </Box>

      {/* Audience dialog */}
      <Dialog open={audDialogOpen} onClose={() => setAudDialogOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle>{t('market.filters.audience')}</DialogTitle>
        <DialogContent>
          {audienceBounds && (
            <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block' }}>
              {audienceBounds.min} — {audienceBounds.max} {t('common.subsShort')}
            </Typography>
          )}
          <Box sx={{ display: 'flex', gap: 1, mt: 1 }}>
            <TextField
              label="От"
              type="number"
              size="small"
              fullWidth
              value={audMinLocal}
              onChange={(e) => setAudMinLocal(e.target.value)}
            />
            <TextField
              label="До"
              type="number"
              size="small"
              fullWidth
              value={audMaxLocal}
              onChange={(e) => setAudMaxLocal(e.target.value)}
            />
          </Box>
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button variant="outlined" onClick={() => setAudDialogOpen(false)}>
            {t('common.cancel')}
          </Button>
          <Button variant="contained" onClick={applyAudience}>
            {t('common.apply')}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Price dialog */}
      <Dialog open={priceDialogOpen} onClose={() => setPriceDialogOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle>{t('market.filters.price')}</DialogTitle>
        <DialogContent>
          {priceBounds && (
            <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: 'block' }}>
              {priceBounds.min} — {priceBounds.max} USD
            </Typography>
          )}
          <Box sx={{ display: 'flex', gap: 1, mt: 1 }}>
            <TextField
              label="От"
              type="number"
              size="small"
              fullWidth
              value={priceMinLocal}
              onChange={(e) => setPriceMinLocal(e.target.value)}
            />
            <TextField
              label="До"
              type="number"
              size="small"
              fullWidth
              value={priceMaxLocal}
              onChange={(e) => setPriceMaxLocal(e.target.value)}
            />
          </Box>
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button variant="outlined" onClick={() => setPriceDialogOpen(false)}>
            {t('common.cancel')}
          </Button>
          <Button variant="contained" onClick={applyPrice}>
            {t('common.apply')}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  )
}

