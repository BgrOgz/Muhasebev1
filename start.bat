@echo off
REM ────────────────────────────────────────────────────────
REM Fatura Otomasyon — Tek Komutla Başlat (Windows)
REM Kullanım: start.bat dosyasına çift tıkla
REM ────────────────────────────────────────────────────────

echo.
echo ╔══════════════════════════════════════════════╗
echo ║     Fatura Otomasyon Sistemi - Başlatılıyor  ║
echo ╚══════════════════════════════════════════════╝
echo.

cd /d "%~dp0"

REM ── 1. Python paketleri ─────────────────────────────
echo [1/4] Python paketleri yukleniyor...
cd backend
pip install -r requirements.txt -q
if errorlevel 1 (
    echo HATA: pip install basarisiz oldu!
    echo Python yuklu mu? python --version
    pause
    exit /b 1
)

REM ── 2. Admin kullanıcı ──────────────────────────────
echo.
echo [2/4] Admin kullanici olusturuluyor...
python -m scripts.seed_admin

REM ── 3. Frontend paketleri ───────────────────────────
echo.
echo [3/4] Frontend paketleri yukleniyor...
cd ..\frontend
if not exist node_modules (
    npm install -q
)

REM ── 4. Servisleri başlat ────────────────────────────
echo.
echo [4/4] Servisler baslatiliyor...
echo.
echo    Backend  - http://localhost:8000/docs
echo    Frontend - http://localhost:3000
echo.
echo    Giris: admin@firma.com / admin123456
echo.

REM Backend'i yeni pencerede başlat
start "Backend" cmd /k "cd /d "%~dp0backend" && uvicorn app.main:app --reload --port 8000"

REM 3 saniye bekle
timeout /t 3 /nobreak > nul

REM Frontend'i bu pencerede başlat
cd /d "%~dp0frontend"
npm run dev -- --port 3000

pause
