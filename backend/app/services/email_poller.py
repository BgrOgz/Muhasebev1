"""
Email Poller — APScheduler ile periyodik Gmail tarama
────────────────────────────────────────────────────────
Her GMAIL_POLL_INTERVAL_MINUTES dakikada bir çalışır.
Bulunan her eki invoice_service'e iletir.
"""

from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings
from app.services.email_service import GmailService
from app.services.email_rate_limiter import rate_limiter
from app.utils.logger import logger

# Scheduler singleton
_scheduler = None  # Optional[AsyncIOScheduler]


async def _poll_emails() -> None:
    """
    Tek bir polling döngüsü.
    APScheduler tarafından periyodik olarak çağrılır.
    """
    # Gmail yapılandırılmamışsa atla (dev modu)
    if not settings.GMAIL_SERVICE_EMAIL or settings.GMAIL_SERVICE_EMAIL == "dev@test.com":
        logger.debug("📧 Gmail yapılandırılmamış, email taraması atlandı (dev modu).")
        return

    logger.info("📧 Email taraması başlıyor...")

    # Veritabanı session'ı burada lazım — circular import önlemek için lazy import
    from app.database import AsyncSessionLocal
    from app.services.invoice_processor import InvoiceProcessor

    try:
        with GmailService() as gmail:
            invoice_emails = gmail.get_unread_invoice_emails()

            if not invoice_emails:
                logger.info("Yeni fatura maili bulunamadı.")
                return

            async with AsyncSessionLocal() as db:
                processor = InvoiceProcessor(db)

                for inv_email in invoice_emails:
                    supplier_email = GmailService.extract_email_address(
                        inv_email.from_address
                    )

                    # Rate limit kontrolü
                    if not rate_limiter.is_allowed(supplier_email):
                        logger.warning(
                            f"Rate limit: {supplier_email} atlandı."
                        )
                        continue

                    all_ok = True

                    for attachment in inv_email.attachments:
                        logger.info(
                            f"  İşleniyor: {attachment.filename} "
                            f"← {supplier_email}"
                        )
                        try:
                            result = await processor.process(
                                attachment=attachment,
                                from_email=supplier_email,
                                email_subject=inv_email.subject,
                                email_date=inv_email.date_str,
                                email_id=str(inv_email.email_id),
                            )

                            if result["success"]:
                                logger.info(
                                    f"  ✅ Fatura işlendi: {result.get('invoice_id')}"
                                )
                            else:
                                all_ok = False
                                logger.error(
                                    f"  ❌ İşleme hatası: {result.get('error')}"
                                )
                                # Supplier'a hata bildirimi gönder
                                gmail.send_error_notification(
                                    supplier_email,
                                    result.get("error", "Bilinmeyen hata"),
                                )

                        except Exception as exc:
                            all_ok = False
                            logger.exception(
                                f"  ❌ Beklenmeyen hata ({attachment.filename}): {exc}"
                            )

                    # Tüm ekler başarılıysa maili işaretle
                    if all_ok:
                        gmail.mark_as_processed(inv_email.email_id)
                    else:
                        logger.warning(
                            f"Mail kısmen başarısız, işaretlenmedi: "
                            f"{inv_email.subject}"
                        )

                await db.commit()

    except ConnectionError as exc:
        logger.error(f"Gmail bağlantısı kurulamadı: {exc}")
    except Exception as exc:
        logger.exception(f"Email polling beklenmeyen hata: {exc}")

    logger.info("📧 Email taraması tamamlandı.")


async def _send_approval_reminders() -> None:
    """Bekleyen onaylar için hatırlatma e-postası gönder (saatlik)"""
    from app.database import AsyncSessionLocal
    from app.services.approval_reminder import send_pending_reminders

    try:
        async with AsyncSessionLocal() as db:
            count = await send_pending_reminders(db)
            await db.commit()
            if count:
                logger.info(f"[Reminder] {count} hatırlatma gönderildi.")
    except Exception as exc:
        logger.exception(f"[Reminder] Hatırlatma hatası: {exc}")


# ── Scheduler yönetimi ────────────────────────────────────────────────────────

def start_email_scheduler() -> AsyncIOScheduler:
    """
    APScheduler başlat ve polling job'ı ekle.
    FastAPI lifespan içinden çağrılır.
    """
    global _scheduler

    _scheduler = AsyncIOScheduler(timezone="Europe/Istanbul")

    _scheduler.add_job(
        _poll_emails,
        trigger="interval",
        minutes=settings.GMAIL_POLL_INTERVAL_MINUTES,
        id="email_polling",
        name="Gmail E-Fatura Tarama",
        replace_existing=True,
        # İlk çalışmayı hemen yap (başlangıçta 0 bekleme)
        next_run_time=datetime.now(tz=_scheduler.timezone),
    )

    # Onay hatırlatma job'ı (her saatte bir)
    _scheduler.add_job(
        _send_approval_reminders,
        trigger="interval",
        hours=1,
        id="approval_reminders",
        name="Onay Hatırlatma",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info(
        f"📅 Email scheduler başladı "
        f"(her {settings.GMAIL_POLL_INTERVAL_MINUTES} dakikada bir)"
    )
    return _scheduler


def stop_email_scheduler() -> None:
    """Uygulama kapanırken scheduler'ı durdur"""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("📅 Email scheduler durduruldu.")
    _scheduler = None


def get_scheduler():  # -> Optional[AsyncIOScheduler]
    return _scheduler
