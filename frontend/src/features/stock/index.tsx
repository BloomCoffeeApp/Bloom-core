import { Route, Routes } from 'react-router'

import { CountDetailPage, CountListPage } from './CountPage'
import { StockPage } from './StockPage'
import { SuggestionsPage } from './SuggestionsPage'

export default function StockModule() {
  return (
    <Routes>
      <Route index element={<StockPage />} />
      <Route path="conteo" element={<CountListPage />} />
      <Route path="conteo/:id" element={<CountDetailPage />} />
      <Route path="sugerencias" element={<SuggestionsPage />} />
    </Routes>
  )
}
