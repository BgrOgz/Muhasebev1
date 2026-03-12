# =============================================
# E-Fatura Frontend — Multi-stage Docker Build
# =============================================

# ── Stage 1: Build ──────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Bağımlılıkları önce kopyala (layer caching)
COPY package.json package-lock.json ./
RUN npm ci --silent

# Kaynak kodu kopyala ve build et
COPY . .
RUN npm run build

# ── Stage 2: Serve with Nginx ───────────────
FROM nginx:1.25-alpine

# Nginx konfigürasyonu
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Build çıktısını kopyala
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]
