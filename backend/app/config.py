"""
Uygulama Konfigürasyonu
Tüm environment variable'lar buradan okunur.
"""

from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Optional

# .env dosyasını backend/ veya üst dizinde ara
_BASE = Path(__file__).resolve().parent.parent  # backend/
_ENV_FILE = _BASE / ".env" if (_BASE / ".env").exists() else _BASE.parent / ".env"

# Sistem env değişkenleri .env'yi ezmemesi için override ile yükle
from dotenv import load_dotenv
load_dotenv(dotenv_path=_ENV_FILE, override=True)


class Settings(BaseSettings):
    # ----- UYGULAMA -----
    APP_ENV: str = "development"
    APP_SECRET_KEY: str
    DEBUG: bool = True

    # ----- VERİTABANI -----
    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    @property
    def async_database_url(self) -> str:
        """Railway postgresql:// → postgresql+asyncpg:// otomatik dönüşüm"""
        url = self.DATABASE_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    # ----- JWT AUTH -----
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 24

    # ----- GMAIL -----
    GMAIL_SERVICE_EMAIL: str = ""
    GMAIL_APP_PASSWORD: str = ""
    GMAIL_IMAP_SERVER: str = "imap.gmail.com"
    GMAIL_IMAP_PORT: int = 993
    GMAIL_POLL_INTERVAL_MINUTES: int = 5

    # ----- CLAUDE AI -----
    ANTHROPIC_API_KEY: str
    CLAUDE_MODEL: str = "claude-3-5-sonnet-20241022"

    # ----- SMTP / BİLDİRİM -----
    SMTP_HOST: str = "smtp.sendgrid.net"
    SMTP_PORT: int = 587
    SMTP_USER: str = "apikey"
    SMTP_PASSWORD: str = ""          # Boşsa bildirim simüle edilir (dev modu)
    FROM_EMAIL: str = "noreply@tekstil-fatura.com"
    FROM_NAME: str = "E-Fatura Sistemi"
    APP_URL: str = "http://localhost:3000"
    NOTIFICATION_CC_EMAIL: str = ""  # Opsiyonel CC alıcı

    # ----- SENDGRID (eski alan — geriye dönük uyumluluk) -----
    SENDGRID_API_KEY: str = ""
    SENDGRID_FROM_EMAIL: str = "noreply@company.com"
    SENDGRID_FROM_NAME: str = "Fatura Otomasyon Sistemi"

    # ----- FRONTEND URL (CORS için) -----
    FRONTEND_URL: str = "http://localhost:3000"

    # ----- ONAY SİSTEMİ -----
    FIRST_APPROVER_EMAIL: str = "muhasebe@test.com"
    FINAL_APPROVER_EMAIL: str = "patron@test.com"
    APPROVAL_REMINDER_HOURS: int = 1
    APPROVAL_MAX_REMINDERS: int = 3

    # ----- DOSYA YÜKLEME -----
    MAX_FILE_SIZE_MB: int = 25
    ALLOWED_EXTENSIONS: str = "xml,pdf,xls,xlsx"
    UPLOAD_DIR: str = "./uploads"

    # ----- ARŞİV -----
    ARCHIVE_RETENTION_YEARS: int = 10
    ARCHIVE_DIR: str = "./archive"

    class Config:
        env_file = str(_ENV_FILE)
        case_sensitive = True

    @property
    def allowed_extensions_list(self) -> list[str]:
        return [ext.strip() for ext in self.ALLOWED_EXTENSIONS.split(",")]

    @property
    def max_file_size_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024


# Singleton instance — tüm uygulama bu nesneyi kullanır
settings = Settings()
