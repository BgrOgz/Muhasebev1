import { InvoiceStatus } from '../types'

const STATUS_MAP: Record<InvoiceStatus, { label: string; classes: string }> = {
  draft: { label: 'Taslak', classes: 'bg-gray-100 text-gray-700' },
  processing: { label: 'İşleniyor', classes: 'bg-blue-100 text-blue-700' },
  awaiting_first_approval: { label: '1. Onay Bekliyor', classes: 'bg-yellow-100 text-yellow-800' },
  returned: { label: 'İade Edildi', classes: 'bg-orange-100 text-orange-800' },
  awaiting_final_approval: { label: 'Patron Onayı', classes: 'bg-purple-100 text-purple-800' },
  approved: { label: 'Onaylandı', classes: 'bg-green-100 text-green-800' },
  rejected: { label: 'Reddedildi', classes: 'bg-red-100 text-red-800' },
  archived: { label: 'Arşivlendi', classes: 'bg-gray-100 text-gray-500' },
}

interface Props {
  status: InvoiceStatus
}

export function StatusBadge({ status }: Props) {
  const config = STATUS_MAP[status] ?? { label: status, classes: 'bg-gray-100 text-gray-700' }
  return (
    <span className={`badge ${config.classes}`}>
      {config.label}
    </span>
  )
}
