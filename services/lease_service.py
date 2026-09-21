"""Lease management services."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Mapping
from sqlalchemy import select
from sqlalchemy.orm import Session
from database.models import Lease, LeaseStatus

FIELDS = {
    "property_id", "unit_id", "tenant_id", "start_date", "end_date",
    "monthly_rent", "deposit_amount", "currency", "payment_due_day",
    "renewal_reminder_days", "status",
}


def list_landlord_leases(db: Session, landlord_id: str) -> list[Lease]:
    return list(db.scalars(select(Lease).where(Lease.landlord_id == landlord_id).order_by(Lease.created_at.desc())).all())


def get_lease(db: Session, lease_id: str, landlord_id: str) -> Lease | None:
    return db.scalar(select(Lease).where(Lease.id == lease_id, Lease.landlord_id == landlord_id))


def create_lease(db: Session, landlord_id: str, data: Mapping[str, Any]) -> Lease:
    item = Lease(landlord_id=landlord_id, **_values(data))
    try:
        db.add(item); db.commit(); db.refresh(item); return item
    except Exception:
        db.rollback(); raise


def update_lease(db: Session, lease_id: str, landlord_id: str, data: Mapping[str, Any]) -> Lease | None:
    item = get_lease(db, lease_id, landlord_id)
    if item is None: return None
    for key, value in _values(data).items(): setattr(item, key, value)
    try:
        db.commit(); db.refresh(item); return item
    except Exception:
        db.rollback(); raise


def end_lease(db: Session, lease_id: str, landlord_id: str, ended_on: date | None = None) -> Lease | None:
    item = get_lease(db, lease_id, landlord_id)
    if item is None: return None
    item.status = LeaseStatus.ENDED
    item.end_date = ended_on or date.today()
    try:
        db.commit(); db.refresh(item); return item
    except Exception:
        db.rollback(); raise


def _values(data: Mapping[str, Any]) -> dict[str, Any]:
    values = {key: value for key, value in data.items() if key in FIELDS}
    for key in ("monthly_rent", "deposit_amount"):
        if key in values and values[key] not in (None, ""): values[key] = Decimal(str(values[key]))
    for key in ("start_date", "end_date"):
        if key in values and isinstance(values[key], str) and values[key]: values[key] = date.fromisoformat(values[key])
    if values.get("status") and not isinstance(values["status"], LeaseStatus): values["status"] = LeaseStatus(values["status"])
    return values
