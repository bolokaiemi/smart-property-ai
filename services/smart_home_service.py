"""Smart-device registration and user-confirmed action records."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Mapping
from sqlalchemy import select
from sqlalchemy.orm import Session
from database.models import DeviceAction, DeviceStatus, Property, SmartDevice

DEVICE_FIELDS = {"unit_id", "name", "device_type", "provider", "external_device_id", "status"}


def list_landlord_devices(db: Session, landlord_id: str) -> list[SmartDevice]:
    return list(db.scalars(select(SmartDevice).join(Property).where(Property.owner_id == landlord_id).order_by(SmartDevice.created_at.desc())).all())


def get_device(db: Session, device_id: str, landlord_id: str) -> SmartDevice | None:
    return db.scalar(select(SmartDevice).join(Property).where(SmartDevice.id == device_id, Property.owner_id == landlord_id))


def register_device(db: Session, property_id: str, landlord_id: str, data: Mapping[str, Any]) -> SmartDevice:
    owner = db.scalar(select(Property.id).where(Property.id == property_id, Property.owner_id == landlord_id))
    if owner is None: raise ValueError("Property not found or access denied.")
    values = {key: value for key, value in data.items() if key in DEVICE_FIELDS}
    if values.get("status") and not isinstance(values["status"], DeviceStatus): values["status"] = DeviceStatus(values["status"])
    item = SmartDevice(property_id=property_id, registered_by_id=landlord_id, **values)
    try:
        db.add(item); db.commit(); db.refresh(item); return item
    except Exception:
        db.rollback(); raise


def record_device_action(db: Session, device_id: str, landlord_id: str, action_name: str, parameters: Mapping[str, Any] | None, confirmed: bool) -> DeviceAction:
    if get_device(db, device_id, landlord_id) is None: raise ValueError("Device not found or access denied.")
    if not confirmed: raise ValueError("Smart-home actions require explicit user confirmation.")
    action = DeviceAction(device_id=device_id, requested_by_id=landlord_id, action_name=action_name, action_parameters=json.dumps(parameters or {}), confirmed_by_user=True)
    try:
        db.add(action); db.commit(); db.refresh(action); return action
    except Exception:
        db.rollback(); raise


def mark_device_seen(db: Session, device_id: str, landlord_id: str) -> SmartDevice | None:
    item = get_device(db, device_id, landlord_id)
    if item is None: return None
    item.last_seen_at = datetime.now(timezone.utc); item.status = DeviceStatus.ACTIVE
    try:
        db.commit(); db.refresh(item); return item
    except Exception:
        db.rollback(); raise
