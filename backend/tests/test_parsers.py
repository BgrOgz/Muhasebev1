"""
Parser birim testleri
Çalıştır: pytest tests/test_parsers.py -v
"""

import pytest
from decimal import Decimal
from datetime import date

from app.parsers.ubl_parser import UBLParser
from app.parsers.pdf_parser import PDFParser


# ── Test fixture'ları ─────────────────────────────────────────────────────────

MINIMAL_UBL_XML = """<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
         xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
         xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
    <cbc:ID>2025-001234</cbc:ID>
    <cbc:IssueDate>2025-03-11</cbc:IssueDate>

    <cac:AccountingSupplierParty>
        <cac:Party>
            <cac:PartyName>
                <cbc:Name>ABC Tekstil Ltd.</cbc:Name>
            </cac:PartyName>
            <cac:PartyTaxScheme>
                <cbc:CompanyID>1234567890</cbc:CompanyID>
            </cac:PartyTaxScheme>
        </cac:Party>
    </cac:AccountingSupplierParty>

    <cac:TaxTotal>
        <cbc:TaxAmount currencyID="TRY">900.00</cbc:TaxAmount>
    </cac:TaxTotal>

    <cac:LegalMonetaryTotal>
        <cbc:TaxExclusiveAmount currencyID="TRY">5000.00</cbc:TaxExclusiveAmount>
        <cbc:PayableAmount currencyID="TRY">5900.00</cbc:PayableAmount>
    </cac:LegalMonetaryTotal>

    <cac:InvoiceLine>
        <cbc:InvoicedQuantity unitCode="MT">100</cbc:InvoicedQuantity>
        <cbc:LineExtensionAmount currencyID="TRY">5000.00</cbc:LineExtensionAmount>
        <cac:Item>
            <cbc:Name>Premium Pamuk Kumas</cbc:Name>
        </cac:Item>
        <cac:Price>
            <cbc:PriceAmount currencyID="TRY">50.00</cbc:PriceAmount>
        </cac:Price>
    </cac:InvoiceLine>
</Invoice>
""".encode("utf-8")

MINIMAL_PDF_TEXT = """
                    E-FATURA

Fatura No    : 2025-005678
Fatura Tarihi: 15/03/2025
Vade Tarihi  : 15/04/2025

Satıcı Unvanı: XYZ Tekstil A.Ş.
Vergi No     : 9876543210

Ürün Adı          Miktar   Birim Fiyat    Tutar
Premium İplik      50 KG      120,00     6.000,00

KDV Matrah        : 6.000,00 TRY
KDV               : 1.080,00 TRY
Genel Toplam      : 7.080,00 TRY
"""


# ── UBL-TR XML testleri ───────────────────────────────────────────────────────

class TestUBLParser:

    def test_parse_minimal_xml(self):
        parser = UBLParser(MINIMAL_UBL_XML)
        result = parser.parse()

        assert result["invoice_number"] == "2025-001234"
        assert result["invoice_date"] == date(2025, 3, 11)
        assert result["amount"] == Decimal("5000.00")
        assert result["tax_amount"] == Decimal("900.00")
        assert result["total_amount"] == Decimal("5900.00")
        assert result["currency"] == "TRY"
        assert result["supplier_name"] == "ABC Tekstil Ltd."
        assert result["supplier_vat"] == "1234567890"
        assert result["source_format"] == "xml"

    def test_parse_line_items(self):
        parser = UBLParser(MINIMAL_UBL_XML)
        result = parser.parse()

        assert len(result["line_items"]) == 1
        item = result["line_items"][0]
        assert item["description"] == "Premium Pamuk Kumas"
        assert item["quantity"] == 100.0
        assert item["unit_price"] == 50.0

    def test_ubl_xml_stored(self):
        parser = UBLParser(MINIMAL_UBL_XML)
        result = parser.parse()
        assert result["ubl_xml"] is not None
        assert isinstance(result["ubl_xml"], dict)

    def test_invalid_xml_raises(self):
        with pytest.raises(ValueError, match="Geçersiz XML"):
            UBLParser(b"bu bir xml degildir!!!").parse()

    def test_missing_invoice_id_raises(self):
        xml_without_id = b"""<?xml version="1.0"?>
        <Invoice xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
            <cbc:IssueDate>2025-03-11</cbc:IssueDate>
        </Invoice>"""
        with pytest.raises(ValueError, match="Fatura numarası"):
            UBLParser(xml_without_id).parse()


# ── PDF testleri ──────────────────────────────────────────────────────────────

class TestPDFParser:

    def test_parse_decimal_turkish_format(self):
        """Türk sayı formatı: 1.234,56 → 1234.56"""
        assert PDFParser._parse_decimal("1.234,56") == Decimal("1234.56")
        assert PDFParser._parse_decimal("7.080,00") == Decimal("7080.00")
        assert PDFParser._parse_decimal("6.000,00") == Decimal("6000.00")
        assert PDFParser._parse_decimal("") == Decimal("0")

    def test_parse_date_formats(self):
        assert PDFParser._parse_date("15/03/2025") == date(2025, 3, 15)
        assert PDFParser._parse_date("15.03.2025") == date(2025, 3, 15)
        assert PDFParser._parse_date("2025-03-15") == date(2025, 3, 15)
        assert PDFParser._parse_date(None) is None

    def test_extract_from_text(self):
        """Metin çıkarımı testi (gerçek PDF olmadan)"""
        parser = PDFParser(b"fake_content")
        result = parser._extract_from_text(MINIMAL_PDF_TEXT)

        assert result["invoice_number"] == "2025-005678"
        assert result["invoice_date"] == date(2025, 3, 15)
        assert result["due_date"] == date(2025, 4, 15)
        assert result["total_amount"] == Decimal("7080.00")
        assert result["tax_amount"] == Decimal("1080.00")
        assert result["amount"] == Decimal("6000.00")
        assert "XYZ Tekstil" in result["supplier_name"]
        assert result["supplier_vat"] == "9876543210"

    def test_embedded_xml_detection(self):
        """Gömülü XML bulunduğunda UBL parser'a devredilmeli"""
        xml_text = MINIMAL_UBL_XML.decode("utf-8")
        found = PDFParser._find_embedded_xml(xml_text)
        assert found is not None

    def test_no_embedded_xml(self):
        assert PDFParser._find_embedded_xml("sadece metin, xml yok") is None
