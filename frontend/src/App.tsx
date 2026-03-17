import { useEffect, useState } from 'react'
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
  const { isAuthenticated, user, fetchMe } = useAuthStore()
  const [ready, setReady] = useState(false)

  // Sayfa yenilendiğinde token varsa kullanıcıyı çek — tamamlanana kadar bekle
  useEffect(() => {
    if (isAuthenticated && !user) {
      fetchMe().finally(() => setReady(true))
    } else {
      setReady(true)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  if (!ready && isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center text-gray-400">
          <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          Yükleniyor...
        </div>
      </div>
    )
  }

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
