import { useEffect, useState, useCallback, useRef } from 'react'
import {
  FileText,
  CheckCircle,
  Clock,
  XCircle,
  Upload,
  RefreshCw,
  Search,
  Filter,
  TrendingUp,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react'
import { invoicesApi } from '../services/api'
import { Invoice, InvoiceStatus } from '../types'
import { RiskBadge } from '../components/RiskBadge'
import { StatusBadge } from '../components/StatusBadge'

// ── Statistic Card Component ────────────────────────────────────────────────

function StatCard({
  title,
  value,
  icon: Icon,
  color,
  sub,
}: {
  title: string
  value: string | number
  icon: React.ElementType
  color: string
  sub?: string
}) {
  return (
    <div className="card flex items-center gap-4">
      <div
        className={`w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0 ${color}`}
      >
        <Icon size={22} className="text-white" />
      </div>
      <div>
        <p className="text-sm text-gray-500">{title}</p>
        <p className="text-2xl font-bold text-gray-900">{value}</p>
        {sub && <p className="text-xs text-gray-400">{sub}</p>}
      </div>
    </div>
  )
}

// ── Constants ──────────────────────────────────────────────────────────────

const STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: '', label: 'Tüm Durumlar' },
  { value: 'awaiting_first_approval', label: '1. Onay Bekliyor' },
  { value: 'awaiting_final_approval', label: 'Patron Onayı' },
  { value: 'approved', label: 'Onaylandı' },
  { value: 'rejected', label: 'Reddedildi' },
  { value: 'processing', label: 'İşleniyor' },
  { value: 'returned', label: 'İade Edildi' },
]

const RISK_OPTIONS = [
  { value: '', label: 'Tüm Riskler' },
  { value: 'low', label: '🟢 Düşük' },
  { value: 'medium', label: '🟡 Orta' },
  { value: 'high', label: '🔴 Yüksek' },
]

// ── Main Dashboard Component ───────────────────────────────────────────────

export function Dashboard() {
  const [invoices, setInvoices] = useState<Invoice[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [perPage] = useState(15)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)  // yenileme sırasında listeyi gizleme
  const [uploading, setUploading] = useState(false)
  const [toast, setToast] = useState<{ type: 'success' | 'error'; message: string } | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Filtreler
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [riskFilter, setRiskFilter] = useState<string>('')

  // Özet sayılar
  const [stats, setStats] = useState({
    total: 0,
    pending: 0,
    approved: 0,
    rejected: 0,
  })

  const fetchInvoices = useCallback(async (silent = false) => {
    if (silent) setRefreshing(true)
    else setLoading(true)
    try {
      const { data } = await invoicesApi.list({
        page,
        per_page: perPage,
        status: statusFilter || undefined,
        risk_level: riskFilter || undefined,
        search: search || undefined,
      })
      const d = data.data
      setInvoices(d.items ?? [])
      setTotal(d.total ?? 0)

      // Özet için ilk yüklemede tüm sayımları çek
      if (page === 1 && !statusFilter && !riskFilter && !search) {
        setStats({
          total: d.total ?? 0,
          pending: d.items?.filter((i: Invoice) =>
            ['awaiting_first_approval', 'awaiting_final_approval'].includes(i.status)
          ).length ?? 0,
          approved: d.items?.filter((i: Invoice) => i.status === 'approved').length ?? 0,
          rejected: d.items?.filter((i: Invoice) => i.status === 'rejected').length ?? 0,
        })
      }
    } catch (err) {
      // Liste yükleme hatası sessizce logla — sayfa sıfırlanmasın
      console.error('[Dashboard] Fatura listesi yüklenemedi:', err)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [page, perPage, statusFilter, riskFilter, search])

  useEffect(() => {
    fetchInvoices()
  }, [fetchInvoices])

  const showToast = useCallback((type: 'success' | 'error', message: string) => {
    setToast({ type, message })
    setTimeout(() => setToast(null), 4000)
  }, [])

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      await invoicesApi.upload(file)
      showToast('success', `✅ "${file.name}" yüklendi ve sınıflandırıldı.`)
      // fetchInvoices sessiz modda çalışsın — listeyi silmeden güncelle
      fetchInvoices(true)
    } catch (err: unknown) {
      const axiosError = err as { response?: { data?: { detail?: string } } }
      const detail = axiosError?.response?.data?.detail
      const msg = typeof detail === 'string' ? detail : JSON.stringify(detail ?? 'Bilinmeyen hata')
      showToast('error', `❌ Yükleme hatası: ${msg}`)
      console.error('[Upload] Hata:', err)
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const totalPages = Math.ceil(total / perPage)

  const formatAmount = (amount: number, currency = 'TRY') =>
    new Intl.NumberFormat('tr-TR', { style: 'currency', currency }).format(amount)

  return (
    <div className="p-6 space-y-6">
      {/* Toast Bildirimi */}
      {toast && (
        <div
          className={`fixed top-4 right-4 z-50 px-5 py-3 rounded-xl shadow-lg text-white text-sm font-medium transition-all ${
            toast.type === 'success' ? 'bg-green-600' : 'bg-red-600'
          }`}
        >
          {toast.message}
        </div>
      )}

      {/* Başlık */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-sm text-gray-500 mt-0.5">E-Fatura takip ve yönetim merkezi</p>
        </div>
        <div className="flex items-center gap-3">
          <button onClick={() => fetchInvoices(true)} className="btn-secondary">
            <RefreshCw size={16} className={(loading || refreshing) ? 'animate-spin' : ''} />
            Yenile
          </button>
          <label className={`btn-primary cursor-pointer ${uploading ? 'opacity-70 pointer-events-none' : ''}`}>
            <Upload size={16} className={uploading ? 'animate-bounce' : ''} />
            {uploading ? 'Yükleniyor...' : 'Fatura Yükle'}
            <input
              ref={fileInputRef}
              type="file"
              accept=".xml,.pdf,.xls,.xlsx"
              onChange={handleUpload}
              className="hidden"
              disabled={uploading}
            />
          </label>
        </div>
      </div>

      {/* Özet kartlar */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Toplam Fatura"
          value={stats.total}
          icon={FileText}
          color="bg-blue-500"
        />
        <StatCard
          title="Onay Bekliyor"
          value={stats.pending}
          icon={Clock}
          color="bg-yellow-500"
          sub="1. ve nihai onay"
        />
        <StatCard
          title="Onaylanan"
          value={stats.approved}
          icon={CheckCircle}
          color="bg-green-500"
        />
        <StatCard
          title="Reddedilen"
          value={stats.rejected}
          icon={XCircle}
          color="bg-red-500"
        />
      </div>

      {/* Filtreler */}
      <div className="card">
        <div className="flex flex-wrap gap-3 items-end">
          {/* Arama */}
          <div className="flex-1 min-w-48">
            <label className="block text-xs font-medium text-gray-600 mb-1">Ara</label>
            <div className="relative">
              <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                className="input pl-9 text-sm"
                placeholder="Fatura no, tedarikçi..."
                value={search}
                onChange={(e) => { setSearch(e.target.value); setPage(1) }}
              />
            </div>
          </div>

          {/* Durum filtresi */}
          <div className="w-52">
            <label className="block text-xs font-medium text-gray-600 mb-1">Durum</label>
            <select
              className="input text-sm"
              value={statusFilter}
              onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }}
            >
              {STATUS_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>

          {/* Risk filtresi */}
          <div className="w-40">
            <label className="block text-xs font-medium text-gray-600 mb-1">Risk</label>
            <select
              className="input text-sm"
              value={riskFilter}
              onChange={(e) => { setRiskFilter(e.target.value); setPage(1) }}
            >
              {RISK_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>

          <button
            onClick={() => { setSearch(''); setStatusFilter(''); setRiskFilter(''); setPage(1) }}
            className="btn-secondary text-sm"
          >
            <Filter size={14} />
            Temizle
          </button>
        </div>
      </div>

      {/* Fatura tablosu */}
      <div className="card p-0 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-100">
                <th className="text-left px-4 py-3 font-semibold text-gray-600">Fatura No</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-600">Tedarikçi</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-600">Tarih</th>
                <th className="text-right px-4 py-3 font-semibold text-gray-600">Tutar</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-600">Kategori</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-600">Risk</th>
                <th className="text-left px-4 py-3 font-semibold text-gray-600">Durum</th>
              </tr>
            </thead>
            <tbody className={`divide-y divide-gray-50 ${refreshing ? 'opacity-50' : ''}`}>
              {loading ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-gray-400">
                    <RefreshCw size={20} className="animate-spin mx-auto mb-2" />
                    Yükleniyor...
                  </td>
                </tr>
              ) : invoices.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-gray-400">
                    <TrendingUp size={32} className="mx-auto mb-3 opacity-30" />
                    <p>Fatura bulunamadı</p>
                    <p className="text-xs mt-1">Filtrelerinizi değiştirin veya yeni fatura yükleyin</p>
                  </td>
                </tr>
              ) : (
                invoices.map((inv) => (
                  <tr key={inv.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3 font-mono text-blue-600 font-medium">
                      {inv.invoice_number}
                    </td>
                    <td className="px-4 py-3 text-gray-700">
                      {inv.supplier?.name ?? '-'}
                    </td>
                    <td className="px-4 py-3 text-gray-500">
                      {inv.invoice_date}
                    </td>
                    <td className="px-4 py-3 text-right font-semibold text-gray-900">
                      {formatAmount(inv.total_amount, inv.currency)}
                    </td>
                    <td className="px-4 py-3 text-gray-600 capitalize">
                      {inv.category?.replace(/_/g, ' ') ?? '—'}
                    </td>
                    <td className="px-4 py-3">
                      {inv.risk_level ? <RiskBadge level={inv.risk_level} size="sm" /> : '—'}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={inv.status as InvoiceStatus} />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="px-4 py-3 border-t border-gray-100 flex items-center justify-between text-sm text-gray-600">
            <span>{total} fatura, {totalPages} sayfa</span>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="p-1 rounded hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <ChevronLeft size={18} />
              </button>
              <span className="font-medium">
                {page} / {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="p-1 rounded hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                <ChevronRight size={18} />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
