import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface FiltersState {
  // Dashboard filters
  dashboardSearch: string
  dashboardStatus: string
  dashboardRisk: string

  // Approvals filters
  approvalsStatus: string
  approvalsLevel: string

  // Reports filters
  reportsStartDate: string
  reportsEndDate: string

  // Actions
  setDashboardSearch: (search: string) => void
  setDashboardStatus: (status: string) => void
  setDashboardRisk: (risk: string) => void
  resetDashboardFilters: () => void

  setApprovalsStatus: (status: string) => void
  setApprovalsLevel: (level: string) => void
  resetApprovalsFilters: () => void

  setReportsDateRange: (startDate: string, endDate: string) => void
  resetReportsFilters: () => void

  resetAll: () => void
}

const initialState = {
  dashboardSearch: '',
  dashboardStatus: '',
  dashboardRisk: '',
  approvalsStatus: '',
  approvalsLevel: '',
  reportsStartDate: '',
  reportsEndDate: '',
}

export const useFiltersStore = create<FiltersState>()(
  persist(
    (set) => ({
      ...initialState,

      setDashboardSearch: (search) => set({ dashboardSearch: search }),
      setDashboardStatus: (status) => set({ dashboardStatus: status }),
      setDashboardRisk: (risk) => set({ dashboardRisk: risk }),
      resetDashboardFilters: () =>
        set({
          dashboardSearch: '',
          dashboardStatus: '',
          dashboardRisk: '',
        }),

      setApprovalsStatus: (status) => set({ approvalsStatus: status }),
      setApprovalsLevel: (level) => set({ approvalsLevel: level }),
      resetApprovalsFilters: () =>
        set({
          approvalsStatus: '',
          approvalsLevel: '',
        }),

      setReportsDateRange: (startDate, endDate) =>
        set({ reportsStartDate: startDate, reportsEndDate: endDate }),
      resetReportsFilters: () =>
        set({
          reportsStartDate: '',
          reportsEndDate: '',
        }),

      resetAll: () => set(initialState),
    }),
    {
      name: 'filters-storage',
      partialize: (state) => ({
        dashboardSearch: state.dashboardSearch,
        dashboardStatus: state.dashboardStatus,
        dashboardRisk: state.dashboardRisk,
      }),
    }
  )
)
