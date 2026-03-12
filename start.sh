#!/bin/bash
# ────────────────────────────────────────────────────────
# Fatura Otomasyon — Tek Komutla Başlat
# Kullanım: ./start.sh
# ────────────────────────────────────────────────────────

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║     Fatura Otomasyon Sistemi - Başlatılıyor  ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ── 1. Python paketleri ──────────────────────────────
echo "📦 Python paketleri kontrol ediliyor..."
cd "$SCRIPT_DIR/backend"

if ! pip show fastapi &>/dev/null; then
    echo "   ➜ pip install çalıştırılıyor..."
    pip install -r requirements.txt -q
else
    echo "   ✓ Python paketleri zaten yüklü"
fi

# ── 2. Admin kullanıcı ───────────────────────────────
echo ""
echo "👤 Admin kullanıcı kontrol ediliyor..."
python -m scripts.seed_admin 2>/dev/null || true

# ── 3. Frontend paketleri ────────────────────────────
echo ""
echo "📦 Frontend paketleri kontrol ediliyor..."
cd "$SCRIPT_DIR/frontend"

if [ ! -d "node_modules" ]; then
    echo "   ➜ npm install çalıştırılıyor..."
    npm install -q
else
    echo "   ✓ node_modules zaten var"
fi

# ── 4. Servisleri başlat ─────────────────────────────
echo ""
echo "🚀 Servisler başlatılıyor..."
echo ""
echo "   Backend  → http://localhost:8000/docs"
echo "   Frontend → http://localhost:3000"
echo ""
echo "   Durdurmak için: Ctrl+C"
echo ""

# Backend'i arka planda başlat
cd "$SCRIPT_DIR/backend"
uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!

# 2 saniye bekle backend ayağa kalksın
sleep 2

# Frontend'i ön planda başlat (bu terminal'i bloklar)
cd "$SCRIPT_DIR/frontend"
npm run dev -- --port 3000

# Temizlik
kill $BACKEND_PID 2>/dev/null || true
