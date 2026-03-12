"""Rapor endpoint şemaları"""

from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel


class ReportFilters(BaseModel):
    start_date: date
    end_date: date


class CategorySummary(BaseModel):
    category: str
    count: int
    amount: Decimal
    percentage: float


class SupplierSummary(BaseModel):
    supplier_name: str
    count: int
    amount: Decimal


class SummaryReport(BaseModel):
    period: dict
    summary: dict
    by_category: list[CategorySummary]
    by_supplier: list[SupplierSummary]
    processing_time: dict
