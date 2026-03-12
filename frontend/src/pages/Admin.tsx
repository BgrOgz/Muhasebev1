/**
 * Admin Sayfası — Kullanıcı Yönetimi, Tedarikçiler, Audit Loglar, Sistem
 */
import { useEffect, useState, useCallback } from 'react'
import {
  Settings,
  Users,
  FileText,
  Activity,
  RefreshCw,
  Plus,
  Pencil,
  Trash2,
  Search,
  Download,
  Truck,
  X,
} from 'lucide-react'
import { adminApi, systemApi } from '../services/api'

// ── Tipler ────────────────────────────────────────────────────────────────

interface AdminUser {
  id: string
  email: string
  name: string
  role: string
  department?: string
  is_active: boolean
  last_login?: string
  created_at: string
}

interface AdminSupplier {
  id: string
  name: string
  vat_number?: string
  city?: string
  contact_email?: string
  invoice_count: number
  total_amount: number
  last_invoice_date?: string
}

interface AuditLogEntry {
  id: string
  action: string
  invoice_id?: string
  user?: { id: string; name: string; email: string }
  old_values?: Record<string, unknown>
  new_values?: Record<string, unknown>
  status: string
  created_at: string
}

// ── Kullanıcı oluşturma/düzenleme modalı ──────────────────────────────────

interface UserModalProps {
  user?: AdminUser | null
  onSave: (data: Record<string, unknown>) => void
  onCancel: () => void
  loading: boolean
}

function UserModal({ user, onSave, onCancel, loading }: UserModalProps) {
  const isEdit = !!user
  const [form, setForm] = useState({
    email: user?.email ?? '',
    name: user?.name ?? '',
    password: '',
    role: user?.role ?? 'viewer',
    department: user?.department ?? '',
    is_active: user?.is_active ?? true,
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const data: Record<string, unknown> = { ...form }
    if (isEdit) {
      delete data.email
      if (!data.password) delete data.password
    }
    onSave(data)
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6">
        <div className="flex items-center justify-between mb-5">
          <h3 className="text-lg font-semibold">{isEdit ? 'Kullanıcı Düzenle' : 'Yeni Kullanıcı'}</h3>
          <button onClick={onCancel} className="text-gray-400 hover:text-gray-600"><X size={20} /></button>
        </div>
        <form onSubmit={handleSubmit} className="space-y-3">
          {!isEdit && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">E-posta</label>
              <input
                type="email" className="input" required
                value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })}
              />
            </div>
          )}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Ad Soyad</label>
            <input
              type="text" className="input" required
              value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </div>
          {!isEdit && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Şifre</label>
              <input
                type="password" className="input" required minLength={8}
                value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })}
              />
            </div>
          )}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Rol</label>
              <select className="input" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
                <option value="viewer">Viewer</option>
                <option value="approver">Approver</option>
                <option value="admin">Admin</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Departman</label>
              <input
                type="text" className="input"
                value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })}
              />
            </div>
          </div>
          {isEdit && (
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={form.is_active} onChange={(e) => setForm({ ...form, is_active: e.target.checked })} />
              Aktif
            </label>
          )}
          <div className="flex gap-3 pt-2">
            <button type="button" onClick={onCancel} className="btn-secondary flex-1 justify-center" disabled={loading}>İptal</button>
            <button type="submit" className="btn-primary flex-1 justify-center" disabled={loading}>
              {loading ? 'Kaydediliyor...' : 'Kaydet'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ── Sekme tanımları ───────────────────────────────────────────────────────

type Tab = 'users' | 'suppliers' | 'audit' | 'system'

const TABS: { key: Tab; label: string; icon: React.ElementType }[] = [
  { key: 'users', label: 'Kullanıcılar', icon: Users },
  { key: 'suppliers', label: 'Tedarikçiler', icon: Truck },
  { key: 'audit', label: 'Denetim Kayıtları', icon: FileText },
  { key: 'system', label: 'Sistem', icon: Activity },
]

// ── Ana bileşen ───────────────────────────────────────────────────────────

export function Admin() {
  const [tab, setTab] = useState<Tab>('users')

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Yönetim Paneli</h1>
        <p className="text-sm text-gray-500 mt-0.5">Kullanıcı, tedarikçi ve sistem yönetimi</p>
      </div>

      {/* Sekmeler */}
      <div className="flex border-b border-gray-200 gap-1">
        {TABS.map((t) => {
          const Icon = t.icon
          return (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium rounded-t-lg transition-colors
                ${tab === t.key ? 'border-b-2 border-blue-600 text-blue-600' : 'text-gray-500 hover:text-gray-700'}`}
            >
              <Icon size={15} />
              {t.label}
            </button>
          )
        })}
      </div>

      {tab === 'users' && <UsersTab />}
      {tab === 'suppliers' && <SuppliersTab />}
      {tab === 'audit' && <AuditTab />}
      {tab === 'system' && <SystemTab />}
    </div>
  )
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
//  KULLANICILAR
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function UsersTab() {
  const [users, setUsers] = useState<AdminUser[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [modal, setModal] = useState<{ user?: AdminUser | null } | null>(null)
  const [saving, setSaving] = useState(false)

  const fetchUsers = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await adminApi.listUsers({ search: search || undefined, per_page: 50 })
      setUsers(data.data.items)
    } finally { setLoading(false) }
  }, [search])

  useEffect(() => { fetchUsers() }, [fetchUsers])

  const handleSave = async (formData: Record<string, unknown>) => {
    setSaving(true)
    try {
      if (modal?.user) {
        await adminApi.updateUser(modal.user.id, formData as Parameters<typeof adminApi.updateUser>[1])
      } else {
        await adminApi.createUser(formData as Parameters<typeof adminApi.createUser>[0])
      }
      setModal(null)
      fetchUsers()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      alert(msg ?? 'Hata oluştu')
    } finally { setSaving(false) }
  }

  const handleDelete = async (user: AdminUser) => {
    if (!confirm(`"${user.name}" kullanıcısını silmek istediğinize emin misiniz?`)) return
    try {
      await adminApi.deleteUser(user.id)
      fetchUsers()
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail
      alert(msg ?? 'Hata oluştu')
    }
  }

  const roleColors: Record<string, string> = {
    admin: 'bg-purple-100 text-purple-800',
    approver: 'bg-blue-100 text-blue-800',
    viewer: 'bg-gray-100 text-gray-600',
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            className="input pl-9 text-sm" placeholder="İsim veya e-posta ara..."
            value={search} onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <button onClick={() => setModal({ user: null })} className="btn-primary text-sm">
          <Plus size={15} /> Yeni Kullanıcı
        </button>
      </div>

      <div className="card p-0 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-100">
              <th className="text-left px-4 py-3 font-semibold text-gray-600">Ad Soyad</th>
              <th className="text-left px-4 py-3 font-semibold text-gray-600">E-posta</th>
              <th className="text-left px-4 py-3 font-semibold text-gray-600">Rol</th>
              <th className="text-left px-4 py-3 font-semibold text-gray-600">Departman</th>
              <th className="text-left px-4 py-3 font-semibold text-gray-600">Durum</th>
              <th className="text-right px-4 py-3 font-semibold text-gray-600">İşlem</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {loading ? (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400"><RefreshCw size={18} className="animate-spin mx-auto" /></td></tr>
            ) : users.length === 0 ? (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400">Kullanıcı bulunamadı</td></tr>
            ) : users.map((u) => (
              <tr key={u.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-medium text-gray-900">{u.name}</td>
                <td className="px-4 py-3 text-gray-500">{u.email}</td>
                <td className="px-4 py-3"><span className={`badge ${roleColors[u.role] ?? 'bg-gray-100 text-gray-600'}`}>{u.role}</span></td>
                <td className="px-4 py-3 text-gray-500">{u.department || '-'}</td>
                <td className="px-4 py-3">
                  <span className={`badge ${u.is_active ? 'badge-low' : 'badge-high'}`}>
                    {u.is_active ? 'Aktif' : 'Pasif'}
                  </span>
                </td>
                <td className="px-4 py-3 text-right">
                  <button onClick={() => setModal({ user: u })} className="p-1.5 text-gray-400 hover:text-blue-600 rounded" title="Düzenle">
                    <Pencil size={15} />
                  </button>
                  <button onClick={() => handleDelete(u)} className="p-1.5 text-gray-400 hover:text-red-600 rounded ml-1" title="Sil">
                    <Trash2 size={15} />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {modal && (
        <UserModal
          user={modal.user}
          onSave={handleSave}
          onCancel={() => setModal(null)}
          loading={saving}
        />
      )}
    </div>
  )
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
//  TEDARİKÇİLER
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function SuppliersTab() {
  const [suppliers, setSuppliers] = useState<AdminSupplier[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')

  const fetchSuppliers = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await adminApi.listSuppliers({ search: search || undefined, per_page: 50 })
      setSuppliers(data.data.items)
    } finally { setLoading(false) }
  }, [search])

  useEffect(() => { fetchSuppliers() }, [fetchSuppliers])

  const formatCurrency = (v: number) =>
    new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY', maximumFractionDigits: 0 }).format(v)

  return (
    <div className="space-y-4">
      <div className="relative max-w-sm">
        <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
        <input
          className="input pl-9 text-sm" placeholder="Tedarikçi adı veya VKN ara..."
          value={search} onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      <div className="card p-0 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-100">
              <th className="text-left px-4 py-3 font-semibold text-gray-600">Tedarikçi</th>
              <th className="text-left px-4 py-3 font-semibold text-gray-600">VKN</th>
              <th className="text-left px-4 py-3 font-semibold text-gray-600">Şehir</th>
              <th className="text-right px-4 py-3 font-semibold text-gray-600">Fatura</th>
              <th className="text-right px-4 py-3 font-semibold text-gray-600">Toplam Tutar</th>
              <th className="text-left px-4 py-3 font-semibold text-gray-600">Son Fatura</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {loading ? (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400"><RefreshCw size={18} className="animate-spin mx-auto" /></td></tr>
            ) : suppliers.length === 0 ? (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400">Tedarikçi bulunamadı</td></tr>
            ) : suppliers.map((s) => (
              <tr key={s.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-medium text-gray-900">{s.name}</td>
                <td className="px-4 py-3 text-gray-500 font-mono text-xs">{s.vat_number || '-'}</td>
                <td className="px-4 py-3 text-gray-500">{s.city || '-'}</td>
                <td className="px-4 py-3 text-right text-gray-700 font-semibold">{s.invoice_count}</td>
                <td className="px-4 py-3 text-right font-semibold text-gray-900">{formatCurrency(s.total_amount)}</td>
                <td className="px-4 py-3 text-gray-400 text-xs">{s.last_invoice_date ?? '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
//  DENETİM KAYITLARI
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function AuditTab() {
  const [logs, setLogs] = useState<AuditLogEntry[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [actionFilter, setActionFilter] = useState('')
  const [exporting, setExporting] = useState(false)

  const fetchLogs = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await adminApi.listAuditLogs({
        action: actionFilter || undefined,
        page,
        per_page: 30,
      })
      setLogs(data.data.items)
      setTotal(data.data.total)
    } finally { setLoading(false) }
  }, [actionFilter, page])

  useEffect(() => { fetchLogs() }, [fetchLogs])

  const handleExport = async () => {
    setExporting(true)
    try {
      const { data } = await adminApi.exportAuditLogs()
      const url = window.URL.createObjectURL(new Blob([data]))
      const a = document.createElement('a')
      a.href = url
      a.download = `audit-logs-${new Date().toISOString().slice(0, 10)}.csv`
      a.click()
      window.URL.revokeObjectURL(url)
    } finally { setExporting(false) }
  }

  const totalPages = Math.ceil(total / 30)

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            className="input pl-9 text-sm" placeholder="Eylem filtresi (ör: invoice.first_approved)"
            value={actionFilter} onChange={(e) => { setActionFilter(e.target.value); setPage(1) }}
          />
        </div>
        <button onClick={handleExport} disabled={exporting} className="btn-primary text-sm">
          <Download size={15} /> {exporting ? 'İndiriliyor...' : 'CSV İndir'}
        </button>
      </div>

      <div className="card p-0 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-100">
              <th className="text-left px-4 py-3 font-semibold text-gray-600">Tarih</th>
              <th className="text-left px-4 py-3 font-semibold text-gray-600">Kullanıcı</th>
              <th className="text-left px-4 py-3 font-semibold text-gray-600">Eylem</th>
              <th className="text-left px-4 py-3 font-semibold text-gray-600">Durum</th>
              <th className="text-left px-4 py-3 font-semibold text-gray-600">Detay</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50">
            {loading ? (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-400"><RefreshCw size={18} className="animate-spin mx-auto" /></td></tr>
            ) : logs.length === 0 ? (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-gray-400">Denetim kaydı bulunamadı</td></tr>
            ) : logs.map((log) => (
              <tr key={log.id} className="hover:bg-gray-50">
                <td className="px-4 py-3 text-gray-400 text-xs whitespace-nowrap">
                  {new Date(log.created_at).toLocaleString('tr-TR')}
                </td>
                <td className="px-4 py-3 text-gray-700">
                  {log.user?.name ?? '-'}
                  {log.user?.email && <span className="text-xs text-gray-400 block">{log.user.email}</span>}
                </td>
                <td className="px-4 py-3 font-mono text-xs text-blue-700">{log.action}</td>
                <td className="px-4 py-3">
                  <span className={`badge ${log.status === 'success' ? 'badge-low' : 'badge-high'}`}>
                    {log.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-xs text-gray-500 max-w-[200px] truncate">
                  {log.new_values ? JSON.stringify(log.new_values).slice(0, 80) : '-'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2 text-sm">
          <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} className="btn-secondary text-sm">Önceki</button>
          <span className="text-gray-500">{page} / {totalPages}</span>
          <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages} className="btn-secondary text-sm">Sonraki</button>
        </div>
      )}
    </div>
  )
}

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
//  SİSTEM
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

function SystemTab() {
  const [schedulerStatus, setSchedulerStatus] = useState<{ scheduler: string; jobs: { id: string; name: string; next_run: string | null }[] } | null>(null)
  const [emailLogs, setEmailLogs] = useState<{ id: string; from_email: string; filename: string; status: string; error?: string; created_at: string }[]>([])
  const [loading, setLoading] = useState(true)
  const [polling, setPolling] = useState(false)

  const fetchSystemData = async () => {
    setLoading(true)
    try {
      const [statusRes, logsRes] = await Promise.all([
        systemApi.schedulerStatus(),
        systemApi.emailLogs(20),
      ])
      setSchedulerStatus(statusRes.data.data)
      setEmailLogs(logsRes.data.data)
    } finally { setLoading(false) }
  }

  useEffect(() => { fetchSystemData() }, [])

  const handlePollNow = async () => {
    setPolling(true)
    try { await systemApi.pollNow(); alert('Email taraması başlatıldı.') }
    catch { alert('Hata oluştu.') }
    finally { setPolling(false) }
  }

  return (
    <div className="space-y-6">
      {/* Scheduler durumu */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <Activity size={20} className="text-blue-500" />
            <h3 className="font-semibold text-gray-800">Scheduler Durumu</h3>
          </div>
          <div className="flex gap-2">
            <button onClick={fetchSystemData} className="btn-secondary text-sm">
              <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Yenile
            </button>
            <button onClick={handlePollNow} disabled={polling} className="btn-primary text-sm">
              {polling ? 'Başlatılıyor...' : 'Hemen Tara'}
            </button>
          </div>
        </div>

        {loading ? (
          <p className="text-gray-400 text-sm">Yükleniyor...</p>
        ) : (
          <>
            <div className="flex items-center gap-2 mb-4">
              <span className={`w-2.5 h-2.5 rounded-full ${schedulerStatus?.scheduler === 'running' ? 'bg-green-500' : 'bg-red-500'}`} />
              <span className="text-sm font-medium">{schedulerStatus?.scheduler === 'running' ? 'Çalışıyor' : 'Durdu'}</span>
            </div>
            {schedulerStatus?.jobs?.map((job) => (
              <div key={job.id} className="flex items-center justify-between text-sm bg-gray-50 rounded-lg px-3 py-2 mb-2">
                <span className="font-medium text-gray-700">{job.name}</span>
                <span className="text-gray-400 text-xs">
                  {job.next_run ? `Sonraki: ${new Date(job.next_run).toLocaleString('tr-TR')}` : 'Planlanmamış'}
                </span>
              </div>
            ))}
          </>
        )}
      </div>

      {/* Email logları */}
      <div className="card">
        <h3 className="font-semibold text-gray-800 mb-4">Son Email İşlemleri</h3>
        {emailLogs.length === 0 ? (
          <p className="text-gray-400 text-sm text-center py-4">Log kaydı yok</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="text-left py-2 font-semibold text-gray-600">Gönderen</th>
                  <th className="text-left py-2 font-semibold text-gray-600">Dosya</th>
                  <th className="text-left py-2 font-semibold text-gray-600">Durum</th>
                  <th className="text-left py-2 font-semibold text-gray-600">Tarih</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {emailLogs.map((log) => (
                  <tr key={log.id} className="hover:bg-gray-50">
                    <td className="py-2 text-gray-600 truncate max-w-[160px]">{log.from_email}</td>
                    <td className="py-2 text-gray-600 truncate max-w-[160px]">{log.filename}</td>
                    <td className="py-2">
                      <span className={`badge ${log.status === 'success' ? 'badge-low' : 'badge-high'}`}>
                        {log.status === 'success' ? 'Başarılı' : 'Hata'}
                      </span>
                    </td>
                    <td className="py-2 text-gray-400 text-xs whitespace-nowrap">
                      {new Date(log.created_at).toLocaleString('tr-TR')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
