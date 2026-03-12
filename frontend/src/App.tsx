import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useNavigate } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Login } from './pages/Login'
import { Dashboard } from './pages/Dashboard'
import { Approvals } from './pages/Approvals'
import { Reports } from './pages/Reports'
import { Admin } from './pages/Admin'
import { useAuthStore } from './store/authStore'
import { setGlobalNavigate } from './services/api'

// Global navigate'i BrowserRouter içinden set et
function NavigationSetup() {
  const navigate = useNavigate()
  useEffect(() => {
    setGlobalNavigate(navigate)
  }, [navigate])
  return null
}

// Korumalı route bileşeni
function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore()
  return isAuthenticated ? <>{children}</> : <Navigate to="/login" replace />
}

// Admin-only route
function AdminRoute({ children }: { children: React.ReactNode }) {
  const { user } = useAuthStore()
  return user?.role === 'admin' ? <>{children}</> : <Navigate to="/" replace />
}

export function App() {
  const { isAuthenticated, fetchMe } = useAuthStore()

  // Sayfa yenilendiğinde token varsa kullanıcıyı çek
  useEffect(() => {
    if (isAuthenticated) {
      fetchMe()
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <BrowserRouter>
      <NavigationSetup />
      <Routes>
        {/* Public */}
        <Route path="/login" element={<Login />} />

        {/* Korumalı — Layout wrapper */}
        <Route
          element={
            <PrivateRoute>
              <Layout />
            </PrivateRoute>
          }
        >
          <Route index element={<Dashboard />} />
          <Route path="approvals" element={<Approvals />} />
          <Route path="reports" element={<Reports />} />
          <Route
            path="admin"
            element={
              <AdminRoute>
                <Admin />
              </AdminRoute>
            }
          />
        </Route>

        {/* Catch-all */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
