import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from '../components/AppShell'
import { ComparePage } from './ComparePage'
import { CompanionPage } from './CompanionPage'
import {
  ModelsPage,
  NotFoundPage,
  ProductDetailPage,
  ProductsPage,
  ReviewPage,
  UploadPage,
} from './pages'

export function AppRoutes() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Navigate to="/products" replace />} />
        <Route path="products" element={<ProductsPage />} />
        <Route path="products/:id" element={<ProductDetailPage />} />
        <Route path="products/:id/reviews" element={<ProductDetailPage view="reviews" />} />
        <Route path="products/:id/advanced" element={<ProductDetailPage view="advanced" />} />
        <Route path="products/:id/settings" element={<ProductDetailPage view="settings" />} />
        <Route path="products/:id/review" element={<ReviewPage />} />
        <Route path="products/:id/upload" element={<UploadPage />} />
        <Route path="models" element={<ModelsPage />} />
        <Route path="compare" element={<ComparePage />} />
        <Route path="companion" element={<CompanionPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
