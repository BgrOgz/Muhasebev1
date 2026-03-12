/**
 * Zustand Auth Store — kullanıcı durumunu global olarak yönetir
 */
import { create } from 'zustand'
import { User } from '../types'
import { authApi } from '../services/api'

interface AuthState {
  user: User | null
  isLoading: boolean
  isAuthenticated: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  fetchMe: () => Promise<void>
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isLoading: false,
  isAuthenticated: !!localStorage.getItem('access_token'),

  login: async (email, password) => {
    set({ isLoading: true })
    try {
      const { data } = await authApi.login(email, password)
      const { access_token, refresh_token, user } = data.data
      localStorage.setItem('access_token', access_token)
      localStorage.setItem('refresh_token', refresh_token)
      set({ user, isAuthenticated: true, isLoading: false })
    } catch (err) {
      set({ isLoading: false })
      throw err
    }
  },

  logout: () => {
    authApi.logout()
    set({ user: null, isAuthenticated: false })
  },

  fetchMe: async () => {
    try {
      const { data } = await authApi.me()
      set({ user: data.data, isAuthenticated: true })
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status
      // Sadece 401 (geçersiz token) durumunda logout yap
      // Network hatası (backend kapalı) ise mevcut oturumu koru
      if (status === 401) {
        set({ user: null, isAuthenticated: false })
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
      }
    }
  },
}))
