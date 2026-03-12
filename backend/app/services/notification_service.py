"""
Bildirim Servisi — SendGrid E-posta
────────────────────────────────────────────────────────────────────────
Onay sürecindeki her aşamada ilgili kişilere HTML e-posta gönderir.

Gönderilen bildirimler:
  1. classification_complete  → Birinci onaylayan: "Onaylanacak fatura var"
  2. approval_reminder        → Onaylayan: "Hatırlatma: Bekleyen fatura"
  3. first_approved           → Son onaylayan: "İlk onay verildi, sıra sizde"
  4. first_rejected           → Patron + muhasebeçi: "Fatura reddedildi"
  5. final_approved           → Tedarikçi + muhasebe: "Fatura onaylandı"
  6. final_rejected           → Patron + tedarikçi: "Fatura kesin reddedildi"
"""

import smtplib
import ssl
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from app.utils.logger import logger

# ── Lazy config yardımcıları ──────────────────────────────────────────────────

def _settings():
    from app.config import settings
    return settings


# ── HTML Şablonları ───────────────────────────────────────────────────────────

def _base_html(title: str, body_html: str) -> str:
    """Tüm e-postalar için ortak HTML şablonu"""
    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{title}</title>
  <style>
    body {{ font-family: Arial, sans-serif; background: #f4f4f4; margin: 0; padding: 20px; }}
    .container {{ max-width: 600px; margin: 0 auto; background: #fff;
                 border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,.1); overflow: hidden; }}
    .header {{ background: #1a56db; color: #fff; padding: 24px 32px; }}
    .header h1 {{ margin: 0; font-size: 20px; }}
    .header p {{ margin: 4px 0 0; font-size: 13px; opacity: .85; }}
    .body {{ padding: 32px; color: #333; }}
    .invoice-card {{ background: #f8fafc; border: 1px solid #e2e8f0;
                    border-radius: 6px; padding: 16px; margin: 16px 0; }}
    .invoice-card table {{ width: 100%; border-collapse: collapse; }}
    .invoice-card td {{ padding: 6px 0; font-size: 14px; }}
    .invoice-card td:first-child {{ color: #666; width: 45%; }}
    .badge {{ display: inline-block; padding: 3px 10px; border-radius: 12px;
             font-size: 12px; font-weight: bold; }}
    .badge-low {{ background: #d1fae5; color: #065f46; }}
    .badge-medium {{ background: #fef3c7; color: #92400e; }}
    .badge-high {{ background: #fee2e2; color: #991b1b; }}
    .btn {{ display: inline-block; padding: 12px 24px; background: #1a56db;
           color: #fff; text-decoration: none; border-radius: 6px;
           font-weight: bold; margin-top: 20px; }}
    .btn-green {{ background: #059669; }}
    .btn-red {{ background: #dc2626; }}
    .footer {{ background: #f8fafc; padding: 16px 32px;
              font-size: 12px; color: #888; border-top: 1px solid #e2e8f0; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>📄 E-Fatura Sistemi</h1>
      <p>Tekstil Muhasebe Otomasyonu</p>
    </div>
    <div class="body">
      {body_html}
    </div>
    <div class="footer">
      Bu e-posta otomatik olarak gönderilmiştir. Lütfen yanıtlamayınız.<br/>
      © {datetime.now().year} Tekstil E-Fatura Sistemi
    </div>
  </div>
</body>
</html>"""


def _risk_badge(risk_level: str) -> str:
    css = {"low": "badge-low", "medium": "badge-medium", "high": "badge-high"}.get(
        risk_level, "badge-medium"
    )
    labels = {"low": "🟢 Düşük", "medium": "🟡 Orta", "high": "🔴 Yüksek"}
    label = labels.get(risk_level, risk_level)
    return f'<span class="badge {css}">{label}</span>'


def _invoice_card(invoice_data: dict) -> str:
    risk = invoice_data.get("risk_level", "medium")
    return f"""
    <div class="invoice-card">
      <table>
        <tr><td>Fatura No</td><td><strong>{invoice_data.get('invoice_number', '-')}</strong></td></tr>
        <tr><td>Tedarikçi</td><td>{invoice_data.get('supplier_name', '-')}</td></tr>
        <tr><td>Tutar</td>
            <td><strong>{invoice_data.get('total_amount', '-')} {invoice_data.get('currency', 'TRY')}</strong></td></tr>
        <tr><td>Kategori</td><td>{invoice_data.get('category', '-')}</td></tr>
        <tr><td>Risk Seviyesi</td><td>{_risk_badge(risk)}</td></tr>
        <tr><td>Güven Skoru</td>
            <td>{float(invoice_data.get('confidence', 0)) * 100:.0f}%</td></tr>
        <tr><td>Tarih</td><td>{invoice_data.get('invoice_date', '-')}</td></tr>
      </table>
    </div>"""


# ── E-posta gönderici ─────────────────────────────────────────────────────────

class NotificationService:
    """
    SMTP (veya SendGrid SMTP relay) üzerinden HTML e-posta gönderir.
    .env'deki SMTP_* değişkenlerini kullanır. SMTP yapılandırılmamışsa
    sadece loglar (sessiz mod).
    """

    def __init__(self):
        s = _settings()
        self.smtp_host = getattr(s, "SMTP_HOST", "smtp.sendgrid.net")
        self.smtp_port = int(getattr(s, "SMTP_PORT", 587))
        self.smtp_user = getattr(s, "SMTP_USER", "apikey")
        self.smtp_pass = getattr(s, "SMTP_PASSWORD", "")
        self.from_email = getattr(s, "FROM_EMAIL", "noreply@tekstil-fatura.com")
        self.from_name = getattr(s, "FROM_NAME", "E-Fatura Sistemi")
        self.app_url = getattr(s, "APP_URL", "http://localhost:3000")
        self.enabled = bool(self.smtp_pass)  # SMTP_PASSWORD yoksa devre dışı

    # ── Genel gönderici ───────────────────────────────────────────────────────

    def _send(self, to: str, subject: str, html: str) -> bool:
        """
        E-posta gönder. Başarılıysa True, başarısızsa False.
        SMTP yapılandırılmamışsa yalnızca loglar.
        """
        if not self.enabled:
            logger.debug(
                f"[Notification] SMTP yapılandırılmamış — e-posta simüle edildi\n"
                f"  TO: {to}\n  SUBJECT: {subject}"
            )
            return True  # Test/dev ortamı için başarılı say

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{self.from_name} <{self.from_email}>"
        msg["To"] = to
        msg.attach(MIMEText(html, "html", "utf-8"))

        try:
            context = ssl.create_default_context()
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10) as server:
                server.ehlo()
                server.starttls(context=context)
                server.login(self.smtp_user, self.smtp_pass)
                server.sendmail(self.from_email, to, msg.as_string())
            logger.info(f"[Notification] ✅ E-posta gönderildi → {to} | {subject}")
            return True
        except Exception as exc:
            logger.error(f"[Notification] ❌ E-posta gönderilemedi → {to}: {exc}")
            return False

    def _send_multi(self, recipients: list[str], subject: str, html: str) -> None:
        """Birden fazla alıcıya gönderir (boş / sadece boşluk içerenleri atlar)"""
        for email in recipients:
            if email and email.strip():
                self._send(email, subject, html)

    # ── 1. Sınıflandırma tamamlandı ───────────────────────────────────────────

    def notify_classification_complete(
        self,
        approver_email: str,
        invoice_data: dict,
    ) -> bool:
        """Birinci onaylayan: "Onaylanacak yeni fatura var" """
        subject = (
            f"[Fatura Sistemi] Yeni Fatura Onay Bekliyor — "
            f"{invoice_data.get('invoice_number', '?')}"
        )
        review_url = f"{self.app_url}/approvals"
        body = f"""
        <h2>Yeni Fatura Onay Bekliyor 📋</h2>
        <p>AI sınıflandırması tamamlandı. Fatura <strong>birinci onayınızı</strong> bekliyor.</p>
        {_invoice_card(invoice_data)}
        <p>
          <strong>AI Notu:</strong><br/>
          <em>{invoice_data.get('notes', '-')}</em>
        </p>
        <a href="{review_url}" class="btn">Faturayı İncele ve Onayla →</a>
        """
        html = _base_html(subject, body)
        return self._send(approver_email, subject, html)

    # ── 2. Onay hatırlatması ──────────────────────────────────────────────────

    def notify_approval_reminder(
        self,
        approver_email: str,
        invoice_data: dict,
        reminder_count: int = 1,
    ) -> bool:
        """Bekleyen fatura için hatırlatma (max 3 kez)"""
        subject = (
            f"[Hatırlatma #{reminder_count}] Onay Bekleyen Fatura — "
            f"{invoice_data.get('invoice_number', '?')}"
        )
        review_url = f"{self.app_url}/approvals"
        body = f"""
        <h2>Onay Bekleyen Fatura Hatırlatması ⏰</h2>
        <p>Aşağıdaki fatura <strong>{reminder_count}. kez</strong> hatırlatılmaktadır.
           Lütfen en kısa sürede inceleyin.</p>
        {_invoice_card(invoice_data)}
        <a href="{review_url}" class="btn">Hemen İncele →</a>
        """
        html = _base_html(subject, body)
        return self._send(approver_email, subject, html)

    # ── 3. Birinci onay verildi ───────────────────────────────────────────────

    def notify_first_approved(
        self,
        final_approver_email: str,
        invoice_data: dict,
        first_approver_name: str = "Birinci Onaylayan",
        notes: Optional[str] = None,
    ) -> bool:
        """Son onaylayan: "İlk onay verildi, sıra sizde" """
        subject = (
            f"[Fatura Sistemi] Nihai Onay Bekliyor — "
            f"{invoice_data.get('invoice_number', '?')}"
        )
        review_url = f"{self.app_url}/approvals"
        notes_section = (
            f"<p><strong>Not:</strong> <em>{notes}</em></p>" if notes else ""
        )
        body = f"""
        <h2>Nihai Onayınızı Bekleyen Fatura 🏁</h2>
        <p>
          <strong>{first_approver_name}</strong> tarafından ilk onay verildi.
          Fatura artık <strong>nihai onayınızı</strong> bekliyor.
        </p>
        {_invoice_card(invoice_data)}
        {notes_section}
        <a href="{review_url}" class="btn btn-green">Nihai Kararı Ver →</a>
        """
        html = _base_html(subject, body)
        return self._send(final_approver_email, subject, html)

    # ── 4. Birinci onaylayan reddetti ─────────────────────────────────────────

    def notify_first_rejected(
        self,
        recipients: list[str],
        invoice_data: dict,
        rejector_name: str = "Birinci Onaylayan",
        rejection_notes: Optional[str] = None,
    ) -> None:
        """Patron + muhasebe bildirimi: fatura birinci onayda reddedildi"""
        subject = (
            f"[Fatura Sistemi] Fatura Reddedildi — "
            f"{invoice_data.get('invoice_number', '?')}"
        )
        notes_section = (
            f'<p><strong>Red Sebebi:</strong> <em style="color:#dc2626">{rejection_notes}</em></p>'
            if rejection_notes
            else ""
        )
        body = f"""
        <h2>Fatura Reddedildi ❌</h2>
        <p>
          <strong>{rejector_name}</strong> aşağıdaki faturayı reddetti.
          Fatura tekrar gözden geçirilmek üzere <strong>İADE</strong> statüsüne alındı.
        </p>
        {_invoice_card(invoice_data)}
        {notes_section}
        <p>Gerekirse faturayı düzelterek yeniden işleme alabilirsiniz.</p>
        <a href="{self.app_url}/invoices/{invoice_data.get('id', '')}" class="btn btn-red">
          Faturayı Görüntüle →
        </a>
        """
        html = _base_html(subject, body)
        self._send_multi(recipients, subject, html)

    # ── 5. Nihai onay verildi ─────────────────────────────────────────────────

    def notify_final_approved(
        self,
        recipients: list[str],
        invoice_data: dict,
        approver_name: str = "Patron",
        notes: Optional[str] = None,
    ) -> None:
        """Fatura tamamen onaylandı — muhasebe + tedarikçi bildirimi"""
        subject = (
            f"[Fatura Sistemi] ✅ Fatura Onaylandı — "
            f"{invoice_data.get('invoice_number', '?')}"
        )
        notes_section = (
            f"<p><strong>Not:</strong> <em>{notes}</em></p>" if notes else ""
        )
        body = f"""
        <h2>Fatura Onaylandı ✅</h2>
        <p>
          <strong>{approver_name}</strong> nihai onayı verdi.
          Fatura muhasebe sistemine kaydedilmeye hazır.
        </p>
        {_invoice_card(invoice_data)}
        {notes_section}
        <p><strong>Önerilen Hesap Kodu:</strong>
           {invoice_data.get('suggested_account', '-')}</p>
        <a href="{self.app_url}/invoices/{invoice_data.get('id', '')}" class="btn btn-green">
          Fatura Detayı →
        </a>
        """
        html = _base_html(subject, body)
        self._send_multi(recipients, subject, html)

    # ── 6. Nihai red ──────────────────────────────────────────────────────────

    def notify_final_rejected(
        self,
        recipients: list[str],
        invoice_data: dict,
        rejector_name: str = "Patron",
        rejection_notes: Optional[str] = None,
    ) -> None:
        """Fatura kesin reddedildi — patron + tedarikçi bildirimi"""
        subject = (
            f"[Fatura Sistemi] ⛔ Fatura Kesin Reddedildi — "
            f"{invoice_data.get('invoice_number', '?')}"
        )
        notes_section = (
            f'<p><strong>Red Gerekçesi:</strong> <em style="color:#dc2626">{rejection_notes}</em></p>'
            if rejection_notes
            else ""
        )
        body = f"""
        <h2>Fatura Kesin Olarak Reddedildi ⛔</h2>
        <p>
          <strong>{rejector_name}</strong> aşağıdaki faturayı <strong>kesin olarak reddetti</strong>.
          Fatura sisteme kaydedilmeyecektir.
        </p>
        {_invoice_card(invoice_data)}
        {notes_section}
        <p>Herhangi bir sorunuz varsa muhasebe departmanıyla iletişime geçiniz.</p>
        """
        html = _base_html(subject, body)
        self._send_multi(recipients, subject, html)


# ── Singleton ─────────────────────────────────────────────────────────────────

notification_service = NotificationService()
