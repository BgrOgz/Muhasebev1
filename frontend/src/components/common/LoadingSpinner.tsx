import { Loader2 } from 'lucide-react'

export interface LoadingSpinnerProps {
  message?: string
  size?: 'sm' | 'md' | 'lg'
  fullScreen?: boolean
}

export function LoadingSpinner({
  message = 'Yükleniyor...',
  size = 'md',
  fullScreen = false,
}: LoadingSpinnerProps) {
  const sizeClasses = {
    sm: 'w-6 h-6',
    md: 'w-10 h-10',
    lg: 'w-16 h-16',
  }

  const container = fullScreen
    ? 'fixed inset-0 flex items-center justify-center bg-black bg-opacity-50'
    : 'flex items-center justify-center'

  return (
    <div className={container}>
      <div className="flex flex-col items-center gap-4">
        <Loader2 className={`${sizeClasses[size]} animate-spin text-blue-600`} />
        {message && <p className="text-gray-600 font-medium">{message}</p>}
      </div>
    </div>
  )
}
