import { ImagePlus, Loader2, Trash2 } from 'lucide-react'
import { useRef } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'

import { useProductPhoto, useProductTags } from './api'
import type { Product } from './types'

const MAX_MB = 8
const TYPES = ['image/jpeg', 'image/png', 'image/webp']

/** Customer-facing extras shown in the menu detail sheet: photo, long description, tags, featured. */
export function MenuDetailsEditor({
  product,
  longDescription,
  onLongDescription,
  tags,
  onTags,
  featured,
  onFeatured,
}: {
  product: Product | null
  longDescription: string
  onLongDescription: (v: string) => void
  tags: string[]
  onTags: (t: string[]) => void
  featured: boolean
  onFeatured: (v: boolean) => void
}) {
  const allTags = useProductTags()
  const photo = useProductPhoto()
  const input = useRef<HTMLInputElement>(null)
  // The editor holds the product as it was when opened: show the latest upload result right away.
  const imageUrl = photo.data && product && photo.data.id === product.id ? photo.data.image_url : product?.image_url

  const pick = (file: File | undefined) => {
    if (!file || !product) return
    if (!TYPES.includes(file.type)) return toast.error('Subí una foto JPG, PNG o WebP')
    if (file.size > MAX_MB * 1024 * 1024) return toast.error(`La foto pesa demasiado (máximo ${MAX_MB} MB)`)
    photo.mutate({ id: product.id, file })
  }

  return (
    <div className="grid gap-4">
      <div className="flex items-start gap-4">
        <div className="flex size-28 shrink-0 items-center justify-center overflow-hidden rounded-2xl border bg-muted">
          {imageUrl ? (
            <img src={imageUrl} alt={`Foto de ${product?.name ?? 'producto'}`} className="size-full object-cover" />
          ) : (
            <ImagePlus className="size-8 text-muted-foreground" />
          )}
        </div>
        <div className="space-y-2">
          <p className="text-sm font-medium">Foto</p>
          {product ? (
            <>
              <p className="text-xs text-muted-foreground">JPG, PNG o WebP de hasta {MAX_MB} MB. Se achica y optimiza sola.</p>
              <div className="flex flex-wrap gap-2">
                <input
                  ref={input}
                  type="file"
                  accept={TYPES.join(',')}
                  className="sr-only"
                  aria-label="Elegir foto del producto"
                  data-testid="product-photo-input"
                  onChange={(e) => {
                    pick(e.target.files?.[0])
                    e.target.value = ''
                  }}
                />
                <Button type="button" variant="outline" size="sm" disabled={photo.isPending} onClick={() => input.current?.click()}>
                  {photo.isPending ? <Loader2 className="animate-spin" /> : <ImagePlus />}
                  {imageUrl ? 'Cambiar foto' : 'Subir foto'}
                </Button>
                {imageUrl && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="text-destructive"
                    disabled={photo.isPending}
                    onClick={() => photo.mutate({ id: product.id, file: null })}
                  >
                    <Trash2 /> Quitar
                  </Button>
                )}
              </div>
            </>
          ) : (
            <p className="text-xs text-muted-foreground">Guardá el producto para poder subirle una foto.</p>
          )}
        </div>
      </div>

      <div className="grid gap-1.5">
        <Label htmlFor="pe-long">Descripción larga (opcional)</Label>
        <Textarea
          id="pe-long"
          rows={3}
          maxLength={2000}
          placeholder="Lo que se lee al tocar el producto en el menú: origen del café, cómo se prepara…"
          value={longDescription}
          onChange={(e) => onLongDescription(e.target.value)}
        />
      </div>

      <div className="grid gap-1.5">
        <Label>Etiquetas</Label>
        <div className="flex flex-wrap gap-2">
          {allTags.data?.map((t) => {
            const on = tags.includes(t.code)
            return (
              <button
                key={t.code}
                type="button"
                aria-pressed={on}
                onClick={() => onTags(on ? tags.filter((x) => x !== t.code) : [...tags, t.code])}
                className={cn(
                  'h-9 rounded-full border px-3 text-sm transition-colors',
                  on ? 'border-primary bg-primary text-primary-foreground' : 'hover:bg-muted',
                )}
              >
                {t.label}
              </button>
            )
          })}
        </div>
      </div>

      <label className="flex items-center justify-between gap-3 rounded-xl border px-3 py-2.5">
        <span>
          <span className="block text-sm font-medium">Destacado</span>
          <span className="block text-xs text-muted-foreground">Se marca en el menú y su foto tiene prioridad en el menú online.</span>
        </span>
        <Switch checked={featured} onCheckedChange={onFeatured} />
      </label>
    </div>
  )
}
