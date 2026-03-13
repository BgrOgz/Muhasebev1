"""
Invoice Processor
────────────────────────────────────────────────────────
Email poller'dan gelen her eki alır:
  1. Dosya türüne göre parser'a yönlendirir (XML → UBLParser, PDF → PDFParser)
  2. Supplier'ı bulur / oluşturur
  3. Invoice kaydını DB'ye yazar
  4. Email processing log kaydeder
  5. Claude AI sınıflandırmasını tetikler (Adım 6'da dolacak)
"""

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.email_log import EmailProcessingLog
from app.models.invoice import Invoice, InvoiceStatus
from app.models.supplier import Supplier
from app.services.email_service import EmailAttachment
from app.utils.logger import logger


class InvoiceProcessor:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Ana giriş noktası ─────────────────────────────────────────────────────

    async def process(
        self,
        attachment: EmailAttachment,
        from_email: str,
        email_subject: str,
        email_date: Optional[str],
        email_id: str,
    ) -> dict[str, Any]:
        """
        Tek bir email ekini faturaya dönüştür.
        Başarılı → {"success": True, "invoice_id": "uuid"}
        Başarısız → {"success": False, "error": "mesaj"}
        """
        log = EmailProcessingLog(
            email_id=email_id,
            from_email=from_email,
            email_subject=email_subject,
            attachment_filename=attachment.filename,
            status="processing",
        )
        self.db.add(log)
        await self.db.flush()  # ID almak için

        try:
            # 1. Dosyayı parse et
            invoice_data = await self._parse_attachment(attachment)

            # 2. Supplier'ı bul veya oluştur
            supplier = await self._get_or_create_supplier(
                from_email=from_email,
                name=invoice_data.get("supplier_name", from_email),
                vat_number=invoice_data.get("supplier_vat"),
            )

            # 3. Duplicate kontrolü — aynı fatura numarası zaten varsa hata yerine mevcut ID dön
            existing = await self.db.execute(
                select(Invoice).where(
                    Invoice.invoice_number == invoice_data["invoice_number"],
                    Invoice.deleted_at == None,
                )
            )
            duplicate = existing.scalar_one_or_none()
            if duplicate:
                logger.warning(
                    f"Mükerrer fatura yükleme engellendi: {invoice_data['invoice_number']}"
                )
                log.status = "duplicate"
                log.error_message = f"Bu fatura zaten kayıtlı: {invoice_data['invoice_number']}"
                log.processed_at = datetime.now(timezone.utc)
                from app.utils.exceptions import DuplicateInvoiceError
                raise DuplicateInvoiceError(invoice_data["invoice_number"])

            # 4. Fatura kaydını oluştur
            invoice = Invoice(
                invoice_number=invoice_data["invoice_number"],
                supplier_id=supplier.id,
                amount=invoice_data["amount"],
                tax_amount=invoice_data["tax_amount"],
                total_amount=invoice_data["total_amount"],
                currency=invoice_data.get("currency", "TRY"),
                invoice_date=invoice_data["invoice_date"],
                due_date=invoice_data.get("due_date"),
                status=InvoiceStatus.DRAFT,
                ubl_xml=invoice_data.get("ubl_xml"),
                source_email=from_email,
                source_email_subject=email_subject,
                source_filename=attachment.filename,
            )
            self.db.add(invoice)
            await self.db.flush()

            # 5. Log güncelle
            log.status = "success"
            log.processed_at = datetime.now(timezone.utc)

            # 6. AI sınıflandırmasını tetikle
            await self._trigger_classification(invoice)

            logger.info(
                f"Fatura kaydedildi: {invoice.invoice_number} "
                f"(supplier: {supplier.name})"
            )

            return {"success": True, "invoice_id": str(invoice.id)}

        except Exception as exc:
            from fastapi import HTTPException
            if isinstance(exc, HTTPException):
                raise  # HTTP hataları (409, 415 vb.) doğrudan router'a ilet
            log.status = "failed"
            log.error_message = str(exc)
            log.processed_at = datetime.now(timezone.utc)
            logger.error(f"Fatura işleme hatası ({attachment.filename}): {exc}")
            return {"success": False, "error": str(exc)}

    # ── Parser yönlendirme ────────────────────────────────────────────────────

    async def _parse_attachment(self, attachment: EmailAttachment) -> dict:
        """Dosya uzantısına göre doğru parser'a yönlendir"""
        # Lazy import — Adım 5'te parsers yazılacak
        from app.parsers.ubl_parser import UBLParser
        from app.parsers.pdf_parser import PDFParser

        ext = attachment.filename.rsplit(".", 1)[-1].lower()

        if ext == "xml":
            parser = UBLParser(attachment.content)
            return parser.parse()

        elif ext == "pdf":
            parser = PDFParser(attachment.content)
            return parser.parse()

        elif ext in ("xls", "xlsx"):
            # Excel parser ileride eklenebilir
            raise NotImplementedError(
                f"Excel parser henüz desteklenmiyor: {attachment.filename}"
            )

        else:
            raise ValueError(f"Desteklenmeyen dosya türü: {ext}")

    # ── Supplier yönetimi ─────────────────────────────────────────────────────

    async def _get_or_create_supplier(
        self,
        from_email: str,
        name: str,
        vat_number: str = None,  # Optional[str]
    ) -> Supplier:
        """
        Tedarikçiyi VAT numarasına, isme veya email adresine göre bul.
        Bulamazsa yeni kayıt oluştur.

        ÖNEMLİ: Manuel yüklemelerde sahte email (manuel_yukle@...) kullanılır.
        Bu email ile eşleme YAPILMAZ, yoksa tüm manuel yüklemeler aynı
        tedarikçiye bağlanır (örn: ilk yüklenen tedarikçi hep tekrarlanır).
        """
        is_manual_upload = from_email.startswith("manuel_yukle@")

        # 1. Önce VAT numarasıyla ara (en güvenilir eşleme)
        if vat_number:
            result = await self.db.execute(
                select(Supplier).where(Supplier.vat_number == vat_number)
            )
            supplier = result.scalar_one_or_none()
            if supplier:
                # VAT bulundu; ama isim güncellenmişse güncelle
                if name and name != "Bilinmeyen Tedarikçi" and supplier.name != name:
                    logger.info(
                        f"Tedarikçi ismi güncellendi: {supplier.name} → {name}"
                    )
                    supplier.name = name
                return supplier

        # 2. İsim ile ara (tam eşleşme, sadece gerçek isimler için)
        if name and name != "Bilinmeyen Tedarikçi":
            result = await self.db.execute(
                select(Supplier).where(Supplier.name == name)
            )
            supplier = result.scalar_one_or_none()
            if supplier:
                return supplier

        # 3. Email adresine göre ara — SADECE gerçek email adresleri için
        #    Manuel yükleme emaili (manuel_yukle@...) ile eşleme YAPMA!
        if not is_manual_upload:
            result = await self.db.execute(
                select(Supplier).where(Supplier.contact_email == from_email)
            )
            supplier = result.scalar_one_or_none()
            if supplier:
                return supplier

        # 4. Yeni tedarikçi oluştur
        supplier = Supplier(
            name=name,
            vat_number=vat_number,
            # Manuel yüklemelerde sahte email'i kaydetme
            contact_email=from_email if not is_manual_upload else None,
        )
        self.db.add(supplier)
        await self.db.flush()
        logger.info(f"Yeni tedarikçi oluşturuldu: {name} (vat={vat_number})")
        return supplier

    # ── AI tetikleyici ────────────────────────────────────────────────────────

    async def _trigger_classification(self, invoice: Invoice) -> None:
        """
        Claude AI sınıflandırmasını çalıştır.
        Supplier ilişkisini yükle, ClassificationService'e devret.
        """
        from app.services.classification_service import ClassificationService
        from sqlalchemy.orm import selectinload

        # Supplier ilişkisini eager load et (prompt'ta kullanılıyor)
        from sqlalchemy import select as sa_select
        from app.models.invoice import Invoice as InvoiceModel

        result = await self.db.execute(
            sa_select(InvoiceModel)
            .options(selectinload(InvoiceModel.supplier))
            .where(InvoiceModel.id == invoice.id)
        )
        full_invoice = result.scalar_one_or_none() or invoice

        invoice.status = InvoiceStatus.PROCESSING
        await self.db.flush()

        try:
            svc = ClassificationService(self.db)
            await svc.classify(full_invoice)
            logger.info(
                f"AI sınıflandırması tamamlandı: {invoice.invoice_number}"
            )
        except Exception as exc:
            # Sınıflandırma başarısız → fatura yine de kaydedildi, log yaz
            logger.error(
                f"AI sınıflandırma hatası ({invoice.invoice_number}): {exc}"
            )
            invoice.status = InvoiceStatus.AWAITING_FIRST_APPROVAL
