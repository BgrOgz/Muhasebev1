import { AlertCircle, Check, X } from 'lucide-react'

export interface ConfirmDialogProps {
  isOpen: boolean
  title: string
  message: string
  danger?: boolean
  confirmText?: string
  cancelText?: string
  isLoading?: boolean
  onConfirm: () => void | Promise<void>
  onCancel: () => void
}

export function ConfirmDialog({
  isOpen,
  title,
  message,
  danger = false,
  confirmText = 'Onayla',
  cancelText = 'İptal',
  isLoading = false,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  if (!isOpen) return null

  const buttonColor = danger ? 'bg-red-600 hover:bg-red-700' : 'bg-blue-600 hover:bg-blue-700'
  const iconColor = danger ? 'text-red-600' : 'text-blue-600'

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="card max-w-md w-full mx-4">
        <div className="flex items-start gap-4 mb-4">
          <AlertCircle className={`w-6 h-6 flex-shrink-0 ${iconColor}`} />
          <div>
            <h3 className="text-lg font-bold text-gray-900">{title}</h3>
            <p className="text-gray-600 mt-2">{message}</p>
          </div>
        </div>

        <div className="flex gap-3 mt-6 pt-4 border-t border-gray-200">
          <button
            onClick={onCancel}
            disabled={isLoading}
            className="flex-1 btn btn-secondary flex items-center justify-center gap-2"
          >
            <X size={18} />
            {cancelText}
          </button>
          <button
            onClick={onConfirm}
            disabled={isLoading}
            className={`flex-1 ${buttonColor} text-white px-4 py-2 rounded-lg font-medium flex items-center justify-center gap-2 disabled:opacity-50`}
          >
            <Check size={18} />
            {confirmText}
          </button>
        </div>
      </div>
    </div>
  )
}
