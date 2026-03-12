/**
 * Uygulama genelinde kullanılan formatter fonksiyonları
 */

export function formatCurrency(
  amount: number | string,
  currency: string = 'TRY',
  decimals: number = 2
): string {
  const num = typeof amount === 'string' ? parseFloat(amount) : amount
  if (isNaN(num)) return '0,00 ' + currency

  const formatted = num.toFixed(decimals).replace('.', ',')
  const parts = formatted.split(',')
  parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, '.')

  return parts.join(',') + ' ' + currency
}

export function formatNumber(value: number | string, decimals: number = 2): string {
  const num = typeof value === 'string' ? parseFloat(value) : value
  if (isNaN(num)) return '0'

  return num.toFixed(decimals).replace('.', ',')
}

export function formatDate(date: Date | string): string {
  const d = typeof date === 'string' ? new Date(date) : date
  if (isNaN(d.getTime())) return '-'

  return d.toLocaleDateString('tr-TR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
}

export function formatDateTime(date: Date | string): string {
  const d = typeof date === 'string' ? new Date(date) : date
  if (isNaN(d.getTime())) return '-'

  return d.toLocaleDateString('tr-TR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatPercent(value: number | string): string {
  const num = typeof value === 'string' ? parseFloat(value) : value
  if (isNaN(num)) return '0%'

  return (num * 100).toFixed(0) + '%'
}

export function truncateText(text: string, maxLength: number = 50): string {
  if (text.length <= maxLength) return text
  return text.substring(0, maxLength - 3) + '...'
}

export function getStatusColor(status: string): string {
  const colors: Record<string, string> = {
    awaiting_first_approval: 'text-yellow-600 bg-yellow-50',
    awaiting_final_approval: 'text-orange-600 bg-orange-50',
    approved: 'text-green-600 bg-green-50',
    rejected: 'text-red-600 bg-red-50',
    processing: 'text-blue-600 bg-blue-50',
    returned: 'text-purple-600 bg-purple-50',
    draft: 'text-gray-600 bg-gray-50',
  }
  return colors[status] || 'text-gray-600 bg-gray-50'
}

export function getRiskColor(risk: string): string {
  const colors: Record<string, string> = {
    low: 'text-green-600 bg-green-50',
    medium: 'text-yellow-600 bg-yellow-50',
    high: 'text-red-600 bg-red-50',
  }
  return colors[risk] || 'text-gray-600 bg-gray-50'
}

export function getCategoryLabel(category: string): string {
  const labels: Record<string, string> = {
    kumas: '🧵 Kumaş',
    iplik: '🧶 İplik',
    aksesuar: '🔘 Aksesuar',
    boya_kimyasal: '🧪 Boya & Kimyasal',
    makine_ekipman: '⚙️ Makine & Ekipman',
    enerji: '⚡ Enerji',
    lojistik: '📦 Lojistik',
    hizmet: '🛠️ Hizmet',
    ofis: '🖇️ Ofis',
    diger: '📋 Diğer',
  }
  return labels[category] || category
}
