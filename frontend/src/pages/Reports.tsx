import { useEffect, useState, useCallback } from 'react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Legend,
} from 'recharts'
import { Download, RefreshCw, TrendingUp, DollarSign, FileCheck, AlertTriangle } from 'lucide-react'
import { reportsApi } from '../services/api'
import { ReportSummary } from '../types'

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#f97316', '#ec4899']

const CATEGORY_LABELS: Record<string, string> = {
  kumas: 'Kumaş',
  iplik: 'İplik',
  aksesuar: 'Aksesuar',
  boya_kimyasal: 'Boya/Kimyasal',
  makine_ekipman: 'Makine/Ekipman',
  enerji: 'Enerji',
  lojistik: 'Lojistik',
  hizmet: 'Hizmet',
  ofis: 'Ofis',
  diger: 'Diğer',
}

function StatCard({
  title,
  value,
  icon: Icon,
  color,
}: {
  title: string
  value: string
  icon: React.ElementType
  color: string
}) {
  return (
    <div className="card flex items-center gap-4">
      <div className={`w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0 ${color}`}>
        <Icon size={20} className="text-white" />
      </div>
      <div>
        <p className="text-xs text-gray-500">{title}</p>
        <p className="text-xl font-bold text-gray-900">{value}</p>
      </div>
    </div>
  )
}

export function Reports() {
  const [summary, setSummary] = useState<ReportSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [exporting, setExporting] = useState(false)
  const [dateRange, setDateRange] = useState({
    start: '',
    end: '',
  })

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      const params = {
        start_date: dateRange.start || undefined,
        end_date: dateRange.end || undefined,
      }
      const { data } = await reportsApi.summary(params)
      setSummary(data.data)
    } finally {
      setLoading(false)
    }
  }, [dateRange])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const handleExport = async () => {
    setExporting(true)
    try {
      const { data } = await reportsApi.exportCsv()
      const url = window.URL.createObjectURL(new Blob([data]))
      const a = document.createElement('a')
      a.href = url
      a.download = `fatura-raporu-${new Date().toISOString().slice(0, 10)}.csv`
      a.click()
      window.URL.revokeObjectURL(url)
    } finally {
      setExporting(false)
    }
  }

  const formatCurrency = (v: number) =>
    new Intl.NumberFormat('tr-TR', { style: 'currency', currency: 'TRY', maximumFractionDigits: 0 }).format(v)

  if (loading) {
    return (
      <div className="p-6 flex items-center justify-center h-64">
        <RefreshCw size={24} className="animate-spin text-blue-500" />
      </div>
    )
  }

  // Grafik verileri
  const categoryChartData = (summary?.by_category ?? []).map((c) => ({
    name: CATEGORY_LABELS[c.category] ?? c.category,
    count: c.count,
    amount: c.total_amount,
  }))

  const riskChartData = (summary?.by_risk ?? []).map((r) => ({
    name: r.level === 'low' ? 'Düşük' : r.level === 'medium' ? 'Orta' : 'Yüksek',
    value: r.count,
  }))

  const riskColors: Record<string, string> = {
    Düşük: '#10b981',
    Orta: '#f59e0b',
    Yüksek: '#ef4444',
  }

  return (
    <div className="p-6 space-y-6">
      {/* Başlık */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Raporlar</h1>
          <p className="text-sm text-gray-500 mt-0.5">Fatura istatistikleri ve özet</p>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          {/* Tarih filtresi */}
          <div className="flex items-center gap-2 text-sm">
            <input
              type="date"
              className="input text-sm py-1.5"
              value={dateRange.start}
              onChange={(e) => setDateRange((d) => ({ ...d, start: e.target.value }))}
            />
            <span className="text-gray-400">—</span>
            <input
              type="date"
              className="input text-sm py-1.5"
              value={dateRange.end}
              onChange={(e) => setDateRange((d) => ({ ...d, end: e.target.value }))}
            />
          </div>
          <button onClick={fetchData} className="btn-secondary text-sm">
            <RefreshCw size={14} />
            Yenile
          </button>
          <button onClick={handleExport} disabled={exporting} className="btn-primary text-sm">
            <Download size={14} />
            {exporting ? 'İndiriliyor...' : 'CSV İndir'}
          </button>
        </div>
      </div>

      {/* Özet kartlar */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Toplam Fatura"
          value={String(summary?.total_invoices ?? 0)}
          icon={TrendingUp}
          color="bg-blue-500"
        />
        <StatCard
          title="Toplam Tutar"
          value={formatCurrency(summary?.total_amount ?? 0)}
          icon={DollarSign}
          color="bg-green-500"
        />
        <StatCard
          title="Onaylanan"
          value={String(summary?.approved_count ?? 0)}
          icon={FileCheck}
          color="bg-emerald-500"
        />
        <StatCard
          title="Bekleyen"
          value={String(summary?.pending_count ?? 0)}
          icon={AlertTriangle}
          color="bg-yellow-500"
        />
      </div>

      {/* Grafikler */}
      <div className="grid lg:grid-cols-3 gap-6">

        {/* Kategori dağılımı (bar chart) */}
        <div className="card lg:col-span-2">
          <h3 className="font-semibold text-gray-800 mb-4">Kategori Bazlı Fatura Sayısı</h3>
          {categoryChartData.length === 0 ? (
            <div className="h-48 flex items-center justify-center text-gray-400 text-sm">
              Veri yok
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={categoryChartData} margin={{ top: 0, right: 0, left: -10, bottom: 0 }}>
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip
                  formatter={(value, name) =>
                    name === 'count' ? [value, 'Adet'] : [formatCurrency(Number(value)), 'Tutar']
                  }
                />
                <Bar dataKey="count" fill="#3b82f6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Risk dağılımı (pie chart) */}
        <div className="card">
          <h3 className="font-semibold text-gray-800 mb-4">Risk Dağılımı</h3>
          {riskChartData.length === 0 ? (
            <div className="h-48 flex items-center justify-center text-gray-400 text-sm">
              Veri yok
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie
                  data={riskChartData}
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={80}
                  dataKey="value"
                  label={({ name, value }) => `${name}: ${value}`}
                  labelLine={false}
                >
                  {riskChartData.map((entry, index) => (
                    <Cell key={index} fill={riskColors[entry.name] ?? COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Legend />
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Top tedarikçiler */}
      <div className="card">
        <h3 className="font-semibold text-gray-800 mb-4">Tedarikçi Bazlı Özet</h3>
        {(summary?.by_supplier ?? []).length === 0 ? (
          <p className="text-gray-400 text-sm text-center py-4">Veri yok</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100">
                  <th className="text-left py-2 font-semibold text-gray-600">Tedarikçi</th>
                  <th className="text-right py-2 font-semibold text-gray-600">Fatura Sayısı</th>
                  <th className="text-right py-2 font-semibold text-gray-600">Toplam Tutar</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {summary?.by_supplier.slice(0, 10).map((s, i) => (
                  <tr key={i} className="hover:bg-gray-50">
                    <td className="py-2.5 text-gray-700">{s.supplier_name}</td>
                    <td className="py-2.5 text-right text-gray-500">{s.invoice_count}</td>
                    <td className="py-2.5 text-right font-semibold text-gray-900">
                      {formatCurrency(s.total_amount)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Ortalama güven */}
      {summary && summary.avg_confidence > 0 && (
        <div className="card">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-medium text-gray-700">AI Ortalama Güven Skoru</p>
            <p className="text-lg font-bold text-blue-600">
              {(summary.avg_confidence * 100).toFixed(0)}%
            </p>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-blue-500 h-2 rounded-full transition-all"
              style={{ width: `${summary.avg_confidence * 100}%` }}
            />
          </div>
        </div>
      )}
    </div>
  )
}
