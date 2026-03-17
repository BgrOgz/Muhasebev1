FROM python:3.11-slim

WORKDIR /app

# Sistem bağımlılıkları (PyMuPDF + PostgreSQL için)
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    libmupdf-dev \
    mupdf-tools \
    && rm -rf /var/lib/apt/lists/*

# Python bağımlılıkları
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama kodu
COPY . .

# Non-root kullanıcı oluştur
RUN groupadd -r appuser && useradd -r -g appuser -d /app appuser

# Gerekli klasörler
RUN mkdir -p uploads archive && chown -R appuser:appuser /app

EXPOSE 8000

USER appuser

CMD ["/bin/sh", "-c", "python -m scripts.seed_admin || true && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
