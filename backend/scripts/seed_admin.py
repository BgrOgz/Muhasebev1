"""
İlk admin kullanıcısını oluştur.

Kullanım:
  python -m scripts.seed_admin
  python -m scripts.seed_admin --email admin@firma.com --name "Yönetici" --password güçlü_şifre_123
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Proje kök dizinini Python path'e ekle
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.database import AsyncSessionLocal, engine
from app.models import Base, User
from app.utils.security import hash_password

from sqlalchemy import select


async def seed_admin(email: str, name: str, password: str) -> None:
    """Admin kullanıcı oluştur (yoksa)"""

    # Tabloları oluştur (development modunda)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        # Zaten var mı kontrol et
        result = await db.execute(select(User).where(User.email == email))
        existing = result.scalar_one_or_none()

        if existing:
            print(f"⚠️  Kullanıcı zaten mevcut: {email} (rol: {existing.role})")
            if existing.role != "admin":
                existing.role = "admin"
                existing.is_active = True
                await db.commit()
                print(f"   → Rol 'admin' olarak güncellendi ✓")
            return

        # Yeni admin oluştur
        admin_user = User(
            email=email,
            name=name,
            password_hash=hash_password(password),
            role="admin",
            department="Yönetim",
            is_active=True,
        )
        db.add(admin_user)
        await db.commit()
        print(f"✅ Admin kullanıcı oluşturuldu!")
        print(f"   E-posta : {email}")
        print(f"   İsim    : {name}")
        print(f"   Rol     : admin")
        print(f"   ID      : {admin_user.id}")


def main():
    parser = argparse.ArgumentParser(description="İlk admin kullanıcısını oluştur")
    parser.add_argument("--email", default="admin@firma.com", help="Admin e-posta adresi")
    parser.add_argument("--name", default="Sistem Yöneticisi", help="Admin adı")
    parser.add_argument("--password", default="admin123456", help="Admin şifresi (en az 8 karakter)")

    args = parser.parse_args()

    if len(args.password) < 8:
        print("❌ Şifre en az 8 karakter olmalıdır!")
        sys.exit(1)

    print(f"\n🔧 Seed: Admin kullanıcı oluşturuluyor...")
    print(f"   DB: {settings.DATABASE_URL[:40]}...\n")

    asyncio.run(seed_admin(args.email, args.name, args.password))
    print()


if __name__ == "__main__":
    main()
