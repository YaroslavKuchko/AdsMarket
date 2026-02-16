# Custom Icons

Добавляй сюда SVG иконки для проекта.

## Использование

1. Положи SVG файл в эту папку, например: `stars.svg`

2. Экспортируй в `index.ts`:
```ts
export { default as starsIcon } from './stars.svg'
```

3. Используй в компоненте:
```tsx
import { Icon } from '@/shared/ui/Icon'
import { starsIcon } from '@/shared/assets/icons'

<Icon src={starsIcon} alt="Stars" size={20} />
```

## Рекомендации

- Используй SVG без фиксированных цветов (fill="currentColor") для поддержки тем
- Оптимизируй SVG через [SVGO](https://jakearchibald.github.io/svgomg/)
- Размер: желательно 24x24 или кратный

