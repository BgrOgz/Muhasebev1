"""
Sınıflandırma servisi testleri — Claude API mock'lanır.
Çalıştır: pytest tests/test_classification.py -v
"""

import json
import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch

from app.services.classification_service import ClassificationService, TEXTILE_CATEGORIES


# ── Mock fatura nesnesi ───────────────────────────────────────────────────────

class MockSupplier:
    name = "ABC Tekstil Ltd."
    vat_number = "1234567890"


class MockInvoice:
    id = "00000000-0000-0000-0000-000000000001"
    invoice_number = "2025-TEST-001"
    invoice_date = "2025-03-11"
    amount = Decimal("5000.00")
    tax_amount = Decimal("900.00")
    total_amount = Decimal("5900.00")
    currency = "TRY"
    source_email = "supplier@test.com"
    ubl_xml = None
    supplier = MockSupplier()
    status = "processing"


# ── Parse testleri (DB gerektirmeyen) ─────────────────────────────────────────

class TestClassificationParsing:
    """_parse_claude_response metodunu doğrudan test eder"""

    def _make_service(self):
        svc = ClassificationService.__new__(ClassificationService)
        svc.db = None
        return svc

    def test_parse_valid_response(self):
        svc = self._make_service()
        raw = json.dumps({
            "category": "kumas",
            "risk_level": "low",
            "confidence": 0.95,
            "suggested_account": "7101",
            "payment_method": "havale",
            "anomalies": [],
            "notes": "Standart kumaş faturası."
        })
        result = svc._parse_claude_response(raw, MockInvoice())

        assert result["category"] == "kumas"
        assert result["risk_level"] == "low"
        assert result["confidence"] == 0.95
        assert result["suggested_account"] == "7101"
        assert result["payment_method"] == "havale"
        assert result["anomalies"] == []

    def test_parse_with_code_block(self):
        """Claude bazen ```json ... ``` içinde döner"""
        svc = self._make_service()
        raw = '```json\n{"category":"iplik","risk_level":"medium","confidence":0.8,"suggested_account":"7102","payment_method":"havale","anomalies":[],"notes":"test"}\n```'
        result = svc._parse_claude_response(raw, MockInvoice())
        assert result["category"] == "iplik"

    def test_parse_invalid_category_falls_back(self):
        """Bilinmeyen kategori → 'diger'"""
        svc = self._make_service()
        raw = json.dumps({
            "category": "bilinmeyen_kategori",
            "risk_level": "low",
            "confidence": 0.9,
            "suggested_account": "6990",
            "payment_method": "havale",
            "anomalies": [],
            "notes": ""
        })
        result = svc._parse_claude_response(raw, MockInvoice())
        assert result["category"] == "diger"

    def test_parse_invalid_risk_falls_back(self):
        """Geçersiz risk → 'medium'"""
        svc = self._make_service()
        raw = json.dumps({
            "category": "kumas",
            "risk_level": "very_high",
            "confidence": 0.7,
            "suggested_account": "7101",
            "payment_method": "nakit",
            "anomalies": [],
            "notes": ""
        })
        result = svc._parse_claude_response(raw, MockInvoice())
        assert result["risk_level"] == "medium"

    def test_parse_confidence_clamped(self):
        """Güven değeri 0–1 aralığında tutulur"""
        svc = self._make_service()
        raw = json.dumps({
            "category": "kumas",
            "risk_level": "low",
            "confidence": 1.5,  # 1'den büyük
            "suggested_account": "7101",
            "payment_method": "havale",
            "anomalies": [],
            "notes": ""
        })
        result = svc._parse_claude_response(raw, MockInvoice())
        assert result["confidence"] == 1.0

    def test_parse_anomaly_list(self):
        """Anomali listesi doğru parse edilmeli"""
        svc = self._make_service()
        anomalies = [
            {"type": "price_deviation", "severity": "medium",
             "message": "Fiyat ortalamanin %20 ustunde"}
        ]
        raw = json.dumps({
            "category": "makine_ekipman",
            "risk_level": "medium",
            "confidence": 0.75,
            "suggested_account": "2530",
            "payment_method": "havale",
            "anomalies": anomalies,
            "notes": "Fiyat sapması tespit edildi."
        })
        result = svc._parse_claude_response(raw, MockInvoice())
        assert len(result["anomalies"]) == 1
        assert result["anomalies"][0]["type"] == "price_deviation"

    def test_fallback_on_no_json(self):
        """JSON olmayan yanıt → güvenli fallback"""
        svc = self._make_service()
        result = svc._parse_claude_response(
            "Anlayamadim, lutfen tekrar gonderiniz.", MockInvoice()
        )
        assert result["category"] == "diger"
        assert result["risk_level"] == "medium"
        assert result["confidence"] == 0.3
        assert len(result["anomalies"]) == 1
        assert result["anomalies"][0]["type"] == "parse_error"

    def test_all_categories_valid(self):
        """Tüm kategoriler geçerli"""
        svc = self._make_service()
        for cat in TEXTILE_CATEGORIES:
            raw = json.dumps({
                "category": cat,
                "risk_level": "low",
                "confidence": 0.9,
                "suggested_account": "7101",
                "payment_method": "havale",
                "anomalies": [],
                "notes": ""
            })
            result = svc._parse_claude_response(raw, MockInvoice())
            assert result["category"] == cat, f"Kategori başarısız: {cat}"
