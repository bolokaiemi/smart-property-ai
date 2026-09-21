"""Maintenance request services."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping
from sqlalchemy import select
from sqlalchemy.orm import Session
from database.models import MaintenanceRequest, Property, RequestPriority, RequestStatus

FIELDS = {"unit_id", "assigned_to_id", "title", "description", "category", "priority", "status", "ai_summary"}


def list_landlord_maintenance_requests(db: Session, landlord_id: str) -> list[MaintenanceRequest]:
    statement = select(MaintenanceRequest).join(Property).where(Property.owner_id == landlord_id).order_by(MaintenanceRequest.created_at.desc())
    return list(db.scalars(statement).all())


def get_maintenance_request(db: Session, request_id: str, landlord_id: str) -> MaintenanceRequest | None:
    return db.scalar(select(MaintenanceRequest).join(Property).where(MaintenanceRequest.id == request_id, Property.owner_id == landlord_id))


def create_maintenance_request(db: Session, property_id: str, submitted_by_id: str, data: Mapping[str, Any]) -> MaintenanceRequest:
    item = MaintenanceRequest(property_id=property_id, submitted_by_id=submitted_by_id, **_values(data))
    try:
        db.add(item); db.commit(); db.refresh(item); return item
    except Exception:
        db.rollback(); raise


def update_maintenance_request(db: Session, request_id: str, landlord_id: str, data: Mapping[str, Any]) -> MaintenanceRequest | None:
    item = get_maintenance_request(db, request_id, landlord_id)
    if item is None: return None
    for key, value in _values(data).items(): setattr(item, key, value)
    if item.status in {RequestStatus.RESOLVED, RequestStatus.CLOSED}: item.resolved_at = datetime.now(timezone.utc)
    try:
        db.commit(); db.refresh(item); return item
    except Exception:
        db.rollback(); raise


def _values(data: Mapping[str, Any]) -> dict[str, Any]:
    values = {key: value for key, value in data.items() if key in FIELDS}
    if values.get("priority") and not isinstance(values["priority"], RequestPriority): values["priority"] = RequestPriority(values["priority"])
    if values.get("status") and not isinstance(values["status"], RequestStatus): values["status"] = RequestStatus(values["status"])
    return values
