"""High-level landlord dashboard and tenant queries."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from database.models import Lease, LeaseStatus, MaintenanceRequest, Property, RentalApplication, RequestStatus, Unit, UnitStatus, User


def get_dashboard_statistics(db: Session, landlord_id: str) -> dict[str, int]:
    property_ids = select(Property.id).where(Property.owner_id == landlord_id)
    properties = db.scalar(select(func.count()).select_from(Property).where(Property.owner_id == landlord_id)) or 0
    units = db.scalar(select(func.count()).select_from(Unit).where(Unit.property_id.in_(property_ids))) or 0
    occupied = db.scalar(select(func.count()).select_from(Unit).where(Unit.property_id.in_(property_ids), Unit.status == UnitStatus.OCCUPIED)) or 0
    maintenance = db.scalar(select(func.count()).select_from(MaintenanceRequest).where(MaintenanceRequest.property_id.in_(property_ids), MaintenanceRequest.status.notin_([RequestStatus.RESOLVED, RequestStatus.CLOSED, RequestStatus.CANCELLED]))) or 0
    applications = db.scalar(select(func.count()).select_from(RentalApplication).where(RentalApplication.property_id.in_(property_ids))) or 0
    return {"properties": int(properties), "units": int(units), "occupied_units": int(occupied), "open_maintenance": int(maintenance), "pending_applications": int(applications), "unread_messages": 0}


def list_landlord_tenants(db: Session, landlord_id: str) -> list[User]:
    tenant_ids = select(Lease.tenant_id).where(Lease.landlord_id == landlord_id, Lease.status.in_([LeaseStatus.ACTIVE, LeaseStatus.EXPIRING])).distinct()
    return list(db.scalars(select(User).where(User.id.in_(tenant_ids)).order_by(User.full_name)).all())


def get_landlord_tenant(db: Session, landlord_id: str, tenant_id: str) -> User | None:
    permitted = select(Lease.id).where(Lease.landlord_id == landlord_id, Lease.tenant_id == tenant_id).exists()
    return db.scalar(select(User).where(User.id == tenant_id, permitted))
