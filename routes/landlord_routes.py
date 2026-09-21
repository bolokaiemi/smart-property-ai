"""Complete landlord portal routes for Smart Property AI."""
from __future__ import annotations

import hashlib
import secrets
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile

from database.database import get_db
from database.models import (
    Appointment,
    AuditLog,
    Complaint,
    DeviceStatus,
    Document,
    DocumentType,
    Expense,
    Lease,
    LeaseStatus,
    MaintenanceRequest,
    Message,
    Notification,
    Payment,
    Property,
    RentalApplication,
    RequestPriority,
    RequestStatus,
    SmartDevice,
    Unit,
    UnitStatus,
    User,
    UserRole,
    ViewingAppointment,
)
from services.property_service import (
    PropertyData,
    PropertyService,
    PropertyServiceError,
    PropertyValidationError,
)


router = APIRouter(prefix="/landlord", tags=["Landlord"])
templates = Jinja2Templates(directory="templates")

UPLOAD_ROOT = Path("uploads/documents")
MAX_DOCUMENT_SIZE = 10 * 1024 * 1024
ALLOWED_DOCUMENT_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".doc", ".docx"}


# ---------------------------------------------------------------------------
# Shared security and rendering helpers
# ---------------------------------------------------------------------------

def _session_user_id(request: Request) -> str | None:
    return request.session.get("user_id")


def _require_landlord(request: Request, db: Session) -> User | Response:
    user_id = _session_user_id(request)
    if not user_id:
        next_url = quote(request.url.path, safe="/")
        return RedirectResponse(f"/login?next={next_url}", status_code=303)

    user = db.get(User, user_id)
    if user is None:
        request.session.clear()
        return RedirectResponse("/login?reason=session_expired", status_code=303)

    allowed_roles = {UserRole.LANDLORD, UserRole.PROPERTY_MANAGER, UserRole.ADMINISTRATOR}
    if user.role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Landlord access is required.")
    return user


def _csrf_token(request: Request) -> str:
    token = request.session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf_token"] = token
    return str(token)


def _verify_csrf(request: Request, submitted: Any) -> None:
    expected = str(request.session.get("csrf_token") or "")
    supplied = str(submitted or "")
    if not expected or not supplied or not secrets.compare_digest(expected, supplied):
        raise HTTPException(status_code=403, detail="The security token is missing or invalid.")


def _context(request: Request, user: User, **values: Any) -> dict[str, Any]:
    context = {
        "request": request,
        "current_user": user,
        "user": user,
        "is_authenticated": True,
        "current_language": request.session.get("language", user.preferred_language or "en"),
        "csrf_token": _csrf_token(request),
        "success": request.query_params.get("success"),
        "error": request.query_params.get("error"),
    }
    context.update(values)
    return context


def _render(request: Request, user: User, template: str, **values: Any) -> Response:
    return templates.TemplateResponse(
        request=request,
        name=template,
        context=_context(request, user, **values),
    )


def _redirect(request: Request, route_name: str, message: str | None = None, **path: Any) -> RedirectResponse:
    url = str(request.url_for(route_name, **path))
    if message:
        url = f"{url}?{urlencode({'success': message})}"
    return RedirectResponse(url, status_code=status.HTTP_303_SEE_OTHER)


def _property_ids(db: Session, user: User):
    query = select(Property.id)
    if user.role == UserRole.ADMINISTRATOR:
        return query
    if user.role == UserRole.PROPERTY_MANAGER:
        return query.where(Property.manager_id == user.id)
    return query.where(Property.owner_id == user.id)


def _manageable_property(db: Session, user: User, property_id: str) -> Property:
    query = select(Property).where(Property.id == property_id)
    if user.role == UserRole.LANDLORD:
        query = query.where(Property.owner_id == user.id)
    elif user.role == UserRole.PROPERTY_MANAGER:
        query = query.where(Property.manager_id == user.id)
    item = db.scalar(query)
    if item is None:
        raise HTTPException(status_code=404, detail="Property not found.")
    return item


def _decimal(value: Any, field: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise HTTPException(status_code=422, detail=f"{field} must be a valid number.") from error


def _date(value: Any, field: str, required: bool = True) -> date | None:
    if value in (None, "") and not required:
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError as error:
        raise HTTPException(status_code=422, detail=f"{field} must be a valid date.") from error


def _commit(db: Session, item: Any) -> Any:
    try:
        db.add(item)
        db.commit()
        db.refresh(item)
        return item
    except Exception:
        db.rollback()
        raise


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@router.get("", name="landlord_home", include_in_schema=False)
async def landlord_home() -> RedirectResponse:
    return RedirectResponse("/landlord/dashboard", status_code=303)


@router.get("dashboard", name="landlord_dashboard")
async def landlord_dashboard(request: Request, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    ids = _property_ids(db, user)
    properties = db.scalar(select(func.count()).select_from(Property).where(Property.id.in_(ids))) or 0
    units = db.scalar(select(func.count()).select_from(Unit).where(Unit.property_id.in_(ids))) or 0
    occupied = db.scalar(select(func.count()).select_from(Unit).where(Unit.property_id.in_(ids), Unit.status == UnitStatus.OCCUPIED)) or 0
    maintenance = db.scalar(select(func.count()).select_from(MaintenanceRequest).where(MaintenanceRequest.property_id.in_(ids), MaintenanceRequest.status.notin_([RequestStatus.RESOLVED, RequestStatus.CLOSED, RequestStatus.CANCELLED]))) or 0
    applications = db.scalar(select(func.count()).select_from(RentalApplication).where(RentalApplication.property_id.in_(ids))) or 0
    unread = db.scalar(select(func.count()).select_from(Message).where(Message.recipient_id == user.id, Message.read_at.is_(None))) or 0
    statistics = {"properties": int(properties), "units": int(units), "occupied_units": int(occupied), "open_maintenance": int(maintenance), "pending_applications": int(applications), "unread_messages": int(unread)}

    audit_records = list(db.scalars(select(AuditLog).where(AuditLog.user_id == user.id).order_by(AuditLog.created_at.desc()).limit(8)).all())
    recent_activity = [{"id": row.id, "title": row.action.replace(".", " ").replace("_", " ").title(), "description": row.details or "Landlord portal activity", "created_at": row.created_at} for row in audit_records]

    appointments = list(db.scalars(select(ViewingAppointment).where(ViewingAppointment.property_id.in_(ids), ViewingAppointment.preferred_datetime >= datetime.now(timezone.utc)).order_by(ViewingAppointment.preferred_datetime).limit(6)).all())
    upcoming = [{"id": row.id, "title": "Property viewing", "scheduled_for": row.preferred_datetime, "status": row.status, "property_id": row.property_id} for row in appointments]
    return _render(request, user, "landlord/dashboard.html", page_title="Landlord Dashboard", statistics=statistics, recent_activity=recent_activity, upcoming_appointments=upcoming)


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------

@router.get("/properties", name="properties_page")
async def properties_page(request: Request, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    service = PropertyService(db)
    properties = service.list_properties(user, search=request.query_params.get("search"))
    return _render(request, user, "landlord/properties.html", page_title="Properties", properties=properties)


@router.get("/properties/add", name="add_property_page")
async def add_property_page(request: Request, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    return _render(request, user, "landlord/add_property.html", page_title="Add Property", form_data={}, errors={})


@router.post("/properties/add", name="create_property_action")
async def create_property_action(request: Request, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    form = await request.form(); _verify_csrf(request, form.get("csrf_token"))
    data = PropertyData(name=str(form.get("name", "")), property_type=str(form.get("property_type", "")), street_address=str(form.get("street_address", "")), postal_code=str(form.get("postal_code", "")), city=str(form.get("city", "")), country=str(form.get("country", "Germany")), state=str(form.get("state", "")) or None, description=str(form.get("description", "")) or None, latitude=form.get("latitude"), longitude=form.get("longitude"))
    try:
        item = PropertyService(db).create_property(user, data, request)
    except PropertyValidationError as error:
        return _render(request, user, "landlord/add_property.html", page_title="Add Property", form_data=dict(form), errors={"property": " ".join(error.errors)})
    except PropertyServiceError as error:
        return _render(request, user, "landlord/add_property.html", page_title="Add Property", form_data=dict(form), errors={"property": str(error)})
    return _redirect(request, "property_details_page", "Property created.", property_id=item.id)


@router.get("/properties/{property_id}/edit", name="edit_property_page")
async def edit_property_page(request: Request, property_id: str, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    item = PropertyService(db).get_manageable_property(user, property_id)
    return _render(request, user, "landlord/edit_property.html", page_title="Edit Property", property=item, property_id=property_id, form_data=item.__dict__, errors={})


@router.post("/properties/{property_id}/edit", name="update_property_action")
async def update_property_action(request: Request, property_id: str, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    form = await request.form(); _verify_csrf(request, form.get("csrf_token"))
    data = PropertyData(name=str(form.get("name", "")), property_type=str(form.get("property_type", "")), street_address=str(form.get("street_address", "")), postal_code=str(form.get("postal_code", "")), city=str(form.get("city", "")), country=str(form.get("country", "Germany")), state=str(form.get("state", "")) or None, description=str(form.get("description", "")) or None, latitude=form.get("latitude"), longitude=form.get("longitude"))
    try:
        PropertyService(db).update_property(user, property_id, data, request)
    except PropertyValidationError as error:
        return _render(request, user, "landlord/edit_property.html", page_title="Edit Property", property_id=property_id, form_data=dict(form), errors={"property": " ".join(error.errors)})
    return _redirect(request, "property_details_page", "Property updated.", property_id=property_id)


@router.get("/properties/{property_id}", name="property_details_page")
async def property_details_page(request: Request, property_id: str, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    service = PropertyService(db); item = service.get_accessible_property(user, property_id)
    stats = service.get_property_statistics(user, property_id)
    units = list(db.scalars(select(Unit).where(Unit.property_id == property_id).order_by(Unit.unit_number)).all())
    return _render(request, user, "landlord/property_details.html", page_title="Property Details", property=item, units=units, statistics=stats)


# ---------------------------------------------------------------------------
# Units
# ---------------------------------------------------------------------------

@router.get("/properties/{property_id}/units", name="units_page")
async def units_page(request: Request, property_id: str, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    prop = _manageable_property(db, user, property_id)
    units = list(db.scalars(select(Unit).where(Unit.property_id == property_id).order_by(Unit.unit_number)).all())
    return _render(request, user, "landlord/units.html", page_title="Units", property=prop, property_id=property_id, units=units)


@router.get("/properties/{property_id}/units/add", name="add_unit_page")
async def add_unit_page(request: Request, property_id: str, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    _manageable_property(db, user, property_id)
    return _render(request, user, "landlord/add_unit.html", page_title="Add Unit", property_id=property_id, form_data={}, errors={})


@router.post("/properties/{property_id}/units/add", name="create_unit_action")
async def create_unit_action(request: Request, property_id: str, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    _manageable_property(db, user, property_id); form = await request.form(); _verify_csrf(request, form.get("csrf_token"))
    item = Unit(property_id=property_id, unit_number=str(form.get("unit_number", "")).strip(), floor=str(form.get("floor", "")) or None, rooms=_decimal(form.get("rooms"), "Rooms"), bedrooms=int(form.get("bedrooms") or 0), bathrooms=int(form.get("bathrooms") or 1), area_square_metres=_decimal(form.get("area_square_metres"), "Area") if form.get("area_square_metres") else None, monthly_rent=_decimal(form.get("monthly_rent"), "Monthly rent"), deposit_amount=_decimal(form.get("deposit_amount"), "Deposit") if form.get("deposit_amount") else None, currency=str(form.get("currency") or "EUR").upper(), wheelchair_accessible=form.get("wheelchair_accessible") == "true", pets_allowed=form.get("pets_allowed") == "true", status=UnitStatus.VACANT)
    _commit(db, item)
    return _redirect(request, "unit_details_page", "Unit created.", unit_id=item.id)


def _owned_unit(db: Session, user: User, unit_id: str) -> Unit:
    item = db.scalar(select(Unit).where(Unit.id == unit_id, Unit.property_id.in_(_property_ids(db, user))))
    if item is None: raise HTTPException(status_code=404, detail="Unit not found.")
    return item


@router.get("/units/{unit_id}/edit", name="edit_unit_page")
async def edit_unit_page(request: Request, unit_id: str, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    item = _owned_unit(db, user, unit_id)
    return _render(request, user, "landlord/edit_unit.html", page_title="Edit Unit", unit=item, unit_id=unit_id, property_id=item.property_id, form_data=item.__dict__, errors={})


@router.post("/units/{unit_id}/edit", name="update_unit_action")
async def update_unit_action(request: Request, unit_id: str, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    item = _owned_unit(db, user, unit_id); form = await request.form(); _verify_csrf(request, form.get("csrf_token"))
    item.unit_number = str(form.get("unit_number", item.unit_number)).strip(); item.floor = str(form.get("floor", "")) or None
    item.rooms = _decimal(form.get("rooms"), "Rooms"); item.bedrooms = int(form.get("bedrooms") or 0); item.bathrooms = int(form.get("bathrooms") or 1)
    item.area_square_metres = _decimal(form.get("area_square_metres"), "Area") if form.get("area_square_metres") else None; item.monthly_rent = _decimal(form.get("monthly_rent"), "Monthly rent"); item.deposit_amount = _decimal(form.get("deposit_amount"), "Deposit") if form.get("deposit_amount") else None
    item.currency = str(form.get("currency") or "EUR").upper(); item.wheelchair_accessible = form.get("wheelchair_accessible") == "true"; item.pets_allowed = form.get("pets_allowed") == "true"
    _commit(db, item)
    return _redirect(request, "unit_details_page", "Unit updated.", unit_id=unit_id)


@router.get("/units/{unit_id}", name="unit_details_page")
async def unit_details_page(request: Request, unit_id: str, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    return _render(request, user, "landlord/unit_details.html", page_title="Unit Details", unit=_owned_unit(db, user, unit_id))


# ---------------------------------------------------------------------------
# Tenants and leases
# ---------------------------------------------------------------------------

@router.get("/tenants", name="landlord_tenants_page")
async def landlord_tenants_page(request: Request, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    tenant_ids = select(Lease.tenant_id).where(Lease.landlord_id == user.id).distinct()
    tenants = list(db.scalars(select(User).where(User.id.in_(tenant_ids)).order_by(User.full_name)).all())
    return _render(request, user, "landlord/tenants.html", page_title="Tenants", tenants=tenants)


@router.get("/tenants/{tenant_id}", name="landlord_tenant_details_page")
async def landlord_tenant_details_page(request: Request, tenant_id: str, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    permitted = select(Lease.id).where(Lease.landlord_id == user.id, Lease.tenant_id == tenant_id).exists()
    tenant = db.scalar(select(User).where(User.id == tenant_id, permitted))
    if tenant is None: raise HTTPException(status_code=404, detail="Tenant not found.")
    leases = list(db.scalars(select(Lease).where(Lease.landlord_id == user.id, Lease.tenant_id == tenant_id).order_by(Lease.created_at.desc())).all())
    return _render(request, user, "landlord/tenant_details.html", page_title="Tenant Details", tenant=tenant, leases=leases)


@router.get("/leases", name="landlord_leases_page")
async def landlord_leases_page(request: Request, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    leases = list(db.scalars(select(Lease).where(Lease.landlord_id == user.id).order_by(Lease.created_at.desc())).all())
    return _render(request, user, "landlord/leases.html", page_title="Leases", leases=leases)


@router.get("/leases/add", name="add_lease_page")
async def add_lease_page(request: Request, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    return _render(request, user, "landlord/add_lease.html", page_title="Add Lease", form_data={}, errors={})


@router.post("/leases/add", name="create_lease_action")
async def create_lease_action(request: Request, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    form = await request.form(); _verify_csrf(request, form.get("csrf_token")); prop = _manageable_property(db, user, str(form.get("property_id")))
    unit = _owned_unit(db, user, str(form.get("unit_id")))
    if unit.property_id != prop.id: raise HTTPException(status_code=422, detail="Unit does not belong to the selected property.")
    item = Lease(property_id=prop.id, unit_id=unit.id, tenant_id=str(form.get("tenant_id")), landlord_id=user.id, start_date=_date(form.get("start_date"), "Start date"), end_date=_date(form.get("end_date"), "End date", False), monthly_rent=_decimal(form.get("monthly_rent"), "Monthly rent"), deposit_amount=_decimal(form.get("deposit_amount"), "Deposit") if form.get("deposit_amount") else None, currency=str(form.get("currency") or "EUR").upper(), payment_due_day=int(form.get("payment_due_day") or 1), renewal_reminder_days=int(form.get("renewal_reminder_days") or 60), status=LeaseStatus.DRAFT)
    _commit(db, item); return _redirect(request, "landlord_lease_details_page", "Lease created.", lease_id=item.id)


def _owned_lease(db: Session, user: User, lease_id: str) -> Lease:
    query = select(Lease).where(Lease.id == lease_id)
    if user.role != UserRole.ADMINISTRATOR: query = query.where(Lease.landlord_id == user.id)
    item = db.scalar(query)
    if item is None: raise HTTPException(status_code=404, detail="Lease not found.")
    return item


@router.get("/leases/{lease_id}/edit", name="edit_lease_page")
async def edit_lease_page(request: Request, lease_id: str, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    item = _owned_lease(db, user, lease_id)
    return _render(request, user, "landlord/edit_lease.html", page_title="Edit Lease", lease=item, lease_id=lease_id, form_data=item.__dict__, errors={})


@router.post("/leases/{lease_id}/edit", name="update_lease_action")
async def update_lease_action(request: Request, lease_id: str, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    item = _owned_lease(db, user, lease_id); form = await request.form(); _verify_csrf(request, form.get("csrf_token"))
    item.start_date = _date(form.get("start_date"), "Start date"); item.end_date = _date(form.get("end_date"), "End date", False); item.monthly_rent = _decimal(form.get("monthly_rent"), "Monthly rent"); item.deposit_amount = _decimal(form.get("deposit_amount"), "Deposit") if form.get("deposit_amount") else None; item.currency = str(form.get("currency") or "EUR").upper(); item.payment_due_day = int(form.get("payment_due_day") or 1); item.renewal_reminder_days = int(form.get("renewal_reminder_days") or 60)
    _commit(db, item); return _redirect(request, "landlord_lease_details_page", "Lease updated.", lease_id=lease_id)


@router.get("/leases/{lease_id}", name="landlord_lease_details_page")
async def landlord_lease_details_page(request: Request, lease_id: str, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    return _render(request, user, "landlord/lease_details.html", page_title="Lease Details", lease=_owned_lease(db, user, lease_id))


# ---------------------------------------------------------------------------
# Generic record lists and details
# ---------------------------------------------------------------------------

@router.get("/applications", name="landlord_applications_page")
async def landlord_applications_page(request: Request, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    rows = list(db.scalars(select(RentalApplication).where(RentalApplication.property_id.in_(_property_ids(db, user))).order_by(RentalApplication.created_at.desc())).all())
    return _render(request, user, "landlord/applications.html", page_title="Applications", applications=rows)


@router.get("/applications/{application_id}", name="landlord_application_details_page")
async def landlord_application_details_page(request: Request, application_id: str, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    item = db.scalar(select(RentalApplication).where(RentalApplication.id == application_id, RentalApplication.property_id.in_(_property_ids(db, user))))
    if item is None: raise HTTPException(404, "Application not found.")
    return _render(request, user, "landlord/application_details.html", page_title="Application Details", application=item)


@router.get("/appointments", name="landlord_appointments_page")
async def landlord_appointments_page(request: Request, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    rows = list(db.scalars(select(ViewingAppointment).where(ViewingAppointment.property_id.in_(_property_ids(db, user))).order_by(ViewingAppointment.preferred_datetime.desc())).all())
    return _render(request, user, "landlord/appointments.html", page_title="Appointments", appointments=rows)


@router.get("/appointments/{appointment_id}", name="landlord_appointment_details_page")
async def landlord_appointment_details_page(request: Request, appointment_id: str, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    item = db.scalar(select(ViewingAppointment).where(ViewingAppointment.id == appointment_id, ViewingAppointment.property_id.in_(_property_ids(db, user))))
    if item is None: raise HTTPException(404, "Appointment not found.")
    return _render(request, user, "landlord/appointment_details.html", page_title="Appointment Details", appointment=item)


@router.get("/maintenance", name="landlord_maintenance_page")
async def landlord_maintenance_page(request: Request, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    rows = list(db.scalars(select(MaintenanceRequest).where(MaintenanceRequest.property_id.in_(_property_ids(db, user))).order_by(MaintenanceRequest.created_at.desc())).all())
    return _render(request, user, "landlord/maintenance_requests.html", page_title="Maintenance Requests", maintenance_requests=rows)


@router.get("/maintenance/{request_id}", name="landlord_maintenance_details_page")
async def landlord_maintenance_details_page(request: Request, request_id: str, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    item = db.scalar(select(MaintenanceRequest).where(MaintenanceRequest.id == request_id, MaintenanceRequest.property_id.in_(_property_ids(db, user))))
    if item is None: raise HTTPException(404, "Maintenance request not found.")
    return _render(request, user, "landlord/maintenance_request_details.html", page_title="Maintenance Request Details", maintenance_request=item)


@router.get("/complaints", name="landlord_complaints_page")
async def landlord_complaints_page(request: Request, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    rows = list(db.scalars(select(Complaint).where(Complaint.property_id.in_(_property_ids(db, user))).order_by(Complaint.created_at.desc())).all())
    return _render(request, user, "landlord/complaints.html", page_title="Complaints", complaints=rows)


@router.get("/complaints/{complaint_id}", name="landlord_complaint_details_page")
async def landlord_complaint_details_page(request: Request, complaint_id: str, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    item = db.scalar(select(Complaint).where(Complaint.id == complaint_id, Complaint.property_id.in_(_property_ids(db, user))))
    if item is None: raise HTTPException(404, "Complaint not found.")
    return _render(request, user, "landlord/complaint_details.html", page_title="Complaint Details", complaint=item)


@router.get("/payments", name="landlord_payments_page")
async def landlord_payments_page(request: Request, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    lease_ids = select(Lease.id).where(Lease.landlord_id == user.id)
    rows = list(db.scalars(select(Payment).where(Payment.lease_id.in_(lease_ids)).order_by(Payment.due_date.desc())).all())
    return _render(request, user, "landlord/payments.html", page_title="Payments", payments=rows)


@router.get("/payments/{payment_id}", name="landlord_payment_details_page")
async def landlord_payment_details_page(request: Request, payment_id: str, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    item = db.scalar(select(Payment).join(Lease).where(Payment.id == payment_id, Lease.landlord_id == user.id))
    if item is None: raise HTTPException(404, "Payment not found.")
    return _render(request, user, "landlord/payment_details.html", page_title="Payment Details", payment=item)


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

@router.get("/documents", name="landlord_documents_page")
async def landlord_documents_page(request: Request, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    rows = list(db.scalars(select(Document).where(or_(Document.uploaded_by_id == user.id, Document.property_id.in_(_property_ids(db, user)))).order_by(Document.created_at.desc())).all())
    return _render(request, user, "landlord/documents.html", page_title="Documents", documents=rows)


@router.get("/documents/upload", name="upload_landlord_document_page")
async def upload_landlord_document_page(request: Request, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    return _render(request, user, "landlord/upload_document.html", page_title="Upload Document", form_data={}, errors={})


@router.post("/documents/upload", name="upload_landlord_document_action")
async def upload_landlord_document_action(request: Request, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    form = await request.form(); _verify_csrf(request, form.get("csrf_token")); upload = form.get("file")
    if not isinstance(upload, UploadFile) or not upload.filename: raise HTTPException(422, "Please select a document.")
    extension = Path(upload.filename).suffix.lower()
    if extension not in ALLOWED_DOCUMENT_EXTENSIONS: raise HTTPException(422, "Unsupported document type.")
    content = await upload.read(MAX_DOCUMENT_SIZE + 1)
    if len(content) > MAX_DOCUMENT_SIZE: raise HTTPException(413, "Document exceeds the 10 MB limit.")
    property_id = str(form.get("property_id") or "") or None
    if property_id: _manageable_property(db, user, property_id)
    stored_name = f"{secrets.token_hex(16)}{extension}"; UPLOAD_ROOT.mkdir(parents=True, exist_ok=True); storage_path = UPLOAD_ROOT / stored_name; storage_path.write_bytes(content)
    checksum = hashlib.sha256(content).hexdigest()
    try: document_type = DocumentType(str(form.get("document_type") or "other"))
    except ValueError: document_type = DocumentType.OTHER
    item = Document(uploaded_by_id=user.id, property_id=property_id, document_type=document_type, original_filename=Path(upload.filename).name, stored_filename=stored_name, storage_path=str(storage_path), mime_type=upload.content_type or "application/octet-stream", file_size=len(content), checksum=checksum, is_private=form.get("is_private") == "true")
    _commit(db, item); return _redirect(request, "landlord_document_details_page", "Document uploaded.", document_id=item.id)


@router.get("/documents/{document_id}", name="landlord_document_details_page")
async def landlord_document_details_page(request: Request, document_id: str, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    item = db.scalar(select(Document).where(Document.id == document_id, or_(Document.uploaded_by_id == user.id, Document.property_id.in_(_property_ids(db, user)))))
    if item is None: raise HTTPException(404, "Document not found.")
    return _render(request, user, "landlord/document_details.html", page_title="Document Details", document=item)


# ---------------------------------------------------------------------------
# Expenses and reports
# ---------------------------------------------------------------------------

@router.get("/expenses", name="landlord_expenses_page")
async def landlord_expenses_page(request: Request, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    rows = list(db.scalars(select(Expense).where(Expense.property_id.in_(_property_ids(db, user))).order_by(Expense.expense_date.desc())).all())
    return _render(request, user, "landlord/expenses.html", page_title="Expenses", expenses=rows)


@router.get("/expenses/add", name="add_expense_page")
async def add_expense_page(request: Request, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    return _render(request, user, "landlord/add_expense.html", page_title="Add Expense", form_data={}, errors={})


@router.post("/expenses/add", name="create_expense_action")
async def create_expense_action(request: Request, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    form = await request.form(); _verify_csrf(request, form.get("csrf_token")); prop = _manageable_property(db, user, str(form.get("property_id")))
    item = Expense(property_id=prop.id, maintenance_request_id=str(form.get("maintenance_request_id") or "") or None, recorded_by_id=user.id, category=str(form.get("category", "")).strip(), description=str(form.get("description", "")).strip(), amount=_decimal(form.get("amount"), "Amount"), currency=str(form.get("currency") or "EUR").upper(), expense_date=_date(form.get("expense_date"), "Expense date"))
    _commit(db, item); return _redirect(request, "landlord_expense_details_page", "Expense recorded.", expense_id=item.id)


@router.get("/expenses/{expense_id}", name="landlord_expense_details_page")
async def landlord_expense_details_page(request: Request, expense_id: str, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    item = db.scalar(select(Expense).where(Expense.id == expense_id, Expense.property_id.in_(_property_ids(db, user))))
    if item is None: raise HTTPException(404, "Expense not found.")
    return _render(request, user, "landlord/expense_details.html", page_title="Expense Details", expense=item)


@router.get("/reports", name="landlord_reports_page")
async def landlord_reports_page(request: Request, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    reports = [{"id": "portfolio", "title": "Portfolio summary", "period": "Current", "created_at": datetime.now(timezone.utc)}, {"id": "expenses", "title": "Property expenses", "period": "All time", "created_at": datetime.now(timezone.utc)}]
    return _render(request, user, "landlord/reports.html", page_title="Reports", reports=reports)


@router.get("/reports/{report_id}", name="landlord_report_details_page")
async def landlord_report_details_page(request: Request, report_id: str, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    ids = _property_ids(db, user)
    if report_id == "expenses":
        total = db.scalar(select(func.coalesce(func.sum(Expense.amount), 0)).where(Expense.property_id.in_(ids))) or 0
        report = {"title": "Property expenses", "period": "All time", "summary": f"Total recorded expenses: {total} EUR", "created_at": datetime.now(timezone.utc)}
    else:
        total = db.scalar(select(func.count()).select_from(Property).where(Property.id.in_(ids))) or 0
        report = {"title": "Portfolio summary", "period": "Current", "summary": f"Managed properties: {total}", "created_at": datetime.now(timezone.utc)}
    return _render(request, user, "landlord/report_details.html", page_title="Report Details", report=report)


# ---------------------------------------------------------------------------
# Messages, notifications, smart devices and settings
# ---------------------------------------------------------------------------

@router.get("/messages", name="landlord_messages_page")
async def landlord_messages_page(request: Request, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    rows = list(db.scalars(select(Message).where(or_(Message.sender_id == user.id, Message.recipient_id == user.id)).order_by(Message.created_at.desc())).all())
    return _render(request, user, "landlord/messages.html", page_title="Messages", messages=rows)


@router.get("/messages/{message_id}", name="landlord_message_details_page")
async def landlord_message_details_page(request: Request, message_id: str, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    item = db.scalar(select(Message).where(Message.id == message_id, or_(Message.sender_id == user.id, Message.recipient_id == user.id)))
    if item is None: raise HTTPException(404, "Message not found.")
    if item.recipient_id == user.id and item.read_at is None: item.read_at = datetime.now(timezone.utc); _commit(db, item)
    return _render(request, user, "landlord/message_details.html", page_title="Message Details", message=item)


@router.get("/notifications", name="landlord_notifications_page")
async def landlord_notifications_page(request: Request, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    rows = list(db.scalars(select(Notification).where(Notification.user_id == user.id).order_by(Notification.created_at.desc())).all())
    return _render(request, user, "landlord/notifications.html", page_title="Notifications", notifications=rows)


@router.get("/smart-devices", name="landlord_smart_devices_page")
async def landlord_smart_devices_page(request: Request, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    rows = list(db.scalars(select(SmartDevice).where(SmartDevice.property_id.in_(_property_ids(db, user))).order_by(SmartDevice.created_at.desc())).all())
    return _render(request, user, "landlord/smart_devices.html", page_title="Smart Devices", smart_devices=rows)


@router.get("/smart-devices/add", name="add_smart_device_page")
async def add_smart_device_page(request: Request, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    return _render(request, user, "landlord/add_smart_device.html", page_title="Add Smart Device", form_data={}, errors={})


@router.post("/smart-devices/add", name="create_smart_device_action")
async def create_smart_device_action(request: Request, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    form = await request.form(); _verify_csrf(request, form.get("csrf_token")); prop = _manageable_property(db, user, str(form.get("property_id")))
    item = SmartDevice(property_id=prop.id, unit_id=str(form.get("unit_id") or "") or None, registered_by_id=user.id, name=str(form.get("name", "")).strip(), device_type=str(form.get("device_type", "")).strip(), provider=str(form.get("provider", "")) or None, external_device_id=str(form.get("external_device_id", "")) or None, status=DeviceStatus.PENDING)
    _commit(db, item); return _redirect(request, "landlord_smart_device_details_page", "Smart device added.", device_id=item.id)


@router.get("/smart-devices/{device_id}", name="landlord_smart_device_details_page")
async def landlord_smart_device_details_page(request: Request, device_id: str, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    item = db.scalar(select(SmartDevice).where(SmartDevice.id == device_id, SmartDevice.property_id.in_(_property_ids(db, user))))
    if item is None: raise HTTPException(404, "Smart device not found.")
    return _render(request, user, "landlord/smart_device_details.html", page_title="Smart Device Details", smart_device=item)


@router.get("/settings", name="landlord_settings_page")
async def landlord_settings_page(request: Request, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    return _render(request, user, "landlord/settings.html", page_title="Landlord Settings", settings={}, form_data={}, errors={})


@router.post("/settings", name="update_landlord_settings_action")
async def update_landlord_settings_action(request: Request, db: Session = Depends(get_db)) -> Response:
    user = _require_landlord(request, db)
    if isinstance(user, Response): return user
    form = await request.form(); _verify_csrf(request, form.get("csrf_token"))
    name = str(form.get("display_name", "")).strip(); language = str(form.get("language") or "en").lower()
    if name: user.full_name = name[:150]
    if language in {"en", "de", "fr", "es"}: user.preferred_language = language; request.session["language"] = language
    _commit(db, user)
    return _redirect(request, "landlord_settings_page", "Settings updated.")
