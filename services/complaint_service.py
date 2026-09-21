"""Tenant complaint services for landlords."""
from __future__ import annotations

from typing import Any, Mapping
from sqlalchemy import select
from sqlalchemy.orm import Session
from database.models import Complaint, Property, RequestPriority, RequestStatus

FIELDS = {"assigned_to_id", "subject", "description", "priority", "status"}


def list_landlord_complaints(db: Session, landlord_id: str) -> list[Complaint]:
    return list(db.scalars(select(Complaint).join(Property).where(Property.owner_id == landlord_id).order_by(Complaint.created_at.desc())).all())


def get_complaint(db: Session, complaint_id: str, landlord_id: str) -> Complaint | None:
    return db.scalar(select(Complaint).join(Property).where(Complaint.id == complaint_id, Property.owner_id == landlord_id))


def create_complaint(db: Session, property_id: str, submitted_by_id: str, data: Mapping[str, Any]) -> Complaint:
    item = Complaint(property_id=property_id, submitted_by_id=submitted_by_id, **_values(data))
    try:
        db.add(item); db.commit(); db.refresh(item); return item
    except Exception:
        db.rollback(); raise


def update_complaint(db: Session, complaint_id: str, landlord_id: str, data: Mapping[str, Any]) -> Complaint | None:
    item = get_complaint(db, complaint_id, landlord_id)
    if item is None: return None
    for key, value in _values(data).items(): setattr(item, key, value)
    try:
        db.commit(); db.refresh(item); return item
    except Exception:
        db.rollback(); raise


def _values(data: Mapping[str, Any]) -> dict[str, Any]:
    values = {key: value for key, value in data.items() if key in FIELDS}
    if values.get("priority") and not isinstance(values["priority"], RequestPriority): values["priority"] = RequestPriority(values["priority"])
    if values.get("status") and not isinstance(values["status"], RequestStatus): values["status"] = RequestStatus(values["status"])
    return values
