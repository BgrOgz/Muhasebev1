"""
Gmail IMAP E-Fatura Tarama Servisi
────────────────────────────────────
Her 5 dakikada bir INBOX taranır.
XML veya PDF eki olan mailler işleme alınır.
İşlenen mailler "Processed" label'ı ile işaretlenir → tekrar taranmaz.
"""

import email
import imaplib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.header import decode_header
from typing import Optional

from app.config import settings
from app.utils.logger import logger


# ── Veri yapıları ─────────────────────────────────────────────────────────────

@dataclass
class EmailAttachment:
    filename: str
    content: bytes
    content_type: str
    size_bytes: int


@dataclass
class InvoiceEmail:
    email_id: bytes           # Gmail internal ID
    from_address: str
    subject: str
    date_str: str
    attachments: list[EmailAttachment] = field(default_factory=list)


# ── Ana servis sınıfı ─────────────────────────────────────────────────────────

class GmailService:
    """
    Gmail IMAP bağlantısını yönetir.
    Kullanım:
        with GmailService() as svc:
            emails = svc.get_unread_invoice_emails()
    """

    ALLOWED_EXTENSIONS = {".xml", ".pdf", ".xls", ".xlsx"}
    PROCESSED_LABEL = "Processed"

    def __init__(self):
        self._mail: Optional[imaplib.IMAP4_SSL] = None

    # ── Context manager ───────────────────────────────────────────────────────

    def __enter__(self) -> "GmailService":
        self.connect()
        return self

    def __exit__(self, *_):
        self.close()

    # ── Bağlantı ─────────────────────────────────────────────────────────────

    def connect(self) -> None:
        """Gmail IMAP'a SSL ile bağlan ve giriş yap"""
        try:
            self._mail = imaplib.IMAP4_SSL(
                settings.GMAIL_IMAP_SERVER,
                settings.GMAIL_IMAP_PORT,
            )
            self._mail.login(
                settings.GMAIL_SERVICE_EMAIL,
                settings.GMAIL_APP_PASSWORD,
            )
            logger.info(f"Gmail bağlantısı kuruldu: {settings.GMAIL_SERVICE_EMAIL}")
        except imaplib.IMAP4.error as exc:
            logger.error(f"Gmail bağlantı hatası: {exc}")
            raise ConnectionError(f"Gmail'e bağlanılamadı: {exc}") from exc

    def close(self) -> None:
        """Bağlantıyı güvenli biçimde kapat"""
        if self._mail:
            try:
                self._mail.close()
                self._mail.logout()
            except Exception:
                pass
            finally:
                self._mail = None
        logger.debug("Gmail bağlantısı kapatıldı.")

    # ── E-posta tarama ────────────────────────────────────────────────────────

    def get_unread_invoice_emails(self) -> list[InvoiceEmail]:
        """
        INBOX'taki okunmamış mailleri tara.
        Sadece desteklenen eki olan mailleri döndür.
        """
        if not self._mail:
            raise RuntimeError("Önce connect() çağırın.")

        self._mail.select("INBOX")
        status, data = self._mail.search(None, "UNSEEN")

        if status != "OK":
            logger.error("Gmail INBOX araması başarısız.")
            return []

        email_ids = data[0].split()
        logger.info(f"Okunmamış mail sayısı: {len(email_ids)}")

        results: list[InvoiceEmail] = []

        for eid in email_ids:
            try:
                invoice_email = self._parse_email(eid)
                if invoice_email and invoice_email.attachments:
                    results.append(invoice_email)
            except Exception as exc:
                logger.warning(f"Mail {eid} işlenemedi: {exc}")
                continue

        logger.info(f"Fatura eki bulunan mail: {len(results)}")
        return results

    def _parse_email(self, email_id: bytes) -> Optional[InvoiceEmail]:
        """Tek bir maili parse ederek InvoiceEmail döndür"""
        status, msg_data = self._mail.fetch(email_id, "(RFC822)")
        if status != "OK":
            return None

        raw = msg_data[0][1]
        msg = email.message_from_bytes(raw)

        from_addr = self._decode_header_value(msg.get("From", ""))
        subject = self._decode_header_value(msg.get("Subject", "(konu yok)"))
        date_str = msg.get("Date", "")

        attachments = self._extract_attachments(msg)

        if not attachments:
            return None  # Ek yoksa atla

        return InvoiceEmail(
            email_id=email_id,
            from_address=from_addr,
            subject=subject,
            date_str=date_str,
            attachments=attachments,
        )

    def _extract_attachments(self, msg: email.message.Message) -> list[EmailAttachment]:
        """Maildeki kabul edilen ekleri çıkar (attachment + inline + filename olan her bölüm)"""
        attachments = []

        for part in msg.walk():
            # Multipart container'ları atla
            if part.get_content_maintype() == "multipart":
                continue

            filename = part.get_filename()
            content_disp = part.get_content_disposition() or ""

            # Dosya adı olan veya attachment/inline olarak işaretlenmiş bölümleri al
            if not filename and "attachment" not in content_disp:
                continue
            if not filename:
                continue

            filename = self._decode_header_value(filename)
            ext = self._get_extension(filename)

            if ext not in self.ALLOWED_EXTENSIONS:
                logger.debug(f"Desteklenmeyen uzantı atlandı: {filename}")
                continue

            try:
                content = part.get_payload(decode=True)
                if not content:
                    continue

                # Dosya boyutu kontrolü (25 MB)
                if len(content) > settings.max_file_size_bytes:
                    logger.warning(
                        f"Dosya boyutu limitini aşıyor: {filename} "
                        f"({len(content) // 1024 // 1024} MB)"
                    )
                    continue

                attachments.append(
                    EmailAttachment(
                        filename=filename,
                        content=content,
                        content_type=part.get_content_type(),
                        size_bytes=len(content),
                    )
                )
                logger.debug(f"Ek alındı: {filename} ({len(content)} byte)")

            except Exception as exc:
                logger.error(f"Ek çıkarma hatası ({filename}): {exc}")

        return attachments

    # ── Mail işaretleme ───────────────────────────────────────────────────────

    def mark_as_processed(self, email_id: bytes) -> bool:
        """
        Maili 'Okundu' olarak işaretle ve 'Processed' label'ı ekle.
        Böylece bir sonraki taramada tekrar alınmaz.
        """
        try:
            # Okundu olarak işaretle
            self._mail.store(email_id, "+FLAGS", "\\Seen")

            # Gmail label ekle (API üzerinden)
            # Not: IMAP ile label eklemek Gmail'e özgü bir komuttur
            self._mail.store(email_id, "+X-GM-LABELS", self.PROCESSED_LABEL)
            logger.debug(f"Mail {email_id} 'Processed' olarak işaretlendi.")
            return True
        except Exception as exc:
            logger.error(f"Mail işaretlenemedi ({email_id}): {exc}")
            return False

    def move_to_folder(self, email_id: bytes, folder: str = "Processed") -> bool:
        """Maili belirtilen klasöre taşı (IMAP COPY + DELETE)"""
        try:
            # Hedef klasörü oluştur (yoksa)
            self._mail.create(folder)
        except Exception:
            pass  # Zaten varsa hata verir, görmezden gel

        try:
            self._mail.copy(email_id, folder)
            self._mail.store(email_id, "+FLAGS", "\\Deleted")
            self._mail.expunge()
            return True
        except Exception as exc:
            logger.error(f"Mail taşıma hatası: {exc}")
            return False

    # ── Hata bildirimi ────────────────────────────────────────────────────────

    def send_error_notification(self, to_email: str, error_msg: str) -> bool:
        """
        Supplier'a SMTP ile hata bildirimi gönder.
        (İleride SendGrid servisine devredilecek)
        """
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        from app.utils.validators import validate_email_address

        try:
            # E-posta adresini doğrula (header injection saldırılarını önlemek için)
            to_email = validate_email_address(to_email)

            msg = MIMEMultipart()
            msg["Subject"] = "E-Fatura İşleme Hatası"
            msg["From"] = settings.GMAIL_SERVICE_EMAIL
            msg["To"] = to_email

            body = MIMEText(
                f"""Sayın Tedarikçi,

Gönderdiğiniz e-fatura işlenirken bir sorun oluştu:

  {error_msg}

Lütfen faturayı kontrol edip tekrar gönderin veya destek ekibimizle iletişime geçin.

Saygılarımızla,
Fatura Otomasyon Sistemi
""",
                "plain",
                "utf-8",
            )
            msg.attach(body)

            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
                smtp.login(settings.GMAIL_SERVICE_EMAIL, settings.GMAIL_APP_PASSWORD)
                smtp.sendmail(settings.GMAIL_SERVICE_EMAIL, [to_email], msg.as_string())

            logger.info(f"Hata bildirimi gönderildi → {to_email}")
            return True

        except ValueError as exc:
            logger.error(f"Geçersiz e-posta adresi: {exc}")
            return False
        except Exception as exc:
            logger.error(f"Hata bildirimi gönderilemedi: {exc}")
            return False

    # ── Yardımcılar ───────────────────────────────────────────────────────────

    @staticmethod
    def _decode_header_value(value: str) -> str:
        """E-posta başlıklarındaki RFC2047 encoding'i çöz (UTF-8, latin-1 vb.)"""
        decoded_parts = decode_header(value)
        result = []
        for part, charset in decoded_parts:
            if isinstance(part, bytes):
                result.append(part.decode(charset or "utf-8", errors="replace"))
            else:
                result.append(part)
        return "".join(result)

    @staticmethod
    def _get_extension(filename: str) -> str:
        """Dosya uzantısını küçük harfle döndür"""
        return "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    # ── Rate limiter ──────────────────────────────────────────────────────────

    @staticmethod
    def extract_email_address(from_header: str) -> str:
        """'Ad Soyad <mail@domain.com>' formatından sadece adresi çıkar"""
        match = re.search(r"<(.+?)>", from_header)
        return match.group(1).strip() if match else from_header.strip()
