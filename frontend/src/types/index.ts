// ── Kullanıcı ──────────────────────────────────────────────────────────────

export interface User {
  id: string
  email: string
  name: string
  role: 'admin' | 'approver' | 'viewer'
  department?: string
  is_active: boolean
}

// ── Fatura ─────────────────────────────────────────────────────────────────

export type InvoiceStatus =
  | 'draft'
  | 'processing'
  | 'awaiting_first_approval'
  | 'returned'
  | 'awaiting_final_approval'
  | 'approved'
  | 'rejected'
  | 'archived'

export type RiskLevel = 'low' | 'medium' | 'high'

export interface Invoice {
  id: string
  invoice_number: string
  invoice_date: string
  due_date?: string
  amount: number
  tax_amount: number
  total_amount: number
  currency: string
  status: InvoiceStatus
  category?: string
  risk_level?: RiskLevel
  source_email?: string
  source_filename?: string
  created_at: string
  supplier?: {
    id: string
    name: string
    vat_number?: string
  }
  classification?: Classification
  approvals?: Approval[]
}

// ── Sınıflandırma ──────────────────────────────────────────────────────────

export interface Classification {
  id: string
  category: string
  risk_level: RiskLevel
  confidence_score: number
  suggested_account?: string
  suggested_payment_method?: string
  ai_notes?: string
  anomalies: Anomaly[]
  created_at: string
}

export interface Anomaly {
  type: string
  severity: 'low' | 'medium' | 'high'
  message: string
}

// ── Onay ───────────────────────────────────────────────────────────────────

export type ApprovalLevel = 'first' | 'final'
export type ApprovalStatus = 'pending' | 'approved' | 'rejected'

export interface Approval {
  id: string
  approval_level: ApprovalLevel
  status: ApprovalStatus
  comments?: string
  reason_rejected?: string
  approved_at?: string
  created_at: string
  invoice: {
    id: string
    invoice_number: string
    supplier: string
    amount: number
    status: InvoiceStatus
    category?: string
    risk_level?: RiskLevel
  }
}

// ── Raporlar ───────────────────────────────────────────────────────────────

export interface ReportSummary {
  total_invoices: number
  total_amount: number
  pending_count: number
  approved_count: number
  rejected_count: number
  avg_confidence: number
  by_category: CategoryStat[]
  by_supplier: SupplierStat[]
  by_risk: { level: string; count: number }[]
  period: {
    start: string
    end: string
  }
}

export interface CategoryStat {
  category: string
  count: number
  total_amount: number
}

export interface SupplierStat {
  supplier_name: string
  invoice_count: number
  total_amount: number
}

// ── Pagination ─────────────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  status: string
  data: {
    items: T[]
    total: number
    page: number
    per_page: number
    total_pages: number
  }
}

export interface ApiResponse<T> {
  status: string
  data: T
}
