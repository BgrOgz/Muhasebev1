"""
Parser temel sınıfı
Tüm parser'lar bu interface'i uygular.
parse() → standart dict döndürür → InvoiceProcessor tarafından tüketilir.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional


@dataclass
class ParsedInvoice:
    """
    Parser'dan dönen standart fatura verisi.
    InvoiceProcessor bu yapıyı DB modeline dönüştürür.
    """
    invoice_number: str
    invoice_date: date
    amount: Decimal           # KDV hariç tutar
    tax_amount: Decimal       # KDV tutarı
    total_amount: Decimal     # Genel toplam

    # Tedarikçi bilgileri
    supplier_name: str
    supplier_vat: Optional[str] = None
    supplier_email: Optional[str] = None

    # Opsiyonel
    currency: str = "TRY"
    due_date: Optional[date] = None

    # Ham XML içeriği (UBL-TR için JSONB'ye yazılır)
    ubl_xml: Optional[dict] = None

    # Fatura kalemleri
    line_items: list[dict] = field(default_factory=list)

    # Parse meta
    source_format: str = "unknown"   # "xml" | "pdf"
    parse_warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """InvoiceProcessor'ın beklediği sözlük formatına çevir"""
        return {
            "invoice_number": self.invoice_number,
            "invoice_date": self.invoice_date,
            "amount": self.amount,
            "tax_amount": self.tax_amount,
            "total_amount": self.total_amount,
            "currency": self.currency,
            "due_date": self.due_date,
            "supplier_name": self.supplier_name,
            "supplier_vat": self.supplier_vat,
            "ubl_xml": self.ubl_xml,
            "line_items": self.line_items,
            "source_format": self.source_format,
        }


class BaseParser(ABC):
    """Tüm parser'ların uygulaması gereken arayüz"""

    def __init__(self, content: bytes):
        self.content = content

    @abstractmethod
    def parse(self) -> dict:
        """
        İçeriği parse et, standart dict döndür.
        Hata durumunda ValueError fırlatır.
        """
        ...
