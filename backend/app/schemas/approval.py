"""Onay endpoint şemaları"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class ApprovalActionRequest(BaseModel):
    status: str          # "approved" | "rejected"
    comments: Optional[str] = None
    reason_rejected: Optional[str] = None


class ApprovalListItem(BaseModel):
    id: UUID
    invoice: dict        # invoice_number, supplier, amount, status
    approval_level: str
    status: str
    created_at: datetime
    model_config = {"from_attributes": True}


class ApprovalDetail(BaseModel):
    id: UUID
    invoice_id: UUID
    approval_level: str
    status: str
    comments: Optional[str] = None
    reason_rejected: Optional[str] = None
    approved_at: Optional[datetime] = None
    next_step: Optional[str] = None
    notifications_sent: list[str] = []
    model_config = {"from_attributes": True}
