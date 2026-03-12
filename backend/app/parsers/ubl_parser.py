"""
UBL-TR 2.1 XML Parser
──────────────────────────────────────────────────────────────────
Türkiye'nin resmi e-fatura standardı olan UBL-TR 2.1 formatını parse eder.
GİB tarafından belirlenen namespace'ler kullanılır.

Namespace referansı:
  urn:oasis:names:specification:ubl:schema:xsd:Invoice-2
  urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2 (cac)
  urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2     (cbc)
"""

import json
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional
from xml.etree import ElementTree as ET

from app.parsers.base_parser import BaseParser, ParsedInvoice
from app.utils.logger import logger

# ── UBL-TR Namespace'leri ─────────────────────────────────────────────────────
NS = {
    "inv": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
}


class UBLParser(BaseParser):
    """
    UBL-TR 2.1 XML dosyasını parse eder.
    Hem tam UBL-TR hem de basit XML fatura formatlarını destekler.
    """

    def parse(self) -> dict:
        """XML içeriğini parse et, standart fatura dict'i döndür"""
        try:
            root = ET.fromstring(self.content)
        except ET.ParseError as exc:
            raise ValueError(f"Geçersiz XML formatı: {exc}") from exc

        warnings: list[str] = []

        # Root tag'i kontrol et
        tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag
        if tag not in ("Invoice", "CreditNote", "DebitNote"):
            logger.warning(f"Beklenmeyen root tag: {tag}")
            warnings.append(f"Beklenmeyen root tag: {tag}")

        # ── Temel alanlar ─────────────────────────────────────────────────────
        invoice_number = self._get_text(root, ".//cbc:ID") or self._get_text(
            root, ".//ID"
        )
        if not invoice_number:
            raise ValueError("Fatura numarası (ID) bulunamadı.")

        invoice_date_str = self._get_text(root, ".//cbc:IssueDate") or self._get_text(
            root, ".//IssueDate"
        )
        invoice_date = self._parse_date(invoice_date_str)
        if not invoice_date:
            raise ValueError(f"Fatura tarihi geçersiz: {invoice_date_str}")

        due_date_str = self._get_text(root, ".//cac:PaymentMeans/cbc:PaymentDueDate")
        due_date = self._parse_date(due_date_str)

        currency = (
            self._get_attrib(root, ".//cbc:LineExtensionAmount", "currencyID")
            or self._get_attrib(root, ".//cbc:TaxExclusiveAmount", "currencyID")
            or "TRY"
        )

        # ── Tutarlar ──────────────────────────────────────────────────────────
        # KDV hariç tutar
        amount = self._parse_decimal(
            self._get_text(root, ".//cac:LegalMonetaryTotal/cbc:TaxExclusiveAmount")
            or self._get_text(root, ".//cbc:LineExtensionAmount")
        )

        # KDV tutarı
        tax_amount = self._parse_decimal(
            self._get_text(root, ".//cac:TaxTotal/cbc:TaxAmount")
        )

        # Genel toplam
        total_amount = self._parse_decimal(
            self._get_text(root, ".//cac:LegalMonetaryTotal/cbc:PayableAmount")
            or self._get_text(root, ".//cac:LegalMonetaryTotal/cbc:TaxInclusiveAmount")
        )

        # Toplam hesaplanamadıysa amount + tax'tan hesapla
        if total_amount == Decimal("0"):
            total_amount = amount + tax_amount
            warnings.append("Genel toplam hesaplandı (amount + tax).")

        # ── Tedarikçi bilgileri ────────────────────────────────────────────────
        supplier_name = (
            self._get_text(root, ".//cac:AccountingSupplierParty//cbc:RegistrationName")
            or self._get_text(root, ".//cac:AccountingSupplierParty//cbc:Name")
            or self._get_text(root, ".//cac:SupplierParty//cbc:Name")
            or "Bilinmeyen Tedarikçi"
        )

        supplier_vat = (
            self._get_text(root, ".//cac:AccountingSupplierParty//cbc:CompanyID")
            or self._get_text(
                root,
                ".//cac:AccountingSupplierParty//cac:PartyTaxScheme/cbc:CompanyID",
            )
        )

        # ── Fatura kalemleri ──────────────────────────────────────────────────
        line_items = self._parse_line_items(root)

        # ── Ham XML → dict (JSONB için) ───────────────────────────────────────
        ubl_xml = self._xml_to_dict(root)

        # Uyarı varsa logla
        for w in warnings:
            logger.warning(f"[UBLParser] {invoice_number}: {w}")

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
            source_format="xml",
            parse_warnings=warnings,
        )

        logger.info(
            f"[UBLParser] ✅ {invoice_number} | "
            f"{supplier_name} | {total_amount} {currency}"
        )
        return invoice.to_dict()

    # ── Fatura kalemleri ───────────────────────────────────────────────────────

    def _parse_line_items(self, root: ET.Element) -> list[dict]:
        """InvoiceLine bloklarını parse et"""
        items = []
        lines = root.findall(".//cac:InvoiceLine", NS) or root.findall(
            ".//{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}InvoiceLine"
        )

        for line in lines:
            try:
                description = (
                    self._get_text(line, ".//cac:Item/cbc:Name")
                    or self._get_text(line, ".//cbc:Description")
                    or "-"
                )
                quantity = self._parse_decimal(
                    self._get_text(line, ".//cbc:InvoicedQuantity") or "1"
                )
                unit = self._get_attrib(line, ".//cbc:InvoicedQuantity", "unitCode") or "C62"
                unit_price = self._parse_decimal(
                    self._get_text(line, ".//cac:Price/cbc:PriceAmount") or "0"
                )
                line_amount = self._parse_decimal(
                    self._get_text(line, ".//cbc:LineExtensionAmount") or "0"
                )
                vat_rate = self._parse_decimal(
                    self._get_text(line, ".//cac:TaxTotal//cbc:Percent") or "0"
                )

                items.append({
                    "description": description,
                    "quantity": float(quantity),
                    "unit": unit,
                    "unit_price": float(unit_price),
                    "amount": float(line_amount),
                    "vat_rate": float(vat_rate),
                })
            except Exception as exc:
                logger.warning(f"[UBLParser] Kalem parse hatası: {exc}")
                continue

        return items

    # ── XML → dict dönüştürücü ────────────────────────────────────────────────

    @staticmethod
    def _xml_to_dict(element: ET.Element) -> dict:
        """
        ElementTree'yi JSONB'ye yazılabilir dict'e çevir.
        Namespace prefix'lerini temizler.
        """
        def _strip_ns(tag: str) -> str:
            return tag.split("}")[-1] if "}" in tag else tag

        def _elem_to_dict(elem: ET.Element):  # -> Union[dict, str]
            result: dict = {}

            # Attributes
            if elem.attrib:
                result["@"] = {_strip_ns(k): v for k, v in elem.attrib.items()}

            # Children
            children = list(elem)
            if children:
                for child in children:
                    key = _strip_ns(child.tag)
                    value = _elem_to_dict(child)
                    if key in result:
                        if not isinstance(result[key], list):
                            result[key] = [result[key]]
                        result[key].append(value)
                    else:
                        result[key] = value
            else:
                text = (elem.text or "").strip()
                if result:
                    if text:
                        result["#text"] = text
                else:
                    return text

            return result

        return {_strip_ns(element.tag): _elem_to_dict(element)}

    # ── Yardımcılar ───────────────────────────────────────────────────────────

    def _get_text(self, element: ET.Element, xpath: str) -> Optional[str]:
        """XPath ile element bul ve text içeriğini döndür"""
        # Önce namespace'li dene
        found = element.find(xpath, NS)
        if found is not None and found.text:
            return found.text.strip()

        # Namespace olmadan dene (basit XML için)
        simple_xpath = xpath.replace("cbc:", "").replace("cac:", "").replace("inv:", "")
        found = element.find(simple_xpath)
        if found is not None and found.text:
            return found.text.strip()

        return None

    def _get_attrib(
        self, element: ET.Element, xpath: str, attrib: str
    ) -> Optional[str]:
        """XPath ile element bul ve attribute'unu döndür"""
        found = element.find(xpath, NS)
        if found is not None:
            return found.get(attrib)
        return None

    @staticmethod
    def _parse_date(value: Optional[str]) -> Optional[date]:
        """'YYYY-MM-DD' veya 'DD/MM/YYYY' formatını date'e çevir"""
        if not value:
            return None
        value = value.strip()
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y", "%Y%m%d"):
            try:
                return date.fromisoformat(value) if fmt == "%Y-%m-%d" else \
                    date(*[int(p) for p in __import__("re").split(r"[-/.]", value)][::-1]
                         if fmt in ("%d/%m/%Y", "%d.%m.%Y") else [
                        int(value[:4]), int(value[4:6]), int(value[6:8])
                    ])
            except Exception:
                continue
        return None

    @staticmethod
    def _parse_decimal(value: Optional[str]) -> Decimal:
        """String'den Decimal'e güvenli dönüşüm"""
        if not value:
            return Decimal("0")
        # Binlik ayraç olarak nokta kullanıyorsa temizle
        cleaned = value.strip().replace(" ", "").replace(",", ".")
        # '1.234.56' gibi hatalı formatları düzelt
        parts = cleaned.split(".")
        if len(parts) > 2:
            cleaned = "".join(parts[:-1]) + "." + parts[-1]
        try:
            return Decimal(cleaned)
        except InvalidOperation:
            logger.warning(f"[UBLParser] Decimal parse hatası: '{value}'")
            return Decimal("0")
