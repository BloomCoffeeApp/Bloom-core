import { BadgePercent, CupSoda, Layers, Package, Tags } from 'lucide-react'
import { Suspense } from 'react'
import { Route, Routes, useSearchParams } from 'react-router'

import { PageHeader } from '@/components/page-header'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useModules } from '@/features/business/api'
import { useHasFeature } from '@/features/license/api'
import { UpgradeCard } from '@/features/license/pro-gate'
import { proModules } from '@pro'

import { CategoriesTab } from './CategoriesTab'
import { ModifiersTab } from './ModifiersTab'
import { ProductsTab } from './ProductsTab'
import { SizesTab } from './SizesTab'

function CatalogPage() {
  const [params, setParams] = useSearchParams()
  const promosOn = useModules().on('promos')
  const requested = params.get('tab') || 'productos'
  const tab = requested === 'promos' && !promosOn ? 'productos' : requested
  const promosPro = useHasFeature('promos')
  return (
    <div>
      <PageHeader title="Productos" description="Carta, tamaños, recetas, costos y márgenes." />
      <Tabs value={tab} onValueChange={(v) => setParams({ tab: v }, { replace: true })} className="gap-4">
        <TabsList>
          <TabsTrigger value="productos">
            <Package /> Productos
          </TabsTrigger>
          <TabsTrigger value="categorias">
            <Tags /> Categorías
          </TabsTrigger>
          <TabsTrigger value="tamanos">
            <CupSoda /> Tamaños
          </TabsTrigger>
          <TabsTrigger value="modificadores">
            <Layers /> Modificadores
          </TabsTrigger>
          {promosOn && (
            <TabsTrigger value="promos">
              <BadgePercent /> Promos
            </TabsTrigger>
          )}
        </TabsList>
        <TabsContent value="productos">
          <ProductsTab />
        </TabsContent>
        <TabsContent value="categorias">
          <CategoriesTab />
        </TabsContent>
        <TabsContent value="tamanos">
          <SizesTab />
        </TabsContent>
        <TabsContent value="modificadores">
          <ModifiersTab />
        </TabsContent>
        <TabsContent value="promos">
          {!proModules.PromosTab ? (
            <UpgradeCard feature="promos" compact notIncluded />
          ) : promosPro === false ? (
            <UpgradeCard feature="promos" compact />
          ) : (
            <Suspense fallback={<Skeleton className="h-40 rounded-2xl" />}>
              <proModules.PromosTab />
            </Suspense>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}

export default function CatalogModule() {
  return (
    <Routes>
      <Route path="*" element={<CatalogPage />} />
    </Routes>
  )
}
