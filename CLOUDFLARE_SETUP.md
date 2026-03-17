# Cloudflare Kurulum Rehberi

Bu rehber, Muhasebev1 sistemini Cloudflare ile koruma altına almak için adım adım talimatlar içerir.

---

## 📋 ÖN KOŞULLAR

- ✅ Aktif domain adı (örn: tekstil-fatura.com)
- ✅ Domain registrar'a erişim (GoDaddy, Namecheap, vb.)
- ✅ Cloudflare hesabı (cloudflare.com)
- ✅ Backend URL (örn: api.tekstil-fatura.com)
- ✅ Frontend URL (örn: tekstil-fatura.com)

---

## 🎯 AŞAMA 1: CLOUDFLARE HESABI OLUŞTURMA

### 1.1 Hesap Açma
1. https://dash.cloudflare.com/sign-up adresine git
2. Email ve şifre ile kayıt ol
3. Email doğrula
4. Plan seç: **Pro ($20/ay)** önerilir

### 1.2 Domain Ekleme
1. Cloudflare Dashboard'a gir
2. **Add a Site** butonuna tıkla
3. Domain adını gir: `tekstil-fatura.com`
4. **Add Site** butonuna tıkla
5. Plan seçiminde **Pro** seç (önerilir)

---

## 🔗 AŞAMA 2: DNS NAMESERVER'LARINI DEĞIŞTIR

### 2.1 Cloudflare Nameserver'larını Al
Cloudflare dashboard'da bu iki nameserver'ı göreceksin:
```
ada.ns.cloudflare.com
nova.ns.cloudflare.com
```

### 2.2 Domain Registrar'da Değiştir

**Eğer GoDaddy'den satın aldıysan:**
1. GoDaddy.com'a gir
2. **Domains** → **My Domains** seçi
3. Domain adına tıkla
4. **DNS** sekmesine git
5. **Nameservers** → **Change Nameservers** seç
6. **Custom nameservers** seç
7. Cloudflare nameserver'larını yapıştır:
   ```
   ada.ns.cloudflare.com
   nova.ns.cloudflare.com
   ```
8. **Save** butonuna tıkla

**Diğer registrar'lar için de benzer adımlar geçerli.**

### 2.3 DNS Yayılmasını Bekle
- ⏳ 24 saat içinde yayılır (genelde 1-2 saat)
- Cloudflare dashboard'da "Nameserver check" bölümünü kontrol et
- Yeşil ✅ işareti göründüğünde tamamlanmış demektir

---

## 🔐 AŞAMA 3: SSL/TLS KONFIGÜRASYONU

### 3.1 SSL/TLS Modunu Ayarla
1. Cloudflare Dashboard → **SSL/TLS** menüsüne git
2. **Overview** sekmesinde
3. **Encryption level** → **Full (Strict)** seç
   ```
   Tarayıcı → Cloudflare: TLS şifreli ✅
   Cloudflare → Backend: TLS şifreli ✅
   ```

### 3.2 Origin Certificate Oluştur (Backend SSL)
1. **SSL/TLS** → **Origin Server** sekmesine git
2. **Create Certificate** butonuna tıkla
3. Ayarlar:
   ```
   Hostname: api.tekstil-fatura.com, *.tekstil-fatura.com
   Validity: 15 years (önerilen)
   ```
4. **Create** butonuna tıkla
5. **Certificate** ve **Private Key** kopyala ve kaydet

### 3.3 Backend'e (Railway) SSL Sertifikasını Yükle
1. Railway Dashboard'a git
2. Muhasebev1 projesine gir
3. Backend servisini seç
4. **Settings** → **Domain** sekmesine git
5. Custom domain ekle: `api.tekstil-fatura.com`
6. SSL sertifikasını ve key'i yapıştır (Cloudflare'den kopyladığın)

---

## 🚀 AŞAMA 4: DNS KAYITLARINI AYARLA

### 4.1 DNS Kayıtları Ekle
Cloudflare Dashboard → **DNS** sekmesinde:

#### A Kaydı (Frontend)
```
Type: A
Name: @ (root domain)
Content: Frontend IP (Vercel, Netlify vb. IP)
TTL: Auto
Proxy: Proxied (Cloudflare turuncu bulut)
```

#### CNAME Kaydı (Backend API)
```
Type: CNAME
Name: api
Content: api.tekstil-fatura.com (veya Railway domain)
TTL: Auto
Proxy: Proxied (Cloudflare turuncu bulut)
```

#### MX Kayıtları (Email için)
```
Type: MX
Name: @
Mail server: smtp.sendgrid.net
Priority: 10
TTL: Auto
Proxy: DNS only (gri bulut)
```

**Not**: Mail kayıtları Cloudflare'den geçmemeli, doğrudan DNS'te olmalı!

---

## 🛡️ AŞAMA 5: WAF (WEB APPLICATION FIREWALL) KURALLARI

### 5.1 Managed Rules'u Etkinleştir
1. **Security** → **WAF** → **Managed Rules**
2. **Cloudflare Managed Ruleset** → Tümünü aç:
   ```
   ✅ Cloudflare Managed Baseline Rule
   ✅ Cloudflare Managed Sensitivity Control
   ✅ OWASP ModSecurity Core Rule Set
   ✅ Cloudflare Managed Threat Control
   ```

### 5.2 Custom WAF Kuralları

#### Kural 1: SQL Injection Saldırılarını Blok Et
```
Action: Block
Conditions:
  - URI Path contains: /api/
  - Query string contains: ' OR OR "OR "
```

#### Kural 2: XXE Saldırılarını Blok Et
```
Action: Block
Conditions:
  - Request body contains: <!DOCTYPE
  - Request body contains: <!ENTITY
  - Request body contains: SYSTEM
```

#### Kural 3: CRLF Injection Saldırılarını Blok Et
```
Action: Block
Conditions:
  - Query string contains: %0D%0A (CRLF)
  - Request headers contain: %0D%0A
```

**Cloudflare WAF UI'da kuralları bu şekilde ekleyebilirsin:**
1. **WAF** → **Custom Rules**
2. **Create rule**
3. İfadeleri yaz (expression builder kullan)
4. **Block** action seç
5. **Save**

---

## ⏱️ AŞAMA 6: RATE LIMITING

### 6.1 Rate Limiting Kuralları
1. **Security** → **Rate limiting**
2. **Create rate limit rule**

#### Kural 1: Login Endpoint Koruması
```
Threshold: 5 requests
Time period: 1 minute
Request property: IP
Actions: Block (for 15 minutes)
URL path: /api/v1/auth/login
```

#### Kural 2: Token Refresh Koruması
```
Threshold: 20 requests
Time period: 1 minute
Request property: IP
Actions: Block (for 10 minutes)
URL path: /api/v1/auth/refresh
```

#### Kural 3: Invoice Upload Koruması
```
Threshold: 10 requests
Time period: 1 minute
Request property: IP
Actions: Challenge (CAPTCHA)
URL path: /api/v1/invoices (POST only)
```

---

## 💾 AŞAMA 7: CACHING POLİTİKASI

### 7.1 Cache Rules
1. **Caching** → **Cache Rules**
2. **Create rule**

#### Kural 1: Health Check Endpoint
```
URL path: /api/v1/health
Caching level: Cache Everything
TTL: 5 minutes
```

#### Kural 2: Static Assets
```
File extension: .pdf, .jpg, .png, .css, .js
Caching level: Cache Everything
TTL: 1 hour
Browser cache TTL: 30 minutes
```

#### Kural 3: API Endpoints (No Cache)
```
URL path: /api/v1/invoices
Caching level: Bypass Cache
Reason: Dynamic content
```

---

## 🔒 AŞAMA 8: BACKEND GÜVENLİK BAŞLIKLARI

### 8.1 FastAPI'ye Security Headers Ekle

**Dosya: `backend/app/main.py`**

```python
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import time

# Mevcut lifespan decorator'dan sonra ekle:

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """HTTP security headers ekle"""
    response = await call_next(request)

    # XSS koruması
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"

    # HSTS (HTTP Strict Transport Security)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    # Content Security Policy
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"

    # Referrer Policy
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    # Permissions Policy
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

    return response


# CORS ayarlarını güncelle (Cloudflare ile):
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://tekstil-fatura.com",
        "https://www.tekstil-fatura.com",
    ],  # Production domains
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
    max_age=3600,
)
```

### 8.2 Değişiklikleri Commit Et
```bash
cd backend
git add app/main.py
git commit -m "Add security headers for Cloudflare integration"
git push origin main
```

---

## ✅ AŞAMA 9: TEST VE DOĞRULAMA

### 9.1 DNS Kontrol
```bash
# Terminal'de çalıştır:
nslookup tekstil-fatura.com
dig tekstil-fatura.com

# Çıktı şu olmalı:
# tekstil-fatura.com is proxied by Cloudflare (turuncu bulut)
```

### 9.2 SSL/TLS Kontrol
```bash
curl -I https://api.tekstil-fatura.com

# Beklenen:
# HTTP/2 200
# CF-RAY: header görmek gerekir
# Strict-Transport-Security header
```

### 9.3 WAF Kontrolü
1. Cloudflare Analytics → **Security**
2. WAF Events sekmesinde kurallar harekete geçiş görmeli
3. False positives varsa kuralları ayarla

### 9.4 Rate Limiting Kontrolü
```bash
# Hızlıca birden fazla login isteği gönder:
for i in {1..10}; do
  curl -X POST https://api.tekstil-fatura.com/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"email":"test@test.com","password":"password"}'
  echo "Request $i"
done

# 5. istekten sonra 429 Too Many Requests hatası almanız gerekir
```

### 9.5 Tarayıcı Kontrolü
1. Frontend'i aç: https://tekstil-fatura.com
2. DevTools → Network sekmesine bak
3. Her request için `CF-RAY` header'ı görmeli
4. `X-Content-Type-Options: nosniff` header'ı görmeli

---

## 📊 AŞAMA 10: MONITORING VE ANALYTICS

### 10.1 Cloudflare Analytics Dashboard
1. **Analytics & Logs** → **Overview**
2. İzle:
   ```
   - Requests: Günlük trafik
   - Bandwidth: Tasarruf oranı
   - Threats blocked: Blok edilen saldırılar
   - Cache status: Cache hit rate
   ```

### 10.2 Email Alerts Ayarla
1. **Notifications** → **Notification settings**
2. **Create** butonuna tıkla
3. Alert türü seç:
   ```
   - WAF Rule Triggered (önemli)
   - DDoS Attack (önemli)
   - SSL Certificate Expiration
   - High Error Rate (500+ errors)
   ```
4. Email adresini gir
5. Kaydet

### 10.3 Page Rules (İsteğe Bağlı)
1. **Rules** → **Page Rules**
2. Kurallar:
   ```
   URL: tekstil-fatura.com/admin/*
   Rule: Require authentication (Enable Enterprise feature)

   URL: tekstil-fatura.com/assets/*
   Rule: Cache Everything

   URL: api.tekstil-fatura.com/api/v1/*
   Rule: Bypass Cache
   ```

---

## 🚨 AŞAMA 11: CLOUDFLARE WORKERS (İLERİ - İsteğe Bağlı)

### 11.1 Custom Bot Management
Cloudflare Workers ile custom logik ekleyebilirsin:

```javascript
// workers/rate-limiter.js
addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
})

async function handleRequest(request) {
  const ip = request.headers.get('CF-Connecting-IP')
  const url = new URL(request.url)

  // Login endpoint'e özel kontrol
  if (url.pathname === '/api/v1/auth/login' && request.method === 'POST') {
    const count = await getRequestCount(ip)
    if (count > 5) {
      return new Response('Too many login attempts', { status: 429 })
    }
    await incrementRequestCount(ip)
  }

  return fetch(request)
}
```

Bu ileri seviye, başlangıçta gerekli değil.

---

## ✨ ÖZET CHECKLIST

- [ ] Cloudflare hesabı oluşturdum
- [ ] Domain adını Cloudflare'ye ekledim
- [ ] Nameserver'ları değiştirdim
- [ ] DNS yayılmasını bekledim (24 saat)
- [ ] SSL/TLS → Full (Strict) seçtim
- [ ] DNS kayıtlarını ekledim (A, CNAME, MX)
- [ ] WAF Managed Rules'ları açtım
- [ ] Custom WAF kuralları ekledim (SQL injection, XXE, CRLF)
- [ ] Rate limiting kuralları ekledim (login, refresh, upload)
- [ ] Cache kuralları ekledim
- [ ] Backend security headers'ları ekledim
- [ ] DNS kontrol ettim (nslookup, dig)
- [ ] SSL kontrol ettim (curl -I https://...)
- [ ] WAF events'i izlemedim
- [ ] Rate limiting'i test ettim
- [ ] Analytics dashboard'u açtım
- [ ] Email alerts'i ayarladım

---

## 🆘 TROUBLESHOOTING

### Problem: DNS propagation çok uzun sürüyor
**Çözüm**:
- TTL değerini 300 saniyeye düşür
- 24-48 saat bekle
- `whatsmydns.net`'te kontrol et

### Problem: Backend'e bağlanamıyorum
**Çözüm**:
- Origin Server SSL certificate'ini kontrol et
- Railway'de custom domain doğru ayarlanmış mı kontrol et
- Cloudflare → SSL/TLS → Origin Certificates kontrol et

### Problem: WAF çok katı, meşru istekler blok ediliyor
**Çözüm**:
- **WAF** → **Managed Rules** → **Sensitivity** düşür
- Specifik URL path'leri exclude et
- İP whitelist ekle

### Problem: Email'ler çalışmıyor
**Çözüm**:
- MX kayıtlarının proxy'si kapalı olmalı (gri bulut)
- SPF/DKIM kayıtlarını kontrol et
- SendGrid SMTP doğrudan kullan (Cloudflare'den geçmesin)

---

## 📞 DESTEK

- **Cloudflare Docs**: https://developers.cloudflare.com
- **Cloudflare Community**: https://community.cloudflare.com
- **Status Page**: https://www.cloudflarestatus.com

---

**✅ Kurulum tamamlandı! Sisteminiz artık Cloudflare ile korunmaktadır.**
