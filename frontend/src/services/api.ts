/**
 * API Client — Axios + JWT otomatik ekleme + token yenileme
 */
import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'

const BASE_URL = '/api/v1'

// ── Global navigate — sayfa yeniden yüklenmeden /login'e gitmeye yarar ──────
// App.tsx içinde setGlobalNavigate(navigate) çağrısıyla set edilir
let _navigate: ((path: string) => void) | null = null
export function setGlobalNavigate(fn: (path: string) => void) {
  _navigate = fn
}

function goToLogin() {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
  if (_navigate) {
    _navigate('/login')
  } else {
    // React yüklenmediyse fallback
    window.location.replace('/login')
  }
}

export const api = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
})

// ── Request interceptor: her isteğe token ekle ─────────────────────────────
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = localStorage.getItem('access_token')
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// ── Response interceptor: 401 → refresh token dene ────────────────────────
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as InternalAxiosRequestConfig & { _retry?: boolean }

    if (error.response?.status === 401 && !original._retry) {
      original._retry = true
      const refreshToken = localStorage.getItem('refresh_token')
      if (refreshToken) {
        try {
          const { data } = await axios.post(`${BASE_URL}/auth/refresh`, {
            refresh_token: refreshToken,
          })
          const newToken = data.data.access_token
          localStorage.setItem('access_token', newToken)
          if (original.headers) {
            original.headers.Authorization = `Bearer ${newToken}`
          }
          return api(original)
        } catch {
          // Refresh başarısız → logout (soft navigate)
          goToLogin()
        }
      } else {
        goToLogin()
      }
    }
    return Promise.reject(error)
  }
)

// ── Auth ───────────────────────────────────────────────────────────────────

export const authApi = {
  login: (email: string, password: string) =>
    api.post('/auth/login', { email, password }),

  me: () => api.get('/auth/me'),

  logout: () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
  },
}

// ── Faturalar ──────────────────────────────────────────────────────────────

export const invoicesApi = {
  list: (params?: {
    page?: number
    per_page?: number
    status?: string
    category?: string
    risk_level?: string
    search?: string
  }) => api.get('/invoices', { params }),

  get: (id: string) => api.get(`/invoices/${id}`),

  upload: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api.post('/invoices', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  reclassify: (id: string) => api.post(`/invoices/${id}/reclassify`),

  auditLog: (id: string) => api.get(`/invoices/${id}/audit-log`),
}

// ── Onaylar ────────────────────────────────────────────────────────────────

export const approvalsApi = {
  list: (params?: {
    status?: string
    approval_level?: string
    page?: number
    per_page?: number
  }) => api.get('/approvals', { params }),

  action: (
    id: string,
    body: {
      status: 'approved' | 'rejected'
      comments?: string
      reason_rejected?: string
    }
  ) => api.patch(`/approvals/${id}`, body),
}

// ── Raporlar ────────────────────────────────────────────────────────────────

export const reportsApi = {
  summary: (params?: { start_date?: string; end_date?: string }) =>
    api.get('/reports/summary', { params }),

  categories: (params?: { start_date?: string; end_date?: string }) =>
    api.get('/reports/categories', { params }),

  exportCsv: () =>
    api.get('/reports/export', { responseType: 'blob' }),
}

// ── Sistem ─────────────────────────────────────────────────────────────────

export const systemApi = {
  schedulerStatus: () => api.get('/system/scheduler-status'),
  pollNow: () => api.post('/system/poll-now'),
  emailLogs: (limit = 50) => api.get(`/system/email-logs?limit=${limit}`),
}

// ── Admin ──────────────────────────────────────────────────────────────────

export const adminApi = {
  // Kullanıcılar
  listUsers: (params?: {
    role?: string
    is_active?: boolean
    search?: string
    page?: number
    per_page?: number
  }) => api.get('/admin/users', { params }),

  createUser: (body: {
    email: string
    name: string
    password: string
    role: string
    department?: string
  }) => api.post('/admin/users', body),

  updateUser: (id: string, body: {
    name?: string
    role?: string
    department?: string
    is_active?: boolean
  }) => api.patch(`/admin/users/${id}`, body),

  deleteUser: (id: string) => api.delete(`/admin/users/${id}`),

  // Tedarikçiler
  listSuppliers: (params?: {
    search?: string
    page?: number
    per_page?: number
  }) => api.get('/admin/suppliers', { params }),

  getSupplier: (id: string) => api.get(`/admin/suppliers/${id}`),

  updateSupplier: (id: string, body: Record<string, unknown>) =>
    api.patch(`/admin/suppliers/${id}`, body),

  // Audit loglar
  listAuditLogs: (params?: {
    action?: string
    user_id?: string
    invoice_id?: string
    start_date?: string
    end_date?: string
    page?: number
    per_page?: number
  }) => api.get('/admin/audit-logs', { params }),

  exportAuditLogs: (params?: { start_date?: string; end_date?: string }) =>
    api.get('/admin/audit-logs/export', { params, responseType: 'blob' }),
}
