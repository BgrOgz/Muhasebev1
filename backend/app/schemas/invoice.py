"""Fatura endpoint şemaları"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SupplierOut(BaseModel):
    id: UUID
    name: str
    vat_number: Optional[str] = None
    contact_email: Optional[str] = None
    model_config = {"from_attributes": True}


class ClassificationOut(BaseModel):
    id: UUID
    category: str
    risk_level: str
    confidence_score: Decimal
    suggested_account: Optional[str] = None
    ai_notes: Optional[str] = None
    anomalies: Optional[list] = None
    ai_model_version: Optional[str] = None
    model_config = {"from_attributes": True}


class ApprovalOut(BaseModel):
    id: UUID
    approval_level: str
    status: str
    comments: Optional[str] = None
    approved_at: Optional[datetime] = None
    model_config = {"from_attributes": True}


class InvoiceListItem(BaseModel):
    id: UUID
    invoice_number: str
    supplier: SupplierOut
    amount: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    currency: str
    invoice_date: date
    due_date: Optional[date] = None
    status: str
    category: Optional[str] = None
    risk_level: Optional[str] = None
    created_at: datetime
    model_config = {"from_attributes": True}


class InvoiceDetail(InvoiceListItem):
    classification: Optional[ClassificationOut] = None
    approvals: list[ApprovalOut] = []
    source_email: Optional[str] = None
    source_filename: Optional[str] = None


class InvoiceUpdateRequest(BaseModel):
    category: Optional[str] = None
    notes: Optional[str] = None


class PaginatedResponse(BaseModel):
    status: str = "success"
    data: dict


class InvoiceFilters(BaseModel):
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)
    status: Optional[str] = None
    category: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    sort_by: str = "created_at"
    order: str = "desc"
