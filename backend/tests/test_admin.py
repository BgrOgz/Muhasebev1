"""
Admin panel endpoint testleri
Çalıştır: pytest tests/test_admin.py -v
"""

import pytest
from pydantic import ValidationError

from app.schemas.admin import (
    UserCreateRequest,
    UserUpdateRequest,
    SupplierUpdateRequest,
    UserResponse,
    SupplierResponse,
    AuditLogResponse,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  UserCreateRequest validasyon testleri
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestUserCreateRequest:

    def test_valid_user(self):
        u = UserCreateRequest(
            email="test@firma.com",
            name="Test Kullanıcı",
            password="guvenli_sifre_123",
            role="approver",
            department="Muhasebe",
        )
        assert u.email == "test@firma.com"
        assert u.role == "approver"

    def test_default_role_is_viewer(self):
        u = UserCreateRequest(
            email="viewer@firma.com",
            name="Viewer",
            password="guvenli_sifre_123",
        )
        assert u.role == "viewer"

    def test_invalid_role_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            UserCreateRequest(
                email="x@test.com",
                name="X",
                password="12345678",
                role="superadmin",
            )
        assert "Geçersiz rol" in str(exc_info.value)

    def test_short_password_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            UserCreateRequest(
                email="x@test.com",
                name="X",
                password="123",
            )
        assert "en az 8 karakter" in str(exc_info.value)

    def test_invalid_email_raises(self):
        with pytest.raises(ValidationError):
            UserCreateRequest(
                email="gecersiz-email",
                name="X",
                password="12345678",
            )

    def test_all_roles_accepted(self):
        for role in ("admin", "approver", "viewer"):
            u = UserCreateRequest(
                email=f"{role}@test.com",
                name=role,
                password="12345678",
                role=role,
            )
            assert u.role == role


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  UserUpdateRequest validasyon testleri
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestUserUpdateRequest:

    def test_partial_update_name_only(self):
        u = UserUpdateRequest(name="Yeni İsim")
        assert u.name == "Yeni İsim"
        assert u.role is None
        assert u.is_active is None

    def test_partial_update_role(self):
        u = UserUpdateRequest(role="admin")
        assert u.role == "admin"

    def test_invalid_role_update_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            UserUpdateRequest(role="hacker")
        assert "Geçersiz rol" in str(exc_info.value)

    def test_deactivate_user(self):
        u = UserUpdateRequest(is_active=False)
        assert u.is_active is False

    def test_empty_update_allowed(self):
        """Hiçbir alan verilmezse hata olmamalı"""
        u = UserUpdateRequest()
        assert u.name is None
        assert u.role is None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SupplierUpdateRequest validasyon testleri
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestSupplierUpdateRequest:

    def test_partial_update(self):
        s = SupplierUpdateRequest(name="Yeni Tedarikçi", city="İstanbul")
        assert s.name == "Yeni Tedarikçi"
        assert s.city == "İstanbul"
        assert s.vat_number is None  # gönderilmedi

    def test_full_update(self):
        s = SupplierUpdateRequest(
            name="ABC Tekstil",
            vat_number="1234567890",
            address="Organize Sanayi Bölgesi No:12",
            city="Bursa",
            country="Turkey",
            contact_email="info@abc.com",
            contact_phone="+90 555 123 4567",
        )
        assert s.vat_number == "1234567890"
        assert s.contact_phone == "+90 555 123 4567"

    def test_empty_update_allowed(self):
        s = SupplierUpdateRequest()
        assert s.name is None

    def test_model_dump_exclude_unset(self):
        """Sadece gönderilen alanlar döndürülmeli"""
        s = SupplierUpdateRequest(name="Test")
        dumped = s.model_dump(exclude_unset=True)
        assert "name" in dumped
        assert "city" not in dumped
        assert len(dumped) == 1


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Response modeli testleri
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestResponseModels:

    def test_user_response_from_dict(self):
        data = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "email": "admin@test.com",
            "name": "Admin",
            "role": "admin",
            "is_active": True,
            "created_at": "2025-01-01T00:00:00",
        }
        r = UserResponse(**data)
        assert r.email == "admin@test.com"
        assert r.department is None  # opsiyonel

    def test_supplier_response_defaults(self):
        data = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "name": "Test Supplier",
            "country": "Turkey",
            "created_at": "2025-01-01T00:00:00",
        }
        r = SupplierResponse(**data)
        assert r.invoice_count == 0
        assert r.total_amount == 0.0
        assert r.vat_number is None

    def test_audit_log_response(self):
        data = {
            "id": "550e8400-e29b-41d4-a716-446655440000",
            "action": "admin.user_created",
            "status": "success",
            "new_values": {"email": "new@test.com"},
            "created_at": "2025-01-01T00:00:00",
        }
        r = AuditLogResponse(**data)
        assert r.action == "admin.user_created"
        assert r.invoice_id is None
        assert r.user_name is None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Router düzeyinde testler (import + yapılandırma kontrolü)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestAdminRouterConfig:

    def test_router_import(self):
        """Admin router başarıyla import edilmeli"""
        from app.routers.admin import router
        assert router.prefix == "/admin"
        assert "Admin" in router.tags

    def test_router_has_all_endpoints(self):
        """Tüm beklenen endpoint path'leri var mı?"""
        from app.routers.admin import router

        paths = [route.path for route in router.routes]
        # Router prefix "/admin" path'lere dahil ediliyor
        assert "/admin/users" in paths
        assert "/admin/users/{user_id}" in paths
        assert "/admin/suppliers" in paths
        assert "/admin/suppliers/{supplier_id}" in paths
        assert "/admin/audit-logs" in paths
        assert "/admin/audit-logs/export" in paths

    def test_router_requires_admin_role(self):
        """Router seviyesinde admin dependency olmalı"""
        from app.routers.admin import router
        # dependencies listesinde require_role("admin") bulunmalı
        assert len(router.dependencies) > 0

    def test_main_includes_admin_router(self):
        """main.py admin router'ı kaydetmiş olmalı"""
        from app.main import app

        route_paths = [route.path for route in app.routes]
        # /api/v1/admin/users yolunun varlığını kontrol et
        admin_paths = [p for p in route_paths if "/admin/" in p]
        assert len(admin_paths) >= 6, f"Beklenen 6+ admin path, bulunan: {admin_paths}"
