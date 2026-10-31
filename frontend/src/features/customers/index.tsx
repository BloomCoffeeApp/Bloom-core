import { Route, Routes } from 'react-router'

import { CustomerDetailPage } from './CustomerDetailPage'
import { CustomersPage } from './CustomersPage'

export default function CustomersModule() {
  return (
    <Routes>
      <Route index element={<CustomersPage />} />
      <Route path=":id" element={<CustomerDetailPage />} />
    </Routes>
  )
}
