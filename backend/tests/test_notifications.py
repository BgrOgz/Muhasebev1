"""
Bildirim servisi ve onay workflow testleri
Çalıştır: pytest tests/test_notifications.py -v
"""

import pytest
from unittest.mock import MagicMock, patch

from app.services.notification_service import (
    NotificationService,
    _base_html,
    _risk_badge,
    _invoice_card,
)


# ── Test fixture ──────────────────────────────────────────────────────────────

SAMPLE_INVOICE = {
    "id": "00000000-0000-0000-0000-000000000001",
    "invoice_number": "2025-TEST-001",
    "supplier_name": "ABC Tekstil Ltd.",
    "total_amount": "5900.00",
    "currency": "TRY",
    "invoice_date": "2025-03-11",
    "category": "kumas",
    "risk_level": "low",
    "confidence": 0.95,
    "suggested_account": "7101",
    "notes": "Standart kumaş faturası.",
}


def make_service(smtp_enabled: bool = False) -> NotificationService:
    """SMTP kapalı (simüle) veya açık NotificationService döndür"""
    svc = NotificationService.__new__(NotificationService)
    svc.smtp_host = "smtp.test.com"
    svc.smtp_port = 587
    svc.smtp_user = "apikey"
    svc.smtp_pass = "fake-key" if smtp_enabled else ""
    svc.from_email = "noreply@test.com"
    svc.from_name = "Test Sistemi"
    svc.app_url = "http://localhost:3000"
    svc.enabled = smtp_enabled
    return svc


# ── HTML şablon testleri ──────────────────────────────────────────────────────

class TestHTMLTemplates:

    def test_base_html_contains_title(self):
        html = _base_html("Test Başlık", "<p>İçerik</p>")
        assert "Test Başlık" in html
        assert "E-Fatura Sistemi" in html
        assert "İçerik" in html

    def test_risk_badge_low(self):
        badge = _risk_badge("low")
        assert "badge-low" in badge
        assert "Düşük" in badge

    def test_risk_badge_medium(self):
        badge = _risk_badge("medium")
        assert "badge-medium" in badge
        assert "Orta" in badge

    def test_risk_badge_high(self):
        badge = _risk_badge("high")
        assert "badge-high" in badge
        assert "Yüksek" in badge

    def test_risk_badge_unknown_falls_back(self):
        badge = _risk_badge("bilinmeyen")
        assert "badge-medium" in badge  # default

    def test_invoice_card_contains_data(self):
        card = _invoice_card(SAMPLE_INVOICE)
        assert "2025-TEST-001" in card
        assert "ABC Tekstil Ltd." in card
        assert "5900.00" in card
        assert "kumas" in card
        assert "95%" in card  # confidence score

    def test_invoice_card_risk_badge_embedded(self):
        card = _invoice_card(SAMPLE_INVOICE)
        assert "badge-low" in card


# ── NotificationService (SMTP devre dışı = simüle) ───────────────────────────

class TestNotificationServiceDisabled:
    """SMTP_PASSWORD yok → e-postalar simüle edilir (log only), True döner"""

    def test_send_returns_true_when_disabled(self):
        svc = make_service(smtp_enabled=False)
        result = svc._send("test@example.com", "Konu", "<p>Test</p>")
        assert result is True

    def test_notify_classification_complete(self):
        svc = make_service()
        result = svc.notify_classification_complete(
            approver_email="approver@test.com",
            invoice_data=SAMPLE_INVOICE,
        )
        assert result is True

    def test_notify_approval_reminder(self):
        svc = make_service()
        result = svc.notify_approval_reminder(
            approver_email="approver@test.com",
            invoice_data=SAMPLE_INVOICE,
            reminder_count=2,
        )
        assert result is True

    def test_notify_first_approved(self):
        svc = make_service()
        result = svc.notify_first_approved(
            final_approver_email="boss@test.com",
            invoice_data=SAMPLE_INVOICE,
            first_approver_name="Muhasebe",
            notes="Onaylıyorum",
        )
        assert result is True

    def test_notify_first_rejected_multi(self):
        svc = make_service()
        # send_multi → None döner ama hata fırlatmamalı
        svc.notify_first_rejected(
            recipients=["a@test.com", "b@test.com"],
            invoice_data=SAMPLE_INVOICE,
            rejector_name="Muhasebe",
            rejection_notes="Tutar yanlış",
        )

    def test_notify_final_approved_multi(self):
        svc = make_service()
        svc.notify_final_approved(
            recipients=["a@test.com"],
            invoice_data=SAMPLE_INVOICE,
            approver_name="Patron",
        )

    def test_notify_final_rejected_multi(self):
        svc = make_service()
        svc.notify_final_rejected(
            recipients=["a@test.com"],
            invoice_data=SAMPLE_INVOICE,
            rejector_name="Patron",
            rejection_notes="Sahte fatura",
        )

    def test_send_multi_skips_empty(self):
        """Boş e-posta adresleri atlanmalı"""
        svc = make_service()
        sent = []

        def _capture_send(to, subject, html):
            sent.append(to)
            return True

        svc._send = _capture_send
        svc._send_multi(["valid@test.com", "", "  "], "Konu", "<p>x</p>")
        # Sadece geçerli adres gönderilmeli
        assert len(sent) == 1
        assert sent[0] == "valid@test.com"


# ── Approval reminder yardımcıları ────────────────────────────────────────────

class TestApprovalReminderHelpers:

    def test_get_reminder_info_empty(self):
        from app.services.approval_reminder import _get_reminder_info
        assert _get_reminder_info(None) == {}

    def test_get_reminder_info_no_classification(self):
        from app.services.approval_reminder import _get_reminder_info

        mock_clf = MagicMock()
        mock_clf.anomalies = []
        assert _get_reminder_info(mock_clf) == {}

    def test_get_reminder_info_found(self):
        from app.services.approval_reminder import _get_reminder_info

        mock_clf = MagicMock()
        mock_clf.anomalies = [
            {"type": "parse_error", "severity": "low"},
            {"type": "reminder_meta", "count": 2, "last_sent": "2025-01-01T00:00:00+00:00"},
        ]
        info = _get_reminder_info(mock_clf)
        assert info["count"] == 2

    def test_update_reminder_info_adds(self):
        from app.services.approval_reminder import _update_reminder_info

        mock_clf = MagicMock()
        mock_clf.anomalies = [{"type": "parse_error"}]
        _update_reminder_info(mock_clf, 1)

        anomalies = mock_clf.anomalies
        reminder_entries = [a for a in anomalies if a.get("type") == "reminder_meta"]
        assert len(reminder_entries) == 1
        assert reminder_entries[0]["count"] == 1
        assert "last_sent" in reminder_entries[0]

    def test_update_reminder_info_replaces(self):
        """Var olan reminder_meta güncellenip tekrar eklenmemeli"""
        from app.services.approval_reminder import _update_reminder_info

        mock_clf = MagicMock()
        mock_clf.anomalies = [
            {"type": "reminder_meta", "count": 1, "last_sent": "2025-01-01T00:00:00+00:00"}
        ]
        _update_reminder_info(mock_clf, 2)

        reminder_entries = [
            a for a in mock_clf.anomalies if a.get("type") == "reminder_meta"
        ]
        assert len(reminder_entries) == 1
        assert reminder_entries[0]["count"] == 2

    def test_update_reminder_info_none_classification(self):
        """None classification geçildiğinde hata fırlatmamalı"""
        from app.services.approval_reminder import _update_reminder_info
        _update_reminder_info(None, 1)  # Hata çıkmamalı

    def test_build_invoice_data_with_classification(self):
        from app.services.approval_reminder import _build_invoice_data

        mock_invoice = MagicMock()
        mock_invoice.id = "abc"
        mock_invoice.invoice_number = "2025-001"
        mock_invoice.supplier.name = "Test Tedarikçi"
        mock_invoice.total_amount = "1000.00"
        mock_invoice.currency = "TRY"
        mock_invoice.invoice_date = "2025-03-11"

        mock_clf = MagicMock()
        mock_clf.category = "iplik"
        mock_clf.risk_level = "high"
        mock_clf.confidence_score = 0.8
        mock_clf.suggested_account = "7102"
        mock_clf.ai_notes = "Test notu"

        data = _build_invoice_data(mock_invoice, mock_clf)
        assert data["category"] == "iplik"
        assert data["risk_level"] == "high"
        assert data["confidence"] == 0.8
        assert data["suggested_account"] == "7102"

    def test_build_invoice_data_without_classification(self):
        from app.services.approval_reminder import _build_invoice_data

        mock_invoice = MagicMock()
        mock_invoice.id = "xyz"
        mock_invoice.invoice_number = "2025-002"
        mock_invoice.supplier.name = "Diğer Tedarikçi"
        mock_invoice.total_amount = "2000.00"
        mock_invoice.currency = "TRY"
        mock_invoice.invoice_date = "2025-03-15"
        mock_invoice.category = "enerji"
        mock_invoice.risk_level = "medium"

        data = _build_invoice_data(mock_invoice, None)
        assert data["category"] == "enerji"
        assert data["confidence"] == 0.0
        assert data["suggested_account"] == "-"
