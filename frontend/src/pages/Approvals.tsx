import { useEffect, useState, useCallback } from 'react'
import {
  CheckCircle,
  XCircle,
  Clock,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  MessageSquare,
} from 'lucide-react'
import { approvalsApi } from '../services/api'
import { Approval } from '../types'
import { RiskBadge } from '../components/RiskBadge'

// ── Onay eylemi modalı ────────────────────────────────────────────────────

interface ActionModalProps {
  approval: Approval
  action: 'approved' | 'rejected'
  onConfirm: (data: { comments?: string; reason_rejected?: string }) => void
  onCancel: () => void
  loading: boolean
}

function ActionModal({ approval, action, onConfirm, onCancel, loading }: ActionModalProps) {
  const [comments, setComments] = useState('')
  const [reason, setReason] = useState('')
  const isApprove = action === 'approved'

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6">
        <div className={`w-12 h-12 rounded-full flex items-center justify-center mx-auto mb-4
          ${isApprove ? 'bg-green-100' : 'bg-red-100'}`}>
          {isApprove
            ? <CheckCircle size={24} className="text-green-600" />
            : <XCircle size={24} className="text-red-600" />
          }
        </div>

        <h3 className="text-lg font-semibold text-center text-gray-900 mb-1">
          {isApprove ? 'Faturayı Onayla' : 'Faturayı Reddet'}
        </h3>
        <p className="text-sm text-center text-gray-500 mb-6">
          <strong>{approval.invoice.invoice_number}</strong> numaralı fatura /{' '}
          <strong>{approval.invoice.supplier}</strong>
        </p>

        {isApprove ? (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Not (opsiyonel)
            </label>
            <textarea
              className="input resize-none h-24"
              placeholder="Onay notu..."
              value={comments}
              onChange={(e) => setComments(e.target.value)}
            />
          </div>
        ) : (
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Red sebebi <span className="text-red-500">*</span>
            </label>
            <textarea
              className={`input resize-none h-24 ${!reason.trim() ? 'border-red-300 focus:ring-red-400' : ''}`}
              placeholder="Neden reddediyorsunuz?"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              required
            />
            {!reason.trim() && (
              <p className="text-xs text-red-500 mt-1">Red sebebi yazmadan reddedemezsiniz.</p>
            )}
          </div>
        )}

        <div className="flex gap-3 mt-6">
          <button onClick={onCancel} className="btn-secondary flex-1 justify-center" disabled={loading}>
            İptal
          </button>
          <button
            onClick={() => onConfirm({ comments, reason_rejected: reason })}
            disabled={loading || (!isApprove && !reason.trim())}
            className={`flex-1 justify-center ${
              isApprove ? 'btn-success' : 'btn-danger'
            } ${(!isApprove && !reason.trim()) ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            {loading ? 'İşleniyor...' : isApprove ? 'Onayla' : 'Reddet'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Onay kartı ────────────────────────────────────────────────────────────

interface ApprovalCardProps {
  approval: Approval
  onAction: (approval: Approval, action: 'approved' | 'rejected') => void
}

function ApprovalCard({ approval, onAction }: ApprovalCardProps) {
  const [expanded, setExpanded] = useState(false)
  const inv = approval.invoice

  const formatAmount = (amount: number) =>
    new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY' }).format(amount)

  const levelLabel = approval.approval_level === 'first' ? '1. Onay' : 'Nihai Onay'
  const levelColor = approval.approval_level === 'first'
    ? 'bg-yellow-100 text-yellow-800'
    : 'bg-purple-100 text-purple-800'

  return (
    <div className="card p-0 overflow-hidden">
      {/* Üst kısım */}
      <div className="p-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap mb-2">
              <span className={`badge ${levelColor}`}>{levelLabel}</span>
              {inv.risk_level && <RiskBadge level={inv.risk_level} size="sm" />}
            </div>
            <p className="font-mono font-semibold text-blue-700">{inv.invoice_number}</p>
            <p className="text-gray-600 text-sm mt-0.5">{inv.supplier}</p>
          </div>
          <div className="text-right flex-shrink-0">
            <p className="font-bold text-lg text-gray-900">{formatAmount(inv.amount)}</p>
            <p className="text-xs text-gray-400 capitalize">
              {inv.category?.replace(/_/g, ' ') ?? '-'}
            </p>
          </div>
        </div>

        {/* Aksiyon butonları */}
        {approval.status === 'pending' && (
          <div className="flex gap-2 mt-4">
            <button
              onClick={() => onAction(approval, 'approved')}
              className="btn-success flex-1 justify-center text-sm py-2"
            >
              <CheckCircle size={15} />
              Onayla
            </button>
            <button
              onClick={() => onAction(approval, 'rejected')}
              className="btn-danger flex-1 justify-center text-sm py-2"
            >
              <XCircle size={15} />
              Reddet
            </button>
            <button
              onClick={() => setExpanded((v) => !v)}
              className="btn-secondary px-3 text-sm"
              title="Detay"
            >
              {expanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
            </button>
          </div>
        )}
      </div>

      {/* Detay */}
      {expanded && (
        <div className="border-t border-gray-100 px-4 py-3 bg-gray-50 text-sm space-y-1">
          <p className="text-gray-500">
            <span className="font-medium text-gray-700">Oluşturma:</span>{' '}
            {new Date(approval.created_at).toLocaleString('tr-TR')}
          </p>
          {approval.comments && (
            <div className="flex gap-2 text-gray-600">
              <MessageSquare size={14} className="flex-shrink-0 mt-0.5" />
              <p>{approval.comments}</p>
            </div>
          )}
        </div>
      )}

      {/* Tamamlandı göstergesi */}
      {approval.status !== 'pending' && (
        <div className={`px-4 py-2 text-sm font-medium flex items-center gap-2
          ${approval.status === 'approved'
            ? 'bg-green-50 text-green-700'
            : 'bg-red-50 text-red-700'
          }`}>
          {approval.status === 'approved'
            ? <><CheckCircle size={14} /> Onaylandı</>
            : <><XCircle size={14} /> Reddedildi</>
          }
          {approval.approved_at && (
            <span className="ml-auto text-xs opacity-70">
              {new Date(approval.approved_at).toLocaleString('tr-TR')}
            </span>
          )}
        </div>
      )}
    </div>
  )
}

// ── Ana sayfa ─────────────────────────────────────────────────────────────

export function Approvals() {
  const [pending, setPending] = useState<Approval[]>([])
  const [completed, setCompleted] = useState<Approval[]>([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'pending' | 'completed'>('pending')
  const [modal, setModal] = useState<{
    approval: Approval
    action: 'approved' | 'rejected'
  } | null>(null)
  const [actionLoading, setActionLoading] = useState(false)

  const fetchApprovals = useCallback(async () => {
    setLoading(true)
    try {
      const [pendingRes, completedRes] = await Promise.all([
        approvalsApi.list({ status: 'pending' }),
        approvalsApi.list({ status: 'approved', per_page: 30 }),
      ])
      setPending(pendingRes.data.data.items ?? [])
      setCompleted(completedRes.data.data.items ?? [])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchApprovals()
  }, [fetchApprovals])

  const handleAction = (approval: Approval, action: 'approved' | 'rejected') => {
    setModal({ approval, action })
  }

  const handleConfirm = async (formData: { comments?: string; reason_rejected?: string }) => {
    if (!modal) return
    setActionLoading(true)
    try {
      await approvalsApi.action(modal.approval.id, {
        status: modal.action,
        ...formData,
      })
      setModal(null)
      fetchApprovals()
    } catch (err: unknown) {
      const axiosError = err as { response?: { data?: { detail?: string } } }
      alert('Hata: ' + (axiosError?.response?.data?.detail ?? 'Bilinmeyen hata'))
    } finally {
      setActionLoading(false)
    }
  }

  const displayItems = activeTab === 'pending' ? pending : completed

  return (
    <div className="p-6 space-y-6">
      {/* Başlık */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Onay Paneli</h1>
          <p className="text-sm text-gray-500 mt-0.5">Bekleyen ve tamamlanan onaylarınız</p>
        </div>
        <button onClick={fetchApprovals} className="btn-secondary">
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          Yenile
        </button>
      </div>

      {/* Özet */}
      <div className="grid grid-cols-3 gap-4">
        <div className="card text-center py-4">
          <Clock size={22} className="text-yellow-500 mx-auto mb-2" />
          <p className="text-2xl font-bold">{pending.length}</p>
          <p className="text-sm text-gray-500">Bekleyen</p>
        </div>
        <div className="card text-center py-4">
          <CheckCircle size={22} className="text-green-500 mx-auto mb-2" />
          <p className="text-2xl font-bold">{completed.filter(a => a.status === 'approved').length}</p>
          <p className="text-sm text-gray-500">Onaylanan</p>
        </div>
        <div className="card text-center py-4">
          <XCircle size={22} className="text-red-500 mx-auto mb-2" />
          <p className="text-2xl font-bold">{completed.filter(a => a.status === 'rejected').length}</p>
          <p className="text-sm text-gray-500">Reddedilen</p>
        </div>
      </div>

      {/* Sekmeler */}
      <div className="flex border-b border-gray-200 gap-1">
        {(['pending', 'completed'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2.5 text-sm font-medium rounded-t-lg transition-colors
              ${activeTab === tab
                ? 'border-b-2 border-blue-600 text-blue-600'
                : 'text-gray-500 hover:text-gray-700'
              }`}
          >
            {tab === 'pending' ? `Bekleyen (${pending.length})` : `Tamamlanan (${completed.length})`}
          </button>
        ))}
      </div>

      {/* Liste */}
      {loading ? (
        <div className="text-center py-12 text-gray-400">
          <RefreshCw size={24} className="animate-spin mx-auto mb-3" />
          Yükleniyor...
        </div>
      ) : displayItems.length === 0 ? (
        <div className="card text-center py-12 text-gray-400">
          <CheckCircle size={40} className="mx-auto mb-3 opacity-20" />
          <p className="font-medium">
            {activeTab === 'pending' ? 'Bekleyen onay yok' : 'Tamamlanan onay yok'}
          </p>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {displayItems.map((approval) => (
            <ApprovalCard
              key={approval.id}
              approval={approval}
              onAction={handleAction}
            />
          ))}
        </div>
      )}

      {/* Modal */}
      {modal && (
        <ActionModal
          approval={modal.approval}
          action={modal.action}
          onConfirm={handleConfirm}
          onCancel={() => setModal(null)}
          loading={actionLoading}
        />
      )}
    </div>
  )
}
