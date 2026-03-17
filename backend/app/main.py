"""
Fatura Otomasyon Sistemi — FastAPI Giriş Noktası
Başlatma: uvicorn app.main:app --reload
Docs:     http://localhost:8000/docs
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.utils.logger import logger

# Router'lar
from app.routers import admin, auth, invoices, approvals, reports, system


# ── Uygulama başlatma / kapatma ───────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup ve shutdown olayları"""
    logger.info("🚀 Fatura Otomasyon Sistemi başlatılıyor...")
    logger.info(f"   Ortam  : {settings.APP_ENV}")
    logger.info(f"   Debug  : {settings.DEBUG}")

    # Tabloları oluştur (tüm ortamlarda — create_all idempotent)
    from app.database import create_tables
    await create_tables()
    logger.info("   DB     : Tablolar kontrol edildi ✓")

    # Email polling scheduler'ı başlat
    from app.services.email_poller import start_email_scheduler, stop_email_scheduler
    start_email_scheduler()
    logger.info(
        f"   Email : Scheduler aktif "
        f"(her {settings.GMAIL_POLL_INTERVAL_MINUTES} dk) ✓"
    )

    logger.info("✅ Sistem hazır!\n")
    yield

    # Shutdown
    logger.info("🛑 Sistem kapatılıyor...")
    stop_email_scheduler()


# ── FastAPI uygulaması ────────────────────────────────────────────────────────
app = FastAPI(
    title="Fatura Otomasyon Sistemi",
    description=(
        "Tekstil firması için Gmail tabanlı e-fatura otomasyon sistemi. "
        "AI sınıflandırma + çok kişili onay workflow."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ─────────────────────────────────────────────────────────────────────
_origins = (
    ["http://localhost:3000", "http://127.0.0.1:3000"]
    if settings.APP_ENV == "development"
    else [
        settings.FRONTEND_URL,
        f"https://www.{settings.FRONTEND_URL.replace('https://', '').replace('http://', '')}",
        "https://temtasftr.com",
        "https://www.temtasftr.com",
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    max_age=3600,
)


# ── Güvenlik başlıkları middleware ─────────────────────────────────────────────
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    if settings.APP_ENV == "production":
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )
    return response


# ── Global hata yakalayıcılar ─────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Beklenmeyen hata: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "code": 500,
            "message": "Sunucu hatası. Lütfen daha sonra tekrar deneyin.",
        },
    )


# ── Router'lar (/api/v1 prefix) ───────────────────────────────────────────────
API_PREFIX = "/api/v1"

app.include_router(admin.router,     prefix=API_PREFIX)
app.include_router(auth.router,      prefix=API_PREFIX)
app.include_router(invoices.router,  prefix=API_PREFIX)
app.include_router(approvals.router, prefix=API_PREFIX)
app.include_router(reports.router,   prefix=API_PREFIX)
app.include_router(system.router,    prefix=API_PREFIX)


# ── Sağlık kontrol endpoint'i ─────────────────────────────────────────────────
@app.get("/api/v1/health", tags=["Sistem"])
async def health_check():
    """Servis canlı mı?"""
    return {
        "status": "ok",
        "version": "1.0.0",
        "env": settings.APP_ENV,
    }


@app.get("/", tags=["Sistem"])
async def root():
    return {
        "message": "Fatura Otomasyon Sistemi",
        "docs": "/docs",
        "health": "/api/v1/health",
    }
