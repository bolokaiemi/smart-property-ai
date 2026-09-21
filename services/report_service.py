"""Read-only landlord report generation from existing tables."""
from __future__ import annotations

from decimal import Decimal
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from database.models import Expense, Lease, LeaseStatus, MaintenanceRequest, Property, RequestStatus, Unit, UnitStatus


def landlord_portfolio_report(db: Session, landlord_id: str) -> dict[str, object]:
    property_ids = select(Property.id).where(Property.owner_id == landlord_id)
    properties = db.scalar(select(func.count()).select_from(Property).where(Property.owner_id == landlord_id)) or 0
    units = db.scalar(select(func.count()).select_from(Unit).where(Unit.property_id.in_(property_ids))) or 0
    occupied = db.scalar(select(func.count()).select_from(Unit).where(Unit.property_id.in_(property_ids), Unit.status == UnitStatus.OCCUPIED)) or 0
    active_leases = db.scalar(select(func.count()).select_from(Lease).where(Lease.landlord_id == landlord_id, Lease.status == LeaseStatus.ACTIVE)) or 0
    open_maintenance = db.scalar(select(func.count()).select_from(MaintenanceRequest).where(MaintenanceRequest.property_id.in_(property_ids), MaintenanceRequest.status.notin_([RequestStatus.RESOLVED, RequestStatus.CLOSED, RequestStatus.CANCELLED]))) or 0
    expenses = db.scalar(select(func.coalesce(func.sum(Expense.amount), 0)).where(Expense.property_id.in_(property_ids))) or 0
    occupancy_rate = round((occupied / units * 100), 2) if units else 0.0
    return {
        "properties": int(properties), "units": int(units), "occupied_units": int(occupied),
        "occupancy_rate": occupancy_rate, "active_leases": int(active_leases),
        "open_maintenance": int(open_maintenance), "total_expenses": Decimal(str(expenses)),
        "currency": "EUR",
    }


def property_expense_report(db: Session, landlord_id: str) -> list[dict[str, object]]:
    statement = select(Property.id, Property.name, func.coalesce(func.sum(Expense.amount), 0).label("total")).outerjoin(Expense, Expense.property_id == Property.id).where(Property.owner_id == landlord_id).group_by(Property.id, Property.name).order_by(Property.name)
    return [{"property_id": row.id, "property_name": row.name, "total_expenses": Decimal(str(row.total)), "currency": "EUR"} for row in db.execute(statement)]
