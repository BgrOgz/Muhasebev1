/**
 * API hataları için yardımcı fonksiyonlar
 */

export interface ApiError {
  status?: number
  code?: string
  message: string
  detail?: string
}

export function parseApiError(error: unknown): ApiError {
  // Axios error
  if (error && typeof error === 'object' && 'response' in error) {
    const axiosError = error as any
    const status = axiosError.response?.status
    const data = axiosError.response?.data

    if (data && typeof data === 'object') {
      return {
        status,
        code: data.code || 'UNKNOWN_ERROR',
        message: data.message || 'Sunucu hatası',
        detail: data.detail || undefined,
      }
    }

    return {
      status,
      code: 'NETWORK_ERROR',
      message: axiosError.message || 'Sunucuya bağlanılamadı',
    }
  }

  // Standard error
  if (error instanceof Error) {
    return {
      code: 'UNKNOWN_ERROR',
      message: error.message,
    }
  }

  return {
    code: 'UNKNOWN_ERROR',
    message: 'Bilinmeyen bir hata oluştu',
  }
}

export function getErrorMessage(error: unknown): string {
  const parsed = parseApiError(error)

  const messages: Record<number, string> = {
    400: 'Geçersiz istek. Lütfen bilgileri kontrol edin.',
    401: 'Oturum süresi dolmuş. Lütfen tekrar giriş yapın.',
    403: 'Bu işlemi yapmaya izniniz yok.',
    404: 'İstenen kaynak bulunamadı.',
    409: 'Bu veriler çelişkili veya zaten mevcut.',
    422: 'Lütfen tüm gerekli alanları doldurun.',
    429: 'Çok fazla istek gönderdiniz. Lütfen biraz bekleyin.',
    500: 'Sunucu hatası. Lütfen daha sonra tekrar deneyin.',
  }

  // Backend'den gelen spesifik mesaj varsa onu öncelikle kullan
  if (parsed.detail) return parsed.detail
  if (parsed.message && parsed.message !== 'Sunucu hatası') return parsed.message

  if (parsed.status && parsed.status in messages) {
    return messages[parsed.status]
  }

  return 'Bir hata oluştu. Lütfen tekrar deneyin.'
}

export function isNetworkError(error: unknown): boolean {
  const parsed = parseApiError(error)
  return parsed.code === 'NETWORK_ERROR' || !parsed.status
}

export function isAuthError(error: unknown): boolean {
  const parsed = parseApiError(error)
  return parsed.status === 401 || parsed.status === 403
}

export function isValidationError(error: unknown): boolean {
  const parsed = parseApiError(error)
  return parsed.status === 422 || parsed.status === 400
}

export function isServerError(error: unknown): boolean {
  const parsed = parseApiError(error)
  return parsed.status ? parsed.status >= 500 : false
}
