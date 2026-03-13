"""
PDF E-Fatura Parser
──────────────────────────────────────────────────────────────────
Dört strateji sırayla denenir:
  0. PDF'in gömülü dosya eklerinde UBL-TR XML varsa → UBLParser'a devreder
  1. PDF metin içeriğinde gömülü UBL-TR XML varsa → UBLParser'a devreder
  2. PyPDF2 ile metin çıkarılabiliyorsa → regex ile parse eder
  3. Yukarıdakiler başarısız olursa → Claude Vision API ile görüntü OCR

GİB'in ürettiği e-fatura PDF'lerinde genellikle gömülü XML bulunur.
Görüntü tabanlı (taranmış) PDF'ler için Claude Vision kullanılır.

Satıcı/Alıcı ayrımı: Türk e-faturalarında "SAYIN" kelimesi alıcı
bölümünün başlangıcını işaret eder. Bu bölüme göre satıcı ve alıcı
bilgileri ayrı ayrı çıkarılır.
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

ÖNEMLİ:
- supplier_name: Faturanın SOL ÜST köşesindeki SATICI bilgisini yaz (alıcı değil!)
- supplier_vat: Satıcının TCKN veya VKN numarasını yaz
- line_items: Fatura kalemlerini (mal/hizmet adı ve tutarı) çıkar

{
  "invoice_number": "<fatura numarası>",
  "invoice_date": "<YYYY-MM-DD>",
  "due_date": "<YYYY-MM-DD veya null>",
  "supplier_name": "<SATICI/tedarikçi tam ünvanı — sol üst köşedeki firma/kişi>",
  "supplier_vat": "<satıcının vergi/TC kimlik numarası>",
  "amount": <KDV hariç tutar, sayı>,
  "tax_amount": <hesaplanan KDV tutarı, sayı>,
  "total_amount": <ödenecek/vergiler dahil toplam tutar, sayı>,
  "currency": "TRY",
  "line_items": [
    {"name": "<mal/hizmet adı>", "amount": <tutar>}
  ]
}

Yalnızca JSON döndür, başka hiçbir şey yazma."""


class PDFParser(BaseParser):
    """
    PDF e-faturayı parse eder.
    Önce gömülü XML arar, sonra metin, son çare Claude Vision.
    """

    def parse(self) -> dict:
        """PDF'den fatura verisini çıkar — dört stratejili waterfall"""

        # ── Strateji 0: PDF dosya eklerinden gömülü XML ────────────────────────
        embedded_xml = self._extract_embedded_xml_attachment()
        if embedded_xml:
            logger.info("[PDFParser] PDF ekinden UBL-TR XML çıkarıldı, XML parser'a aktarılıyor.")
            from app.parsers.ubl_parser import UBLParser
            return UBLParser(embedded_xml).parse()

        # ── Strateji 1: Metin içinde gömülü UBL-TR XML ─────────────────────────
        text = self._extract_text()
        if text:
            xml_content = self._find_embedded_xml(text)
            if xml_content:
                logger.info("[PDFParser] Metin içinde UBL-TR XML bulundu, XML parser'a aktarılıyor.")
                from app.parsers.ubl_parser import UBLParser
                return UBLParser(xml_content).parse()

        # ── Strateji 2: Regex çıkarımı ──────────────────────────────────────────
        if text and len(text.strip()) > 50:
            logger.info("[PDFParser] Metin çıkarıldı, regex parse yapılıyor.")
            return self._extract_from_text(text)

        # ── Strateji 3: Claude Vision OCR ────────────────────────────────────────
        logger.info("[PDFParser] Metin çıkarılamadı, Claude Vision OCR başlatılıyor.")
        return self._extract_with_claude_vision()

    # ── Gömülü XML dosya eki çıkarma ────────────────────────────────────────────

    def _extract_embedded_xml_attachment(self) -> Optional[bytes]:
        """PDF'in gömülü dosya eklerinden (attachment) UBL-TR XML'i çıkar.
        GİB e-faturaları genellikle UBL-TR XML'i ek olarak gömer."""
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(stream=self.content, filetype="pdf")

            # PyMuPDF 1.x ve 2.x uyumu
            count = doc.embfile_count() if hasattr(doc, 'embfile_count') else 0

            for i in range(count):
                try:
                    info = doc.embfile_info(i)
                    name = info.get('name', '') or info.get('filename', '')
                    if name.lower().endswith('.xml'):
                        xml_data = doc.embfile_get(i)
                        if b'<Invoice' in xml_data or b'invoice' in xml_data.lower():
                            logger.debug(f"[PDFParser] Gömülü XML eki bulundu: {name}")
                            doc.close()
                            return xml_data
                except Exception:
                    continue

            doc.close()
        except Exception as exc:
            logger.debug(f"[PDFParser] Gömülü dosya eki çıkarma hatası: {exc}")
        return None

    # ── Metin çıkarma ───────────────────────────────────────────────────────────

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

    # ── Claude Vision OCR ───────────────────────────────────────────────────────

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
            max_tokens=1024,
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

        # Vision'dan gelen kalem bilgisi → ubl_xml uyumlu yapı oluştur
        vision_line_items = data.get("line_items", [])
        line_items = []
        ubl_invoice_lines = []
        for item in vision_line_items:
            if isinstance(item, dict) and item.get("name"):
                line_items.append({
                    "description": item["name"],
                    "amount": float(self._safe_decimal(item.get("amount"))),
                })
                ubl_invoice_lines.append({
                    "Item": {"Name": item["name"]},
                    "LineExtensionAmount": {"#text": str(item.get("amount", "0"))},
                })

        # ubl_xml uyumlu yapı (sınıflandırma için)
        ubl_xml = {
            "_source": "pdf-vision",
            "Invoice": {"InvoiceLine": ubl_invoice_lines} if ubl_invoice_lines else {},
        }

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
            ubl_xml=ubl_xml,
            line_items=line_items,
            source_format="pdf-vision",
            parse_warnings=warnings,
        )

        logger.info(
            f"[PDFParser/Vision] ✅ {invoice_number} | "
            f"{supplier_name} | {total_amount} {currency}"
        )
        return invoice.to_dict()

    # ── Gömülü XML tespiti (metin içinde) ───────────────────────────────────────

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

    # ── Regex ile metin çıkarımı (Strateji 2) ──────────────────────────────────

    def _extract_from_text(self, text: str) -> dict:
        """Türk e-fatura PDF formatından regex ile alan çıkar.
        Satıcı ve alıcı bölümlerini 'SAYIN' kelimesiyle ayırır."""
        warnings: list[str] = []

        # ── Satıcı / Alıcı bölümlerini ayır ─────────────────────────────────────
        seller_text, buyer_text = self._split_seller_buyer(text)

        # ── Fatura numarası ──────────────────────────────────────────────────────
        invoice_number = (
            self._match(text, r"Fatura\s*[Nn]o\.?\s*[:\-]?\s*([A-Z0-9\-]{6,30})")
            or self._match(text, r"FATURA\s*NO\.?\s*[:\-]?\s*([A-Z0-9\-]{6,30})")
            or self._match(text, r"Invoice\s*No\.?\s*[:\-]?\s*([A-Z0-9\-]{6,30})")
            or f"PDF-{hash(self.content) % 100000:05d}"
        )
        if invoice_number.startswith("PDF-"):
            warnings.append("Fatura numarası bulunamadı, geçici ID atandı.")

        # ── Tarihler ─────────────────────────────────────────────────────────────
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

        # ── Tutarlar ─────────────────────────────────────────────────────────────
        total_str = (
            self._match(text, r"Ödenecek\s*[Tt]utar[ıi]?\s*[:\-]?\s*([\d.,]+)")
            or self._match(text, r"Vergiler\s*[Dd]ahil\s*[Tt]oplam\s*[Tt]utar[ıi]?\s*[:\-]?\s*([\d.,]+)")
            or self._match(text, r"(?:Genel\s*)?Toplam\s*[:\-]?\s*([\d.,]+)\s*(?:TRY|TL|₺)?")
            or self._match(text, r"(?:GENEL\s*)?TOPLAM\s*[:\-]?\s*([\d.,]+)")
        )
        total_amount = self._parse_decimal(total_str)

        tax_str = (
            self._match(text, r"Hesaplanan\s*KDV\s*(?:\([^)]*\))?\s*[:\-]?\s*([\d.,]+)")
            or self._match(text, r"(?:Toplam\s*)?KDV\s*(?:Tutarı)?\s*[:\-]?\s*([\d.,]+)")
            or self._match(text, r"(?:TAX|VAT)\s*[:\-]?\s*([\d.,]+)")
        )
        tax_amount = self._parse_decimal(tax_str)

        amount_str = (
            self._match(text, r"KDV\s*[Mm]atrah[ıi]?\s*[:\-]?\s*([\d.,]+)")
            or self._match(text, r"Mal\s*Hizmet\s*Toplam\s*Tutar[ıi]?\s*[:\-]?\s*([\d.,]+)")
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

        # ── Tedarikçi — SADECE satıcı bölümünden çıkar ──────────────────────────
        supplier_name = self._extract_supplier_name(seller_text)
        supplier_vat = self._extract_supplier_vat(seller_text)

        if supplier_name == "Bilinmeyen Tedarikçi":
            warnings.append("Tedarikçi adı PDF'den çıkarılamadı.")

        # ── Para birimi ──────────────────────────────────────────────────────────
        currency = "TRY"
        if re.search(r"\bUSD\b|\$", text):
            currency = "USD"
        elif re.search(r"\bEUR\b|€", text):
            currency = "EUR"

        # ── Fatura kalemlerini çıkar ─────────────────────────────────────────────
        line_items = self._extract_line_items_from_text(text)

        # ── ubl_xml uyumlu yapı oluştur (sınıflandırma AI'ı için) ────────────────
        ubl_xml_data = self._build_classification_data(line_items, text)

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
            ubl_xml=ubl_xml_data,
            line_items=line_items,
            source_format="pdf",
            parse_warnings=warnings,
        )

        logger.info(
            f"[PDFParser] ✅ {invoice_number} | "
            f"{supplier_name} | {total_amount} {currency}"
        )
        return invoice.to_dict()

    # ── Satıcı / Alıcı bölüm ayırma ────────────────────────────────────────────

    @staticmethod
    def _split_seller_buyer(text: str) -> tuple[str, str]:
        """E-fatura PDF'inde satıcı ve alıcı bölümlerini ayır.
        Türk e-faturalarında 'SAYIN' kelimesi alıcı bölümünün başlangıcıdır."""
        # "SAYIN" satırında böl — öncesi satıcı, sonrası alıcı
        match = re.search(r'\bSAYIN\b', text, re.IGNORECASE)
        if match:
            return text[:match.start()], text[match.start():]

        # Alternatif: "Alıcı" etiketiyle böl
        match2 = re.search(r'\b[Aa]lıcı\b', text)
        if match2:
            return text[:match2.start()], text[match2.start():]

        return text, ""

    def _extract_supplier_name(self, seller_text: str) -> str:
        """Satıcı adını SATICI bölümünden çıkar.
        Standart etiketler bulunamazsa ilk anlamlı satırı kullan."""

        # 1. Standart etiketlerle dene
        name = (
            self._match(seller_text, r"[Ss]atıcı\s*[Üü]nvan[ıi]?\s*[:\-]?\s*([^\n]{3,80})")
            or self._match(seller_text, r"[Ff]irma\s*[Üü]nvan[ıi]?\s*[:\-]?\s*([^\n]{3,80})")
            or self._match(seller_text, r"Supplier\s*[:\-]?\s*([^\n]{3,60})")
        )
        if name and name.strip():
            return name.strip().rstrip(":")

        # 2. Etiket yoksa: satıcı bölümünün ilk anlamlı satırı firma/kişi adıdır
        #    (Türk e-faturalarında standart format)
        lines = [l.strip() for l in seller_text.strip().split('\n') if l.strip()]

        # Atlanacak satır kalıpları (adres, telefon, vergi dairesi, vb.)
        skip_patterns = [
            r'^Tel\b', r'^Fax\b', r'^E-?[Pp]osta', r'^Vergi\s*[Dd]airesi',
            r'^TCKN\b', r'^VKN\b', r'^\d{10,}$', r'^Kapı\s*No',
            r'^e-?[Ff]atura', r'^e-?FATURA', r'^Özelleştirme',
            r'^Senaryo', r'^Fatura\s*[Tt]ipi', r'^Fatura\s*[Nn]o',
            r'^ETTN\b', r'^Sıra', r'^Mal\s*Hizmet',
        ]

        for line in lines[:6]:  # İlk 6 satıra bak
            if len(line) < 3:
                continue
            # Skip metadata/address patterns
            if any(re.match(p, line, re.IGNORECASE) for p in skip_patterns):
                continue
            # Skip sadece şehir/ilçe olan satırlar
            if re.match(r'^[A-ZÇĞİÖŞÜ]+\s*/\s*[A-Za-zçğıöşü]+$', line):
                continue
            # Skip sokak/mahalle adresleri
            if re.search(r'\b(SK\.|SOK\.|MAH\.|MH\.|CAD\.|CD\.|BL\.|BLOK|NO\s*:)', line, re.IGNORECASE):
                continue
            # Bu satır büyük olasılıkla firma/kişi adıdır
            return line[:80]

        return "Bilinmeyen Tedarikçi"

    def _extract_supplier_vat(self, seller_text: str) -> Optional[str]:
        """Satıcı vergi/kimlik numarasını SADECE satıcı bölümünden çıkar.
        Bu sayede alıcının VKN'si yanlışlıkla satıcıya atanmaz."""
        return (
            self._match(seller_text, r"TCKN\s*[:\-]?\s*(\d{11})")
            or self._match(seller_text, r"VKN\s*[:\-]?\s*(\d{10,11})")
            or self._match(seller_text, r"[Vv]ergi\s*[Nn]o\.?\s*[:\-]?\s*(\d{10,11})")
        )

    # ── Fatura kalemlerini metinden çıkarma ─────────────────────────────────────

    def _extract_line_items_from_text(self, text: str) -> list[dict]:
        """PDF metninden fatura kalemlerini (mal/hizmet satırlarını) çıkar.
        Türk e-faturalarında tipik tablo formatı:
          Sıra No | Mal Hizmet | Miktar | Birim Fiyat | ...
        """
        items = []

        # Yöntem 1: Numaralı satırları bul (1  ürün adı  miktar  fiyat ...)
        # Sıra numarası ile başlayan satırları yakala
        pattern = r'(?:^|\n)\s*(\d{1,3})\s+([A-Za-zÇçĞğİıÖöŞşÜü\s\-\.\,\/\(\)]+?)' \
                  r'\s+([\d,\.]+)\s*(?:Adet|adet|KG|kg|M2|m2|MT|LT|lt|TON|C62)'
        matches = re.findall(pattern, text, re.MULTILINE)

        for m in matches:
            seq_no, desc, qty = m
            desc = desc.strip()
            if len(desc) >= 2 and desc.lower() not in ('mal', 'hizmet', 'sıra'):
                items.append({
                    "description": desc,
                    "quantity": qty,
                })

        # Yöntem 2: Basit mal/hizmet açıklaması yakalama (eğer yukarıdaki bulamadıysa)
        if not items:
            # "1  yem bedeli" gibi basit formatları yakala
            simple_pattern = r'(?:^|\n)\s*(\d{1,3})\s+([A-Za-zÇçĞğİıÖöŞşÜü][A-Za-zÇçĞğİıÖöŞşÜü\s\-\.\,\/\(\)]{2,50})'
            simple_matches = re.findall(simple_pattern, text, re.MULTILINE)

            for m in simple_matches:
                seq_no, desc = m
                desc = desc.strip()
                # Skip table headers and metadata
                skip_words = [
                    'mal hizmet', 'sıra no', 'birim fiyat', 'kdv oranı',
                    'kdv tutarı', 'diğer vergiler', 'fatura no', 'fatura tarihi',
                    'toplam tutar', 'toplam iskonto', 'özelleştirme',
                    'hesaplanan kdv', 'ödenecek tutar', 'vergiler dahil',
                    'vergi istisna', 'yalnız', 'not:',
                ]
                if any(desc.lower().startswith(w) for w in skip_words):
                    continue
                if len(desc) >= 2:
                    items.append({"description": desc})

        return items[:20]  # max 20 kalem

    # ── Sınıflandırma için ubl_xml uyumlu yapı ─────────────────────────────────

    @staticmethod
    def _build_classification_data(
        line_items: list[dict], raw_text: str
    ) -> dict:
        """PDF'den çıkarılan verileri classification_service'in okuyabileceği
        ubl_xml uyumlu yapıya çevir.

        Classification service ubl_xml.Invoice.InvoiceLine yapısını okur.
        Ayrıca ham metin (_raw_text) saklanarak AI'a gönderilir.
        """
        # InvoiceLine yapısını oluştur
        invoice_lines = []
        for item in line_items:
            invoice_lines.append({
                "Item": {"Name": item.get("description", "")},
                "LineExtensionAmount": {"#text": str(item.get("amount", "0"))},
            })

        result = {
            "_source": "pdf_text",
            "_raw_text": raw_text[:5000] if raw_text else "",  # max 5000 karakter
        }

        if invoice_lines:
            result["Invoice"] = {"InvoiceLine": invoice_lines}

        return result

    # ── Yardımcılar ─────────────────────────────────────────────────────────────

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
