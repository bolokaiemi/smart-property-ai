"""Maintenance and property expense tracking."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Mapping
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from database.models import Expense, Property

FIELDS = {"maintenance_request_id", "category", "description", "amount", "currency", "expense_date"}


def list_landlord_expenses(db: Session, landlord_id: str, property_id: str | None = None) -> list[Expense]:
    statement = select(Expense).join(Property).where(Property.owner_id == landlord_id)
    if property_id: statement = statement.where(Expense.property_id == property_id)
    return list(db.scalars(statement.order_by(Expense.expense_date.desc())).all())


def get_expense(db: Session, expense_id: str, landlord_id: str) -> Expense | None:
    return db.scalar(select(Expense).join(Property).where(Expense.id == expense_id, Property.owner_id == landlord_id))


def create_expense(db: Session, property_id: str, landlord_id: str, data: Mapping[str, Any]) -> Expense:
    owner = db.scalar(select(Property.id).where(Property.id == property_id, Property.owner_id == landlord_id))
    if owner is None: raise ValueError("Property not found or access denied.")
    values = {key: value for key, value in data.items() if key in FIELDS}
    values["amount"] = Decimal(str(values["amount"]))
    if isinstance(values.get("expense_date"), str): values["expense_date"] = date.fromisoformat(values["expense_date"])
    item = Expense(property_id=property_id, recorded_by_id=landlord_id, **values)
    try:
        db.add(item); db.commit(); db.refresh(item); return item
    except Exception:
        db.rollback(); raise


def delete_expense(db: Session, expense_id: str, landlord_id: str) -> bool:
    item = get_expense(db, expense_id, landlord_id)
    if item is None: return False
    try:
        db.delete(item); db.commit(); return True
    except Exception:
        db.rollback(); raise


def expense_total(db: Session, landlord_id: str, property_id: str | None = None) -> Decimal:
    statement = select(func.coalesce(func.sum(Expense.amount), 0)).join(Property).where(Property.owner_id == landlord_id)
    if property_id: statement = statement.where(Expense.property_id == property_id)
    return Decimal(str(db.scalar(statement) or 0))
