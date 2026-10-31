import { Layers, Package, Tags } from 'lucide-react'
import { Route, Routes, useSearchParams } from 'react-router'

import { PageHeader } from '@/components/page-header'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

import { CategoriesTab } from './CategoriesTab'
import { ModifiersTab } from './ModifiersTab'
import { ProductsTab } from './ProductsTab'

function CatalogPage() {
  const [params, setParams] = useSearchParams()
  const tab = params.get('tab') || 'productos'
  return (
    <div>
      <PageHeader title="Productos" description="Carta, recetas, costos y márgenes." />
      <Tabs value={tab} onValueChange={(v) => setParams({ tab: v }, { replace: true })} className="gap-4">
        <TabsList>
          <TabsTrigger value="productos">
            <Package /> Productos
          </TabsTrigger>
          <TabsTrigger value="categorias">
            <Tags /> Categorías
          </TabsTrigger>
          <TabsTrigger value="modificadores">
            <Layers /> Modificadores
          </TabsTrigger>
        </TabsList>
        <TabsContent value="productos">
          <ProductsTab />
        </TabsContent>
        <TabsContent value="categorias">
          <CategoriesTab />
        </TabsContent>
        <TabsContent value="modificadores">
          <ModifiersTab />
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
