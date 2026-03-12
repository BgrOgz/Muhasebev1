"""
Özel HTTP istisnaları
FastAPI exception handler'lar bu sınıfları yakalar.
"""

from fastapi import HTTPException, status


class NotFoundError(HTTPException):
    def __init__(self, resource: str = "Kayıt"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource} bulunamadı.",
        )


class UnauthorizedError(HTTPException):
    def __init__(self, detail: str = "Kimlik doğrulaması gerekli."):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class ForbiddenError(HTTPException):
    def __init__(self, detail: str = "Bu işlem için yetkiniz yok."):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


class ConflictError(HTTPException):
    def __init__(self, detail: str = "Kayıt zaten mevcut."):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail,
        )


class ValidationError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        )


class FileTooLargeError(HTTPException):
    def __init__(self, max_mb: int):
        super().__init__(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Dosya boyutu {max_mb} MB limitini aşıyor.",
        )


class InvalidFileTypeError(HTTPException):
    def __init__(self, allowed: list[str]):
        super().__init__(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Geçersiz dosya türü. İzin verilenler: {', '.join(allowed)}",
        )


class DuplicateInvoiceError(HTTPException):
    def __init__(self, invoice_number: str):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Bu fatura zaten sistemde kayıtlı: {invoice_number}",
        )
