"""
Pytest konfigürasyonu — test ortamı için çevre değişkenlerini ayarlar.
Gerçek .env olmadan testlerin çalışmasını sağlar.
"""

import os
import pytest

# Config yüklenmeden önce test değerlerini set et
os.environ.setdefault("APP_SECRET_KEY", "test-secret-key-32-chars-minimum!!")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test_db")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-key-32-chars-minimum!!!!")
os.environ.setdefault("GMAIL_SERVICE_EMAIL", "test@test.com")
os.environ.setdefault("GMAIL_APP_PASSWORD", "test-app-password")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-key")
os.environ.setdefault("SENDGRID_API_KEY", "SG.test-key")
os.environ.setdefault("FIRST_APPROVER_EMAIL", "approver@test.com")
os.environ.setdefault("FINAL_APPROVER_EMAIL", "patron@test.com")
