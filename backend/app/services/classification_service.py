"""
Fatura Sınıflandırma Servisi — Claude AI
────────────────────────────────────────────────────────────────
Her fatura için Claude'a yapılandırılmış bir prompt gönderir.
Dönen JSON'dan:
  - category       : Fatura kategorisi (kumaş, aksesuar, makine vb.)
  - risk_level     : low | medium | high
  - confidence     : 0.00–1.00
  - suggested_account : Muhasebe hesap kodu
  - payment_method : önerilen ödeme yöntemi
  - anomalies      : tespit edilen anomaliler listesi
  - notes          : Claude'un açıklaması
"""

import json
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.external.claude_client import claude_client
from app.models.approval import Approval, ApprovalLevel, ApprovalStatus
from app.models.audit_log import AuditLog
from app.models.classification import Classification
from app.models.invoice import Invoice, InvoiceStatus
from app.utils.logger import logger

# ── Fatura kategorileri (prompt'ta kullanılır) ─────────────────────────────────
INVOICE_CATEGORIES = [
    "kumas",            # Ham ve işlenmiş kumaş
    "iplik",            # İplik ve iplik ürünleri
    "aksesuar",         # Düğme, fermuar, etiket vb.
    "boya_kimyasal",    # Boyalar ve kimyasallar
    "makine_ekipman",   # Üretim makineleri
    "enerji",           # Elektrik, doğalgaz
    "lojistik",         # Kargo, nakliye
    "hizmet",           # Danışmanlık, bakım, yazılım
    "ofis",             # Ofis malzemeleri
    "teknoloji",        # Bilgisayar, elektronik, IT ekipmanları
    "yemek_iase",       # Yemek, gıda, iaşe
    "bakim_onarim",     # Bina bakım, onarım
    "sigorta",          # Sigorta primleri
    "diger",            # Yukarıdakilere uymayan diğer
]

# Geriye uyumluluk — eski referanslar için
TEXTILE_CATEGORIES = INVOICE_CATEGORIES

# ── Muhasebe hesap kodları (öneri için) ──────────────────────────────────────
ACCOUNT_CODES = {
    "kumas": "7101",
    "iplik": "7102",
    "aksesuar": "7103",
    "boya_kimyasal": "7104",
    "makine_ekipman": "2530",
    "enerji": "7710",
    "lojistik": "7730",
    "hizmet": "7740",
    "ofis": "7800",
    "teknoloji": "2550",
    "yemek_iase": "7750",
    "bakim_onarim": "7760",
    "sigorta": "7770",
    "diger": "6990",
}


class ClassificationService:
    """
    Faturayı Claude AI ile sınıflandırır ve DB'ye kaydeder.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Ana metod ─────────────────────────────────────────────────────────────

    async def classify(self, invoice: Invoice) -> Classification:
        """
        Faturayı sınıflandır ve Classification kaydı oluştur.
        Başarı sonrası fatura durumunu AWAITING_FIRST_APPROVAL'a çeker.
        """
        logger.info(
            f"[Classification] Başlıyor: {invoice.invoice_number} "
            f"(tutar: {invoice.total_amount} {invoice.currency})"
        )

        # Geçmiş sınıflandırmayı kontrol et
        existing = await self.db.execute(
            select(Classification).where(Classification.invoice_id == invoice.id)
        )
        old = existing.scalar_one_or_none()

        # Claude'a sor
        raw_result = self._ask_claude(invoice)

        # Sonucu parse et
        result = self._parse_claude_response(raw_result, invoice)

        # DB kaydını oluştur veya güncelle
        if old:
            old.category = result["category"]
            old.risk_level = result["risk_level"]
            old.confidence_score = Decimal(str(result["confidence"]))
            old.suggested_account = result["suggested_account"]
            old.suggested_payment_method = result["payment_method"]
            old.ai_notes = result["notes"]
            old.ai_model_version = result["model_version"]
            old.anomalies = result["anomalies"]
            classification = old
        else:
            classification = Classification(
                invoice_id=invoice.id,
                category=result["category"],
                risk_level=result["risk_level"],
                confidence_score=Decimal(str(result["confidence"])),
                suggested_account=result["suggested_account"],
                suggested_payment_method=result["payment_method"],
                ai_notes=result["notes"],
                ai_model_version=result["model_version"],
                anomalies=result["anomalies"],
            )
            self.db.add(classification)

        # Fatura bilgilerini güncelle
        invoice.category = result["category"]
        invoice.risk_level = result["risk_level"]
        invoice.status = InvoiceStatus.AWAITING_FIRST_APPROVAL

        # Birinci onay kaydını oluştur
        await self._create_first_approval(invoice)

        # Audit log
        self.db.add(AuditLog(
            invoice_id=invoice.id,
            action="invoice.classified",
            new_values={
                "category": result["category"],
                "risk_level": result["risk_level"],
                "confidence": float(result["confidence"]),
                "anomaly_count": len(result["anomalies"]),
                "model": result["model_version"],
            },
        ))

        await self.db.flush()

        logger.info(
            f"[Classification] ✅ {invoice.invoice_number} → "
            f"kategori={result['category']} risk={result['risk_level']} "
            f"güven={result['confidence']:.0%}"
        )
        return classification

    # ── Claude prompt ─────────────────────────────────────────────────────────

    def _ask_claude(self, invoice: Invoice) -> str:
        """Fatura verilerini Claude'a gönder, ham JSON yanıtı al"""

        system_prompt = f"""Sen bir tekstil firması için e-fatura analiz uzmanısın.
Görevin: Gelen fatura verilerini analiz ederek JSON formatında sınıflandırma sonucu üretmek.

Firma tekstil sektöründe faaliyet gösteriyor ancak teknoloji, ofis, yemek, sigorta gibi
sektör dışı gider faturaları da alabilir. Kategoriyi faturadaki MAL/HİZMET içeriğine göre seç,
tedarikçi ismi veya kargo bilgisine göre değil.

Örneğin:
- Ekran kartı, bilgisayar, yazıcı → teknoloji
- Kumaş, parça boya → kumas veya boya_kimyasal
- HepsiJet/Aras Kargo teslimatı ama ürün elektronik → teknoloji (kargoya değil ürüne bak)

KATEGORİLER (sadece bunlardan birini seç):
{', '.join(INVOICE_CATEGORIES)}

KATEGORİ AÇIKLAMALARI:
- kumas: Ham kumaş, işlenmiş kumaş alımları
- iplik: İplik ve iplik ürünleri
- aksesuar: Düğme, fermuar, etiket, ambalaj
- boya_kimyasal: Boya, kimyasal madde
- makine_ekipman: Üretim makineleri, yedek parça
- enerji: Elektrik, doğalgaz, su faturaları
- lojistik: Kargo, nakliye, taşımacılık HİZMETİ faturaları (ürün taşıma bedeli)
- hizmet: Danışmanlık, yazılım hizmeti, bakım sözleşmesi
- ofis: Kırtasiye, ofis mobilyası
- teknoloji: Bilgisayar, elektronik, IT ekipmanı, yazıcı, ekran kartı, telefon
- yemek_iase: Yemek, gıda, iaşe, kantin
- bakim_onarim: Bina bakım, tesisat, onarım
- sigorta: Sigorta primleri
- diger: Yukarıdakilere uymayan giderler

RİSK SEVİYELERİ:
- low    : Normal fatura, standart tutar, bilinen tedarikçi
- medium : Orta risk, dikkate alınmalı
- high   : Yüksek risk — olağandışı tutar, bilinmeyen tedarikçi, anomali var

YANIT FORMATI (sadece JSON döndür, başka hiçbir şey yazma):
{{
  "category": "<kategori>",
  "risk_level": "low|medium|high",
  "confidence": 0.00,
  "suggested_account": "<hesap_kodu>",
  "payment_method": "nakit|havale|cek|kredi_karti|acik_hesap",
  "anomalies": [
    {{"type": "<tip>", "severity": "low|medium|high", "message": "<açıklama>"}}
  ],
  "notes": "<kısa analiz notu>"
}}"""

        # Fatura kalemlerini metne çevir
        line_items_text = ""
        raw_pdf_text = ""

        if invoice.ubl_xml:
            # Öncelik 1: UBL-XML'den yapılandırılmış kalem bilgisi
            lines = invoice.ubl_xml.get("Invoice", {}).get("InvoiceLine", [])
            if isinstance(lines, dict):
                lines = [lines]
            for i, line in enumerate(lines[:10], 1):  # max 10 kalem
                desc = line.get("Item", {}).get("Name", "-")
                if isinstance(desc, dict):
                    desc = desc.get("#text", "-")
                amount = line.get("LineExtensionAmount", {})
                if isinstance(amount, dict):
                    amount = amount.get("#text", "?")
                line_items_text += f"  {i}. {desc}: {amount} TRY\n"

            # Öncelik 2: PDF'den çıkarılan ham metin (AI'ın okuması için)
            raw_pdf_text = invoice.ubl_xml.get("_raw_text", "")

        # Dosya adından ipucu
        filename_hint = ""
        if invoice.source_filename:
            filename_hint = f"\n- Dosya Adı    : {invoice.source_filename}"

        # Ham PDF metni varsa ve kalem bilgisi yoksa, metni prompt'a ekle
        raw_text_section = ""
        if raw_pdf_text and not line_items_text.strip():
            # İlk 2000 karakteri al (çok uzun metin prompt'u kirletir)
            truncated = raw_pdf_text[:2000]
            raw_text_section = f"""

PDF'DEN ÇIKARILAN HAM METİN (faturanın okunabilir içeriği):
{truncated}
"""

        user_message = f"""Aşağıdaki faturayı analiz et ve JSON döndür:

FATURA BİLGİLERİ:
- Fatura No     : {invoice.invoice_number}
- Tedarikçi     : {invoice.supplier.name if invoice.supplier else 'Bilinmiyor'}
- Vergi No      : {invoice.supplier.vat_number if invoice.supplier else '-'}
- Fatura Tarihi : {invoice.invoice_date}
- KDV Hariç     : {invoice.amount} {invoice.currency}
- KDV           : {invoice.tax_amount} {invoice.currency}
- Genel Toplam  : {invoice.total_amount} {invoice.currency}
- Kaynak Email  : {invoice.source_email or '-'}{filename_hint}

FATURA KALEMLERİ:
{line_items_text or '  (kalem bilgisi mevcut değil)'}
{raw_text_section}
ÖNEMLİ: Kategoriyi belirlerken teslimat/kargo bilgisine değil, satın alınan MAL veya HİZMETin
ne olduğuna odaklan. Tedarikçi adı yanıltıcı olabilir (ör: incehesap.com bir elektronik mağazasıdır).
PDF ham metnindeki "Mal Hizmet" tablosunu dikkatle oku — orada satın alınan ürün/hizmet yazar.

Sadece JSON döndür."""

        return claude_client.complete(
            system_prompt=system_prompt,
            user_message=user_message,
        )

    # ── Yanıt parse ───────────────────────────────────────────────────────────

    def _parse_claude_response(
        self, raw: str, invoice: Invoice
    ) -> dict[str, Any]:
        """
        Claude'un ham metin yanıtından JSON çıkar.
        Parse başarısız olursa güvenli fallback değerler döndürür.
        """
        # JSON bloğunu çıkar (Claude bazen ```json ... ``` içinde verir)
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not json_match:
            logger.warning(
                f"[Classification] JSON bulunamadı, fallback kullanılıyor.\n"
                f"Ham yanıt: {raw[:200]}"
            )
            return self._fallback_result(invoice)

        try:
            data = json.loads(json_match.group())
        except json.JSONDecodeError as exc:
            logger.warning(f"[Classification] JSON parse hatası: {exc}")
            return self._fallback_result(invoice)

        # Alanları doğrula ve temizle
        category = data.get("category", "diger").lower()
        if category not in INVOICE_CATEGORIES:
            category = "diger"

        risk_level = data.get("risk_level", "medium").lower()
        if risk_level not in ("low", "medium", "high"):
            risk_level = "medium"

        confidence = float(data.get("confidence", 0.5))
        confidence = max(0.0, min(1.0, confidence))  # 0–1 aralığında tut

        suggested_account = (
            data.get("suggested_account")
            or ACCOUNT_CODES.get(category, "6990")
        )

        payment_method = data.get("payment_method", "havale")

        anomalies = data.get("anomalies", [])
        if not isinstance(anomalies, list):
            anomalies = []

        notes = str(data.get("notes", ""))[:1000]  # max 1000 karakter

        return {
            "category": category,
            "risk_level": risk_level,
            "confidence": confidence,
            "suggested_account": suggested_account,
            "payment_method": payment_method,
            "anomalies": anomalies,
            "notes": notes,
            "model_version": settings_model(),
        }

    def _fallback_result(self, invoice: Invoice) -> dict[str, Any]:
        """Claude yanıtı parse edilemezse güvenli varsayılan değerler"""
        return {
            "category": "diger",
            "risk_level": "medium",
            "confidence": 0.3,
            "suggested_account": "6990",
            "payment_method": "havale",
            "anomalies": [{
                "type": "parse_error",
                "severity": "low",
                "message": "AI yanıtı parse edilemedi, manuel inceleme gerekebilir."
            }],
            "notes": "Otomatik sınıflandırma başarısız — manuel doğrulama önerilir.",
            "model_version": settings_model(),
        }

    # ── Onay kaydı oluştur ────────────────────────────────────────────────────

    async def _create_first_approval(self, invoice: Invoice) -> None:
        """
        Sınıflandırma tamamlandığında otomatik olarak
        birinci onay kaydını oluştur (FIRST_APPROVER_EMAIL kullanıcısına).
        """
        from sqlalchemy import select
        from app.models.user import User

        # İlk approver kullanıcısını bul
        result = await self.db.execute(
            select(User).where(
                User.email == settings_first_approver(),
                User.is_active == True,
            )
        )
        approver = result.scalar_one_or_none()

        if not approver:
            # Yapılandırılan kullanıcı yoksa herhangi bir admin'e ata
            from app.models.user import User
            fallback = await self.db.execute(
                select(User).where(User.role == "admin", User.is_active == True).limit(1)
            )
            approver = fallback.scalar_one_or_none()

        if not approver:
            logger.warning(
                f"[Classification] Birinci onaylayan bulunamadı: "
                f"{settings_first_approver()} — onay atanmadı."
            )
            return

        approval = Approval(
            invoice_id=invoice.id,
            approver_id=approver.id,
            approval_level=ApprovalLevel.FIRST,
            status=ApprovalStatus.PENDING,
        )
        self.db.add(approval)
        logger.debug(
            f"[Classification] Birinci onay oluşturuldu → {approver.email}"
        )


# ── Lazy config yardımcıları (circular import önlemek için) ───────────────────

def settings_model() -> str:
    from app.config import settings
    return settings.CLAUDE_MODEL


def settings_first_approver() -> str:
    from app.config import settings
    return settings.FIRST_APPROVER_EMAIL
