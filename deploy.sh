#!/bin/bash
# =============================================
# E-Fatura Sistemi — VPS Kurulum & Deploy Script
# Kullanım: bash deploy.sh
# =============================================

set -e  # Hata olursa dur

DOMAIN="temtasftr.com"
APP_DIR="/opt/fatura"
REPO_DIR="$APP_DIR/Muhasebev1"

echo "🚀 E-Fatura Sistemi Deploy Başlıyor..."
echo "   Domain: $DOMAIN"
echo ""

# ── 1. Sistem Güncellemesi ─────────────────────────────────────────────────────
echo "📦 [1/7] Sistem güncelleniyor..."
apt-get update -qq
apt-get upgrade -y -qq

# ── 2. Docker Kurulumu ────────────────────────────────────────────────────────
echo "🐳 [2/7] Docker kuruluyor..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
    systemctl enable docker
    systemctl start docker
    echo "   ✅ Docker kuruldu"
else
    echo "   ✅ Docker zaten kurulu: $(docker --version)"
fi

# Docker Compose v2 kontrolü
if ! docker compose version &> /dev/null; then
    apt-get install -y docker-compose-plugin
fi

# ── 3. Uygulama Dizini ─────────────────────────────────────────────────────────
echo "📁 [3/7] Uygulama dizini hazırlanıyor..."
mkdir -p $APP_DIR
mkdir -p $REPO_DIR/nginx/ssl

# ── 4. .env Dosyası Kontrolü ──────────────────────────────────────────────────
echo "⚙️  [4/7] Environment kontrol ediliyor..."
if [ ! -f "$REPO_DIR/.env" ]; then
    echo ""
    echo "   ❌ .env dosyası bulunamadı!"
    echo "   Lütfen .env.production.example dosyasını kopyalayın:"
    echo "   cp $REPO_DIR/.env.production.example $REPO_DIR/.env"
    echo "   Sonra .env dosyasını düzenleyip tekrar çalıştırın."
    exit 1
fi
echo "   ✅ .env dosyası mevcut"

# ── 5. SSL Sertifikası (Let's Encrypt) ───────────────────────────────────────
echo "🔒 [5/7] SSL sertifikası alınıyor..."
cd $REPO_DIR

# Önce HTTP üzerinden nginx başlat (certbot doğrulaması için)
cat > ./nginx/nginx-temp.conf << 'EOF'
server {
    listen 80;
    server_name _;
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
    location / {
        return 200 "ok";
    }
}
EOF

docker run -d --name temp-nginx \
    -p 80:80 \
    -v $(pwd)/nginx/nginx-temp.conf:/etc/nginx/conf.d/default.conf \
    -v certbot_www:/var/www/certbot \
    nginx:1.25-alpine 2>/dev/null || true

sleep 2

# Certbot ile sertifika al
docker run --rm \
    -v certbot_conf:/etc/letsencrypt \
    -v certbot_www:/var/www/certbot \
    certbot/certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email admin@$DOMAIN \
    --agree-tos \
    --no-eff-email \
    -d $DOMAIN \
    -d www.$DOMAIN \
    --non-interactive || echo "   ⚠️  SSL atlandı (test ortamı)"

docker stop temp-nginx 2>/dev/null || true
docker rm temp-nginx 2>/dev/null || true
rm -f ./nginx/nginx-temp.conf

# nginx.conf içindeki DOMAIN_ADI'nı gerçek domain ile değiştir
sed -i "s/DOMAIN_ADI/$DOMAIN/g" ./nginx/nginx.conf
echo "   ✅ nginx.conf güncellendi: $DOMAIN"

# ── 6. Docker Build & Start ────────────────────────────────────────────────────
echo "🔨 [6/7] Docker image'lar build ediliyor ve başlatılıyor..."
cd $REPO_DIR

docker compose pull db 2>/dev/null || true
docker compose build --no-cache
docker compose up -d

echo "   ⏳ Servisler başlıyor (30 saniye bekleniyor)..."
sleep 30

# Sağlık kontrolü
if curl -sf http://localhost/api/v1/health > /dev/null; then
    echo "   ✅ Backend sağlıklı"
else
    echo "   ⚠️  Backend henüz hazır değil, logları kontrol et:"
    echo "   docker compose logs backend"
fi

# ── 7. Firewall ────────────────────────────────────────────────────────────────
echo "🔥 [7/7] Firewall ayarlanıyor..."
if command -v ufw &> /dev/null; then
    ufw --force enable
    ufw allow 22/tcp    # SSH
    ufw allow 80/tcp    # HTTP
    ufw allow 443/tcp   # HTTPS
    ufw deny 8000/tcp   # Backend direkt erişimi kapat (sadece nginx üzerinden)
    ufw deny 5432/tcp   # PostgreSQL dışarıya kapalı
    echo "   ✅ UFW firewall aktif"
fi

echo ""
echo "════════════════════════════════════════"
echo "✅ Deploy tamamlandı!"
echo ""
echo "   🌍 Site    : https://$DOMAIN"
echo "   📊 API     : https://$DOMAIN/api/v1/health"
echo "   📚 Docs    : https://$DOMAIN/docs"
echo ""
echo "   Loglar için: docker compose logs -f"
echo "   Yeniden başlat: docker compose restart"
echo "════════════════════════════════════════"
