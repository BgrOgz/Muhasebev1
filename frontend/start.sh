#!/bin/bash
# E-Fatura Frontend Başlatma Scripti
export PATH="/opt/homebrew/bin:$PATH"
cd "$(dirname "$0")"
echo "🚀 Frontend başlatılıyor → http://localhost:3000"
node node_modules/.bin/vite
