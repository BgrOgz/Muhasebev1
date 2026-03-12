import { X, Calendar, AlertCircle, CheckCircle, Clock, FileText } from 'lucide-react'
import { Invoice } from '../types'
import { formatCurrency, formatDate, getCategoryLabel, getRiskColor } from '../utils/formatters'
import { RiskBadge } from './RiskBadge'
import { StatusBadge } from './StatusBadge'

interface InvoiceDetailModalProps {
  invoice: Invoice | null
  isOpen: boolean
  onClose: () => void
}

export function InvoiceDetailModal({ invoice, isOpen, onClose }: InvoiceDetailModalProps) {
  if (!isOpen || !invoice) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <h2 className="text-xl font-bold text-gray-900">
            Fatura Detayı: {invoice.invoice_number}
          </h2>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700 transition-colors"
          >
            <X size={24} />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Fatura Bilgileri */}
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Fatura Bilgileri</h3>
            <div className="grid grid-cols-2 gap-4 bg-gray-50 p-4 rounded-lg">
              <div>
                <p className="text-sm text-gray-600">Fatura No</p>
                <p className="font-medium text-gray-900">{invoice.invoice_number}</p>
              </div>
              <div>
                <p className="text-sm text-gray-600">Tedarikçi</p>
                <p className="font-medium text-gray-900">
                  {invoice.supplier?.name || 'Bilinmiyor'}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-600">Fatura Tarihi</p>
                <p className="font-medium text-gray-900 flex items-center gap-2">
                  <Calendar size={16} className="text-gray-500" />
                  {formatDate(invoice.invoice_date)}
                </p>
              </div>
              <div>
                <p className="text-sm text-gray-600">Vade Tarihi</p>
                <p className="font-medium text-gray-900">
                  {invoice.due_date ? formatDate(invoice.due_date) : '-'}
                </p>
              </div>
            </div>
          </div>

          {/* Tutarlar */}
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Tutarlar</h3>
            <div className="space-y-3 bg-blue-50 p-4 rounded-lg border border-blue-200">
              <div className="flex justify-between items-center">
                <span className="text-gray-600">KDV Hariç:</span>
                <span className="font-semibold text-gray-900">
                  {formatCurrency(invoice.amount, invoice.currency)}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-600">KDV:</span>
                <span className="font-semibold text-gray-900">
                  {formatCurrency(invoice.tax_amount, invoice.currency)}
                </span>
              </div>
              <div className="flex justify-between items-center pt-3 border-t border-blue-200">
                <span className="text-gray-900 font-semibold">Genel Toplam:</span>
                <span className="font-bold text-lg text-blue-600">
                  {formatCurrency(invoice.total_amount, invoice.currency)}
                </span>
              </div>
            </div>
          </div>

          {/* Sınıflandırma */}
          {invoice.classification && (
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-4">AI Sınıflandırması</h3>
              <div className="bg-purple-50 p-4 rounded-lg border border-purple-200 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-gray-600">Kategori:</span>
                  <span className="font-medium">
                    {getCategoryLabel(invoice.classification.category)}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-600">Risk Seviyesi:</span>
                  <RiskBadge level={invoice.classification.risk_level} />
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-gray-600">Güven Skoru:</span>
                  <span className="font-medium">
                    {(invoice.classification.confidence_score * 100).toFixed(0)}%
                  </span>
                </div>
                {invoice.classification.ai_notes && (
                  <div className="pt-3 border-t border-purple-200">
                    <p className="text-sm text-gray-600 mb-2">AI Notu:</p>
                    <p className="text-sm text-gray-700">{invoice.classification.ai_notes}</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Durum */}
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Durum</h3>
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-gray-600">Fatura Durumu:</span>
                <StatusBadge status={invoice.status} />
              </div>
            </div>
          </div>

          {/* Timeline */}
          <div>
            <h3 className="text-lg font-semibold text-gray-900 mb-4">İşlem Geçmişi</h3>
            <div className="space-y-3">
              <div className="flex gap-4 pb-4 border-l-2 border-gray-200">
                <div className="flex-shrink-0">
                  <div className="w-3 h-3 bg-blue-600 rounded-full -ml-2 mt-1.5"></div>
                </div>
                <div>
                  <p className="font-medium text-gray-900">Fatura Yüklendi</p>
                  <p className="text-sm text-gray-500">
                    {formatDate(invoice.created_at || new Date())}
                  </p>
                </div>
              </div>

              {invoice.classification && (
                <div className="flex gap-4 pb-4 border-l-2 border-green-200">
                  <div className="flex-shrink-0">
                    <div className="w-3 h-3 bg-green-600 rounded-full -ml-2 mt-1.5"></div>
                  </div>
                  <div>
                    <p className="font-medium text-gray-900">AI Sınıflandırması Tamamlandı</p>
                    <p className="text-sm text-gray-500">
                      {formatDate(invoice.classification.created_at || new Date())}
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex gap-3 p-6 border-t border-gray-200">
          <button
            onClick={onClose}
            className="flex-1 btn btn-secondary"
          >
            Kapat
          </button>
          <button className="flex-1 btn btn-primary">
            <FileText size={18} />
            Dosya İndir
          </button>
        </div>
      </div>
    </div>
  )
}
