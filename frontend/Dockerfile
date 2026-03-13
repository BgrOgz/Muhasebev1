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
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# ── Stage 2: Serve with Nginx ───────────────
FROM nginx:1.25-alpine

# gettext paketi (envsubst için gerekli)
RUN apk add --no-cache gettext

# Nginx konfigürasyon şablonu
COPY nginx.conf.template /etc/nginx/conf.d/default.conf.template

# Build çıktısını kopyala
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 3000

# BACKEND_URL env değişkenini nginx.conf'a yerleştir ve nginx başlat
CMD ["/bin/sh", "-c", "envsubst '$BACKEND_URL' < /etc/nginx/conf.d/default.conf.template > /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"]
