"""
PDF E-Fatura Parser
──────────────────────────────────────────────────────────────────
Üç strateji sırayla denenir:
  1. PDF içinde gömülü UBL-TR XML varsa → UBLParser'a devreder
  2. PyPDF2 ile metin çıkarılabiliyorsa → regex ile parse eder
  3. Yukarıdakiler başarısız olursa → Claude Vision API ile görüntü OCR

GİB'in ürettiği e-fatura PDF'lerinde genellikle gömülü XML bulunur.
Görüntü tabanlı (taranmış) PDF'ler için Claude Vision kullanılır.
"""

import io
import json
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from app.parsers.base_parser import BaseParser, ParsedInvoice
from app.utils.logger import logger

# Claude Vision için prompt sabitleri
_VISION_SYSTEM = """Sen bir e-fatura OCR uzmanısın. Verilen fatura görüntüsünden
tüm fatura alanlarını eksiksiz oku ve yalnızca JSON döndür."""

_VISION_USER = """Bu fatura görüntüsünden aşağıdaki JSON formatında verileri çıkar.
Sayısal değerleri nokta ondalık ayırıcıyla döndür (örn: 99.80).
Bulamadığın alanlar için null kullan.

{
  "invoice_number": "<fatura numarası>",
  "invoice_date": "<YYYY-MM-DD>",
  "due_date": "<YYYY-MM-DD veya null>",
  "supplier_name": "<tedarikçi/satıcı tam ünvanı>",
  "supplier_vat": "<vergi numarası veya null>",
  "amount": <KDV hariç tutar, sayı>,
  "tax_amount": <hesaplanan KDV tutarı, sayı>,
  "total_amount": <ödenecek/vergiler dahil toplam tutar, sayı>,
  "currency": "TRY"
}

Yalnızca JSON döndür, başka hiçbir şey yazma."""


class PDFParser(BaseParser):
    """
    PDF e-faturayı parse eder.
    Önce gömülü XML arar, sonra metin, son çare Claude Vision.
    """

    def parse(self) -> dict:
        """PDF'den fatura verisini çıkar — üç stratejili waterfall"""

        # ── Strateji 1: Gömülü UBL-TR XML ────────────────────────────────────
        text = self._extract_text()
        if text:
            xml_content = self._find_embedded_xml(text)
            if xml_content:
                logger.info("[PDFParser] Gömülü UBL-TR XML bulundu, XML parser'a aktarılıyor.")
                from app.parsers.ubl_parser import UBLParser
                return UBLParser(xml_content).parse()

        # ── Strateji 2: Regex çıkarımı ────────────────────────────────────────
        if text and len(text.strip()) > 50:
            logger.info("[PDFParser] Metin çıkarıldı, regex parse yapılıyor.")
            return self._extract_from_text(text)

        # ── Strateji 3: Claude Vision OCR ─────────────────────────────────────
        logger.info("[PDFParser] Metin çıkarılamadı, Claude Vision OCR başlatılıyor.")
        return self._extract_with_claude_vision()

    # ── Metin çıkarma ─────────────────────────────────────────────────────────

    def _extract_text(self) -> str:
        """PyPDF2 ile PDF'den düz metin çıkar"""
        try:
            import PyPDF2

            reader = PyPDF2.PdfReader(io.BytesIO(self.content))
            pages_text = []
            for page in reader.pages:
                page_text = page.extract_text() or ""
                pages_text.append(page_text)
            full_text = "\n".join(pages_text)
            logger.debug(f"[PDFParser] {len(reader.pages)} sayfa, {len(full_text)} karakter çıkarıldı.")
            return full_text
        except Exception as exc:
            logger.error(f"[PDFParser] PyPDF2 hatası: {exc}")
            return ""

    # ── Claude Vision OCR ─────────────────────────────────────────────────────

    def _extract_with_claude_vision(self) -> dict:
        """
        PDF sayfalarını PNG görüntüye çevirip Claude Vision API'ye gönderir.
        Dönen JSON'dan ParsedInvoice oluşturur.
        """
        images = self._pdf_to_images()
        if not images:
            raise ValueError("PDF görüntüye dönüştürülemedi.")

        logger.info(f"[PDFParser] {len(images)} sayfa görüntüye dönüştürüldü, Claude'a gönderiliyor.")

        from app.external.claude_client import claude_client

        raw = claude_client.complete_with_images(
            system_prompt=_VISION_SYSTEM,
            user_message=_VISION_USER,
            images=images,
            image_media_type="image/png",
            max_tokens=512,
        )

        return self._parse_vision_response(raw)

    def _pdf_to_images(self, dpi: int = 150) -> list[bytes]:
        """
        PyMuPDF ile PDF sayfalarını PNG bayt dizisine çevirir.
        Sadece ilk 3 sayfayı işler (fatura genelde tek sayfadır).
        """
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(stream=self.content, filetype="pdf")
            images: list[bytes] = []
            mat = fitz.Matrix(dpi / 72, dpi / 72)

            for page_num in range(min(3, len(doc))):
                page = doc[page_num]
                pix = page.get_pixmap(matrix=mat)
                images.append(pix.tobytes("png"))

            doc.close()
            return images

        except Exception as exc:
            logger.error(f"[PDFParser] PDF→görüntü dönüşüm hatası: {exc}")
            return []

    def _parse_vision_response(self, raw: str) -> dict:
        """Claude Vision'ın JSON yanıtını ParsedInvoice'a çevir"""
        warnings: list[str] = []

        # JSON bloğunu çıkar
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not json_match:
            raise ValueError(f"Claude Vision geçerli JSON döndürmedi: {raw[:200]}")

        try:
            data = json.loads(json_match.group())
        except json.JSONDecodeError as exc:
            raise ValueError(f"Claude Vision JSON parse hatası: {exc}")

        # Fatura numarası
        invoice_number = data.get("invoice_number") or f"PDF-{hash(self.content) % 100000:05d}"
        if not data.get("invoice_number"):
            warnings.append("Fatura numarası bulunamadı, geçici ID atandı.")

        # Tarihler
        invoice_date = self._parse_date(data.get("invoice_date")) or date.today()
        due_date = self._parse_date(data.get("due_date"))

        # Tutarlar
        amount = self._safe_decimal(data.get("amount"))
        tax_amount = self._safe_decimal(data.get("tax_amount"))
        total_amount = self._safe_decimal(data.get("total_amount"))

        # Tutarları tamamla
        if total_amount > 0 and tax_amount > 0 and amount == 0:
            amount = total_amount - tax_amount
        elif total_amount == 0 and amount > 0:
            total_amount = amount + tax_amount

        # Tedarikçi
        supplier_name = (data.get("supplier_name") or "Bilinmeyen Tedarikçi").strip()
        supplier_vat = data.get("supplier_vat")

        # Para birimi
        currency = (data.get("currency") or "TRY").upper()

        for w in warnings:
            logger.warning(f"[PDFParser/Vision] {invoice_number}: {w}")

        invoice = ParsedInvoice(
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            amount=amount,
            tax_amount=tax_amount,
            total_amount=total_amount,
            currency=currency,
            due_date=due_date,
            supplier_name=supplier_name,
            supplier_vat=supplier_vat,
            source_format="pdf-vision",
            parse_warnings=warnings,
        )

        logger.info(
            f"[PDFParser/Vision] ✅ {invoice_number} | "
            f"{supplier_name} | {total_amount} {currency}"
        )
        return invoice.to_dict()

    # ── Gömülü XML tespiti ────────────────────────────────────────────────────

    @staticmethod
    def _find_embedded_xml(text: str) -> Optional[bytes]:
        """PDF metninde UBL-TR XML bloğu ara."""
        pattern = r"(<\?xml[^?]*\?>.*?</Invoice>)"
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).encode("utf-8")

        pattern2 = r"(<Invoice[^>]*>.*?</Invoice>)"
        match2 = re.search(pattern2, text, re.DOTALL | re.IGNORECASE)
        if match2:
            xml_str = '<?xml version="1.0" encoding="UTF-8"?>' + match2.group(1)
            return xml_str.encode("utf-8")

        return None

    # ── Regex ile metin çıkarımı ──────────────────────────────────────────────

    def _extract_from_text(self, text: str) -> dict:
        """Türk e-fatura PDF formatından regex ile alan çıkar."""
        warnings: list[str] = []

        invoice_number = (
            self._match(text, r"Fatura\s*[Nn]o\.?\s*[:\-]?\s*([A-Z0-9\-]{6,30})")
            or self._match(text, r"FATURA\s*NO\.?\s*[:\-]?\s*([A-Z0-9\-]{6,30})")
            or self._match(text, r"Invoice\s*No\.?\s*[:\-]?\s*([A-Z0-9\-]{6,30})")
            or f"PDF-{hash(self.content) % 100000:05d}"
        )
        if invoice_number.startswith("PDF-"):
            warnings.append("Fatura numarası bulunamadı, geçici ID atandı.")

        date_str = (
            self._match(text, r"Fatura\s*[Tt]arihi\s*[:\-]?\s*(\d{2}[/.\-]\d{2}[/.\-]\d{4})")
            or self._match(text, r"Düzenleme\s*[Tt]arihi\s*[:\-]?\s*(\d{2}[/.\-]\d{2}[/.\-]\d{4})")
            or self._match(text, r"(\d{2}[/.\-]\d{2}[/.\-]\d{4})")
        )
        invoice_date = self._parse_date(date_str) or date.today()
        if not date_str:
            warnings.append("Fatura tarihi bulunamadı, bugünkü tarih kullanıldı.")

        due_date_str = self._match(
            text, r"Vade\s*[Tt]arihi\s*[:\-]?\s*(\d{2}[/.\-]\d{2}[/.\-]\d{4})"
        )
        due_date = self._parse_date(due_date_str)

        total_str = (
            self._match(text, r"(?:Genel\s*)?Toplam\s*[:\-]?\s*([\d.,]+)\s*(?:TRY|TL|₺)?")
            or self._match(text, r"(?:GENEL\s*)?TOPLAM\s*[:\-]?\s*([\d.,]+)")
            or self._match(text, r"Ödenecek\s*[Tt]utar\s*[:\-]?\s*([\d.,]+)")
        )
        total_amount = self._parse_decimal(total_str)

        tax_str = (
            self._match(text, r"(?:Toplam\s*)?KDV\s*(?:Tutarı)?\s*[:\-]?\s*([\d.,]+)")
            or self._match(text, r"KDV\s*[:\-]?\s*([\d.,]+)")
            or self._match(text, r"(?:TAX|VAT)\s*[:\-]?\s*([\d.,]+)")
        )
        tax_amount = self._parse_decimal(tax_str)

        amount_str = (
            self._match(text, r"(?:KDV\s*)?[Mm]atrah\s*[:\-]?\s*([\d.,]+)")
            or self._match(text, r"Ara\s*[Tt]oplam\s*[:\-]?\s*([\d.,]+)")
        )
        amount = self._parse_decimal(amount_str)

        if total_amount > Decimal("0") and tax_amount > Decimal("0") and amount == Decimal("0"):
            amount = total_amount - tax_amount
        elif total_amount == Decimal("0") and amount > Decimal("0"):
            total_amount = amount + tax_amount
            warnings.append("Toplam tutar hesaplandı.")
        elif total_amount == Decimal("0"):
            warnings.append("Tutar bilgileri bulunamadı.")

        supplier_name = (
            self._match(text, r"[Ss]atıcı\s*(?:[Uu]nvanı?)?\s*[:\-]?\s*([^\n]{3,60})")
            or self._match(text, r"[Ff]irma\s*(?:[Uu]nvanı?)?\s*[:\-]?\s*([^\n]{3,60})")
            or self._match(text, r"Supplier\s*[:\-]?\s*([^\n]{3,60})")
            or "Bilinmeyen Tedarikçi"
        )
        supplier_name = supplier_name.strip().rstrip(":")

        supplier_vat = (
            self._match(text, r"[Vv]ergi\s*[Nn]o\.?\s*[:\-]?\s*(\d{10,11})")
            or self._match(text, r"VKN\s*[:\-]?\s*(\d{10,11})")
            or self._match(text, r"TCKN\s*[:\-]?\s*(\d{11})")
        )

        currency = "TRY"
        if re.search(r"\bUSD\b|\$", text):
            currency = "USD"
        elif re.search(r"\bEUR\b|€", text):
            currency = "EUR"

        for w in warnings:
            logger.warning(f"[PDFParser] {invoice_number}: {w}")

        invoice = ParsedInvoice(
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            amount=amount,
            tax_amount=tax_amount,
            total_amount=total_amount,
            currency=currency,
            due_date=due_date,
            supplier_name=supplier_name,
            supplier_vat=supplier_vat,
            source_format="pdf",
            parse_warnings=warnings,
        )

        logger.info(
            f"[PDFParser] ✅ {invoice_number} | "
            f"{supplier_name} | {total_amount} {currency}"
        )
        return invoice.to_dict()

    # ── Yardımcılar ───────────────────────────────────────────────────────────

    @staticmethod
    def _match(text: str, pattern: str) -> Optional[str]:
        m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        return m.group(1).strip() if m else None

    @staticmethod
    def _parse_date(value: Optional[str]) -> Optional[date]:
        if not value:
            return None
        value = value.strip()
        for fmt in ("%d/%m/%Y", "%d.%m.%Y", "%d-%m-%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(value, fmt).date()
            except ValueError:
                continue
        return None

    @staticmethod
    def _parse_decimal(value: Optional[str]) -> Decimal:
        if not value:
            return Decimal("0")
        cleaned = value.strip()
        if "," in cleaned and "." in cleaned:
            cleaned = cleaned.replace(".", "").replace(",", ".")
        elif "," in cleaned:
            cleaned = cleaned.replace(",", ".")
        cleaned = re.sub(r"[^\d.]", "", cleaned)
        try:
            return Decimal(cleaned) if cleaned else Decimal("0")
        except Exception:
            return Decimal("0")

    @staticmethod
    def _safe_decimal(value) -> Decimal:
        """Claude'un döndürdüğü sayısal değeri Decimal'e çevir"""
        if value is None:
            return Decimal("0")
        try:
            return Decimal(str(value).strip())
        except Exception:
            return Decimal("0")
