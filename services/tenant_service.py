"""
Tenant portal business services.

File:
    services/tenant_service.py

This module handles tenant-authorized database operations for:
- Dashboard statistics
- Leases
- Payments and rent status
- Maintenance requests
- Complaints
- Documents
- Messages
- Appointments
- Notifications
- Tenant profile
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, desc, func, or_
from sqlalchemy.orm import Session

from database.models import (
    AccountStatus,
    Appointment,
    AppointmentStatus,
    Complaint,
    Document,
    Lease,
    LeaseStatus,
    MaintenanceRequest,
    Message,
    Notification,
    Payment,
    PaymentStatus,
    Property,
    RequestPriority,
    RequestStatus,
    TenantProfile,
    Unit,
    User,
    UserRole,
)


class TenantServiceError(Exception):
    """Base tenant-service exception."""


class TenantNotFoundError(TenantServiceError):
    """Raised when a tenant account cannot be found."""


class TenantPermissionError(TenantServiceError):
    """Raised when a user is not authorized as a tenant."""


class TenantResourceNotFoundError(TenantServiceError):
    """Raised when a tenant resource cannot be found."""


class TenantValidationError(TenantServiceError):
    """Raised when submitted tenant data is invalid."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def clean_text(
    value: Any,
    *,
    field_name: str,
    required: bool = False,
    maximum_length: int | None = None,
) -> str | None:
    cleaned = str(value or "").strip()

    if required and not cleaned:
        raise TenantValidationError(
            f"{field_name} is required."
        )

    if maximum_length and len(cleaned) > maximum_length:
        raise TenantValidationError(
            f"{field_name} cannot exceed "
            f"{maximum_length} characters."
        )

    return cleaned or None


def enum_value(value: Any) -> str | None:
    if value is None:
        return None

    return str(getattr(value, "value", value))


def serialize_datetime(value: Any) -> str | None:
    if value is None:
        return None

    if hasattr(value, "isoformat"):
        return value.isoformat()

    return str(value)


def serialize_decimal(value: Any) -> float | None:
    if value is None:
        return None

    return float(value)


# ============================================================
# Tenant authorization
# ============================================================


def get_tenant_user(
    db: Session,
    user_id: str,
) -> User:
    """Return and validate an active tenant user."""

    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if user is None:
        raise TenantNotFoundError(
            "Tenant account not found."
        )

    if user.status != AccountStatus.ACTIVE:
        raise TenantPermissionError(
            "This tenant account is not active."
        )

    allowed_roles = {
        UserRole.TENANT,
        UserRole.ADMINISTRATOR,
    }

    if user.role not in allowed_roles:
        raise TenantPermissionError(
            "Tenant access is required."
        )

    return user


def get_tenant_profile(
    db: Session,
    tenant_id: str,
) -> TenantProfile | None:
    """Return a tenant's profile when one exists."""

    return (
        db.query(TenantProfile)
        .filter(TenantProfile.user_id == tenant_id)
        .first()
    )


# ============================================================
# Leases
# ============================================================


def list_tenant_leases(
    db: Session,
    tenant_id: str,
    *,
    include_ended: bool = True,
) -> list[Lease]:
    """Return leases belonging to one tenant."""

    get_tenant_user(db, tenant_id)

    query = (
        db.query(Lease)
        .filter(Lease.tenant_id == tenant_id)
    )

    if not include_ended:
        query = query.filter(
            Lease.status.in_(
                [
                    LeaseStatus.ACTIVE,
                    LeaseStatus.EXPIRING,
                ]
            )
        )

    return query.order_by(
        desc(Lease.start_date)
    ).all()


def get_active_lease(
    db: Session,
    tenant_id: str,
) -> Lease | None:
    """Return the tenant's most recent active lease."""

    get_tenant_user(db, tenant_id)

    return (
        db.query(Lease)
        .filter(
            Lease.tenant_id == tenant_id,
            Lease.status.in_(
                [
                    LeaseStatus.ACTIVE,
                    LeaseStatus.EXPIRING,
                ]
            ),
        )
        .order_by(desc(Lease.start_date))
        .first()
    )


def get_tenant_lease(
    db: Session,
    tenant_id: str,
    lease_id: str,
) -> Lease:
    """Return one lease only when it belongs to the tenant."""

    get_tenant_user(db, tenant_id)

    lease = (
        db.query(Lease)
        .filter(
            Lease.id == lease_id,
            Lease.tenant_id == tenant_id,
        )
        .first()
    )

    if lease is None:
        raise TenantResourceNotFoundError(
            "Lease not found."
        )

    return lease


def get_lease_property(
    db: Session,
    lease: Lease,
) -> Property | None:
    return (
        db.query(Property)
        .filter(Property.id == lease.property_id)
        .first()
    )


def get_lease_unit(
    db: Session,
    lease: Lease,
) -> Unit | None:
    return (
        db.query(Unit)
        .filter(Unit.id == lease.unit_id)
        .first()
    )


def tenant_property_ids(
    db: Session,
    tenant_id: str,
) -> list[str]:
    """Return property IDs connected to the tenant's leases."""

    rows = (
        db.query(Lease.property_id)
        .filter(Lease.tenant_id == tenant_id)
        .distinct()
        .all()
    )

    return [
        row[0]
        for row in rows
        if row[0] is not None
    ]


def tenant_unit_ids(
    db: Session,
    tenant_id: str,
) -> list[str]:
    """Return unit IDs connected to the tenant's leases."""

    rows = (
        db.query(Lease.unit_id)
        .filter(Lease.tenant_id == tenant_id)
        .distinct()
        .all()
    )

    return [
        row[0]
        for row in rows
        if row[0] is not None
    ]


def tenant_has_property_access(
    db: Session,
    tenant_id: str,
    property_id: str,
    unit_id: str | None = None,
) -> bool:
    """Check whether a property or unit belongs to the tenant's lease."""

    query = db.query(Lease.id).filter(
        Lease.tenant_id == tenant_id,
        Lease.property_id == property_id,
    )

    if unit_id is not None:
        query = query.filter(
            Lease.unit_id == unit_id
        )

    return query.first() is not None


# ============================================================
# Payments
# ============================================================


def list_tenant_payments(
    db: Session,
    tenant_id: str,
    *,
    lease_id: str | None = None,
    limit: int | None = None,
) -> list[Payment]:
    """Return rent payments belonging to a tenant."""

    get_tenant_user(db, tenant_id)

    query = db.query(Payment).filter(
        Payment.tenant_id == tenant_id
    )

    if lease_id is not None:
        get_tenant_lease(
            db,
            tenant_id,
            lease_id,
        )

        query = query.filter(
            Payment.lease_id == lease_id
        )

    query = query.order_by(
        desc(Payment.due_date)
    )

    if limit is not None:
        limit = max(1, min(int(limit), 100))
        query = query.limit(limit)

    return query.all()


def get_tenant_payment(
    db: Session,
    tenant_id: str,
    payment_id: str,
) -> Payment:
    """Return one payment belonging to a tenant."""

    get_tenant_user(db, tenant_id)

    payment = (
        db.query(Payment)
        .filter(
            Payment.id == payment_id,
            Payment.tenant_id == tenant_id,
        )
        .first()
    )

    if payment is None:
        raise TenantResourceNotFoundError(
            "Payment record not found."
        )

    return payment


def payment_summary(
    db: Session,
    tenant_id: str,
) -> dict[str, Any]:
    """Return summarized tenant payment information."""

    payments = list_tenant_payments(
        db,
        tenant_id,
    )

    paid_total = Decimal("0.00")
    outstanding_total = Decimal("0.00")
    overdue_total = Decimal("0.00")
    overdue_count = 0
    next_payment = None

    for payment in payments:
        amount = payment.amount or Decimal("0.00")

        if payment.status == PaymentStatus.PAID:
            paid_total += amount

        elif payment.status == PaymentStatus.OVERDUE:
            overdue_total += amount
            outstanding_total += amount
            overdue_count += 1

        elif payment.status in {
            PaymentStatus.PENDING,
            PaymentStatus.PARTIALLY_PAID,
            PaymentStatus.FAILED,
        }:
            outstanding_total += amount

        if payment.status in {
            PaymentStatus.PENDING,
            PaymentStatus.PARTIALLY_PAID,
        }:
            if (
                next_payment is None
                or payment.due_date < next_payment.due_date
            ):
                next_payment = payment

    return {
        "paid_total": float(paid_total),
        "outstanding_total": float(outstanding_total),
        "overdue_total": float(overdue_total),
        "overdue_count": overdue_count,
        "next_payment": next_payment,
        "currency": (
            payments[0].currency
            if payments
            else "EUR"
        ),
   }


# ============================================================
# Maintenance requests
# ============================================================


def list_maintenance_requests(
    db: Session,
    tenant_id: str,
    *,
    include_closed: bool = True,
    limit: int | None = None,
) -> list[MaintenanceRequest]:
    """Return maintenance requests submitted by a tenant."""

    get_tenant_user(db, tenant_id)

    query = db.query(MaintenanceRequest).filter(
        MaintenanceRequest.submitted_by_id == tenant_id
    )

    if not include_closed:
        query = query.filter(
            MaintenanceRequest.status.notin_(
                [
                    RequestStatus.RESOLVED,
                    RequestStatus.CLOSED,
                    RequestStatus.CANCELLED,
                ]
            )
        )

    query = query.order_by(
        desc(MaintenanceRequest.created_at)
    )

    if limit is not None:
        limit = max(1, min(int(limit), 100))
        query = query.limit(limit)

    return query.all()


def get_maintenance_request(
    db: Session,
    tenant_id: str,
    request_id: str,
) -> MaintenanceRequest:
    """Return a tenant-owned maintenance request."""

    get_tenant_user(db, tenant_id)

    maintenance_request = (
        db.query(MaintenanceRequest)
        .filter(
            MaintenanceRequest.id == request_id,
            MaintenanceRequest.submitted_by_id
            == tenant_id,
        )
        .first()
    )

    if maintenance_request is None:
        raise TenantResourceNotFoundError(
            "Maintenance request not found."
        )

    return maintenance_request


def create_maintenance_request(
    db: Session,
    *,
    tenant_id: str,
    property_id: str,
    unit_id: str | None,
    title: str,
    description: str,
    category: str | None,
    priority: str = "normal",
) -> MaintenanceRequest:
    """Create a maintenance request for a tenant's property."""

    get_tenant_user(db, tenant_id)

    if not tenant_has_property_access(
        db,
        tenant_id,
        property_id,
        unit_id,
    ):
        raise TenantPermissionError(
            "You do not have access to this property or unit."
        )

    try:
        selected_priority = RequestPriority(priority)
    except ValueError as exc:
        raise TenantValidationError(
            "Select a valid maintenance priority."
        ) from exc

    request_title = clean_text(
        title,
        field_name="Title",
        required=True,
        maximum_length=200,
    )

    request_description = clean_text(
        description,
        field_name="Description",
        required=True,
        maximum_length=5000,
    )

    request_category = clean_text(
        category,
        field_name="Category",
        maximum_length=100,
    )

    maintenance_request = MaintenanceRequest(
        property_id=property_id,
        unit_id=unit_id,
        submitted_by_id=tenant_id,
        assigned_to_id=None,
        title=request_title,
        description=request_description,
        category=request_category,
        priority=selected_priority,
        status=RequestStatus.OPEN,
        ai_summary=None,
        resolved_at=None,
        created_at=utc_now(),
        updated_at=utc_now(),
    )

    try:
        db.add(maintenance_request)
        db.commit()
        db.refresh(maintenance_request)
    except Exception:
        db.rollback()
        raise

    return maintenance_request


def cancel_maintenance_request(
    db: Session,
    *,
    tenant_id: str,
    request_id: str,
) -> MaintenanceRequest:
    """Cancel an unresolved tenant maintenance request."""

    maintenance_request = get_maintenance_request(
        db,
        tenant_id,
        request_id,
    )

    if maintenance_request.status in {
        RequestStatus.RESOLVED,
        RequestStatus.CLOSED,
        RequestStatus.CANCELLED,
    }:
        raise TenantValidationError(
            "This maintenance request cannot be cancelled."
        )

    maintenance_request.status = RequestStatus.CANCELLED
    maintenance_request.updated_at = utc_now()

    try:
        db.commit()
        db.refresh(maintenance_request)
    except Exception:
        db.rollback()
        raise

    return maintenance_request


# ============================================================
# Complaints
# ============================================================


def list_complaints(
    db: Session,
    tenant_id: str,
    *,
    include_closed: bool = True,
    limit: int | None = None,
) -> list[Complaint]:
    """Return complaints submitted by a tenant."""

    get_tenant_user(db, tenant_id)

    query = db.query(Complaint).filter(
        Complaint.submitted_by_id == tenant_id
    )

    if not include_closed:
        query = query.filter(
            Complaint.status.notin_(
                [
                    RequestStatus.RESOLVED,
                    RequestStatus.CLOSED,
                    RequestStatus.CANCELLED,
                ]
            )
        )

    query = query.order_by(
        desc(Complaint.created_at)
    )

    if limit is not None:
        limit = max(1, min(int(limit), 100))
        query = query.limit(limit)

    return query.all()


def get_complaint(
    db: Session,
    tenant_id: str,
    complaint_id: str,
) -> Complaint:
    """Return one tenant-owned complaint."""

    get_tenant_user(db, tenant_id)

    complaint = (
        db.query(Complaint)
        .filter(
            Complaint.id == complaint_id,
            Complaint.submitted_by_id == tenant_id,
        )
        .first()
    )

    if complaint is None:
        raise TenantResourceNotFoundError(
            "Complaint not found."
        )

    return complaint


def create_complaint(
    db: Session,
    *,
    tenant_id: str,
    property_id: str,
    subject: str,
    description: str,
    priority: str = "normal",
) -> Complaint:
    """Create a complaint for a tenant's property."""

    get_tenant_user(db, tenant_id)

    if not tenant_has_property_access(
        db,
        tenant_id,
        property_id,
    ):
        raise TenantPermissionError(
            "You do not have access to this property."
        )

    try:
        selected_priority = RequestPriority(priority)
    except ValueError as exc:
        raise TenantValidationError(
            "Select a valid complaint priority."
        ) from exc

    complaint = Complaint(
        property_id=property_id,
        submitted_by_id=tenant_id,
        assigned_to_id=None,
        subject=clean_text(
            subject,
            field_name="Subject",
            required=True,
            maximum_length=200,
        ),
        description=clean_text(
            description,
            field_name="Description",
            required=True,
            maximum_length=5000,
        ),
        priority=selected_priority,
        status=RequestStatus.OPEN,
        created_at=utc_now(),
        updated_at=utc_now(),
    )

    try:
        db.add(complaint)
        db.commit()
        db.refresh(complaint)
    except Exception:
        db.rollback()
        raise

    return complaint


# ============================================================
# Documents
# ============================================================


def list_tenant_documents(
    db: Session,
    tenant_id: str,
    *,
    limit: int | None = None,
) -> list[Document]:
    """
    Return documents connected to the tenant.

    Documents are accessible when uploaded by the tenant or connected
    to one of the tenant's leases or properties.
    """

    get_tenant_user(db, tenant_id)

    leases = list_tenant_leases(
        db,
        tenant_id,
    )

    lease_ids = [lease.id for lease in leases]
    property_ids = [
        lease.property_id
        for lease in leases
    ]

    access_filters = [
        Document.uploaded_by_id == tenant_id
    ]

    if lease_ids:
        access_filters.append(
            Document.lease_id.in_(lease_ids)
        )

    if property_ids:
        access_filters.append(
            Document.property_id.in_(property_ids)
        )

    query = (
        db.query(Document)
        .filter(or_(*access_filters))
        .order_by(desc(Document.created_at))
    )

    if limit is not None:
        limit = max(1, min(int(limit), 100))
        query = query.limit(limit)

    return query.all()


def get_tenant_document(
    db: Session,
    tenant_id: str,
    document_id: str,
) -> Document:
    """Return one document if it is accessible to the tenant."""

    documents = list_tenant_documents(
        db,
        tenant_id,
    )

    document = next(
        (
            item
            for item in documents
            if item.id == document_id
        ),
        None,
    )

    if document is None:
        raise TenantResourceNotFoundError(
            "Document not found."
        )

    return document


# ============================================================
# Messages
# ============================================================


def list_tenant_messages(
    db: Session,
    tenant_id: str,
    *,
    limit: int | None = None,
) -> list[Message]:
    """Return messages sent or received by the tenant."""

    get_tenant_user(db, tenant_id)

    query = (
        db.query(Message)
        .filter(
            or_(
                Message.sender_id == tenant_id,
                Message.recipient_id == tenant_id,
            )
        )
        .order_by(desc(Message.created_at))
    )

    if limit is not None:
        limit = max(1, min(int(limit), 100))
        query = query.limit(limit)

    return query.all()


def get_tenant_message(
    db: Session,
    tenant_id: str,
    message_id: str,
) -> Message:
    """Return one message involving the tenant."""

    get_tenant_user(db, tenant_id)

    message = (
        db.query(Message)
        .filter(
            Message.id == message_id,
            or_(
                Message.sender_id == tenant_id,
                Message.recipient_id == tenant_id,
            ),
        )
        .first()
    )

    if message is None:
        raise TenantResourceNotFoundError(
            "Message not found."
        )

    return message


def mark_message_read(
    db: Session,
    *,
    tenant_id: str,
    message_id: str,
) -> Message:
    """Mark a received tenant message as read."""

    message = get_tenant_message(
        db,
        tenant_id,
        message_id,
    )

    if message.recipient_id != tenant_id:
        raise TenantPermissionError(
            "Only the recipient can mark this message as read."
        )

    if message.read_at is None:
        message.read_at = utc_now()

        try:
            db.commit()
            db.refresh(message)
        except Exception:
            db.rollback()
            raise

    return message


# ============================================================
# Appointments
# ============================================================


def list_tenant_appointments(
    db: Session,
    tenant_id: str,
    *,
    upcoming_only: bool = False,
    limit: int | None = None,
) -> list[Appointment]:
    """Return appointments requested by the tenant."""

    get_tenant_user(db, tenant_id)

    query = db.query(Appointment).filter(
        Appointment.requested_by_id == tenant_id
    )

    if upcoming_only:
        query = query.filter(
            Appointment.scheduled_at >= utc_now(),
            Appointment.status.in_(
                [
                    AppointmentStatus.REQUESTED,
                    AppointmentStatus.CONFIRMED,
                ]
            ),
        )

    query = query.order_by(
        desc(Appointment.scheduled_at)
    )

    if limit is not None:
        limit = max(1, min(int(limit), 100))
        query = query.limit(limit)

    return query.all()


def get_tenant_appointment(
    db: Session,
    tenant_id: str,
    appointment_id: str,
) -> Appointment:
    """Return one tenant-owned appointment."""

    get_tenant_user(db, tenant_id)

    appointment = (
        db.query(Appointment)
        .filter(
            Appointment.id == appointment_id,
            Appointment.requested_by_id == tenant_id,
        )
        .first()
    )

    if appointment is None:
        raise TenantResourceNotFoundError(
            "Appointment not found."
        )

    return appointment


# ============================================================
# Notifications
# ============================================================


def list_tenant_notifications(
    db: Session,
    tenant_id: str,
    *,
    unread_only: bool = False,
    limit: int = 20,
) -> list[Notification]:
    """Return tenant notifications."""

    get_tenant_user(db, tenant_id)

    query = db.query(Notification).filter(
        Notification.user_id == tenant_id
    )

    if unread_only:
        query = query.filter(
            Notification.is_read.is_(False)
        )

    return (
        query.order_by(
            desc(Notification.created_at)
        )
        .limit(max(1, min(int(limit), 100)))
        .all()
    )


def mark_notification_read(
    db: Session,
    *,
    tenant_id: str,
    notification_id: str,
) -> Notification:
    """Mark one tenant notification as read."""

    notification = (
        db.query(Notification)
        .filter(
            Notification.id == notification_id,
            Notification.user_id == tenant_id,
        )
        .first()
    )

    if notification is None:
        raise TenantResourceNotFoundError(
            "Notification not found."
        )

    notification.is_read = True

    try:
        db.commit()
        db.refresh(notification)
    except Exception:
        db.rollback()
        raise

    return notification


# ============================================================
# Tenant profile
# ============================================================


def update_tenant_profile(
    db: Session,
    *,
    tenant_id: str,
    emergency_contact_name: str | None,
    emergency_contact_phone: str | None,
    accessibility_requirements: str | None,
) -> TenantProfile:
    """Create or update a tenant profile."""

    get_tenant_user(db, tenant_id)

    profile = get_tenant_profile(
        db,
        tenant_id,
    )

    if profile is None:
        profile = TenantProfile(
            user_id=tenant_id,
            created_at=utc_now(),
        )

        db.add(profile)

    profile.emergency_contact_name = clean_text(
        emergency_contact_name,
        field_name="Emergency contact name",
        maximum_length=150,
    )

    profile.emergency_contact_phone = clean_text(
        emergency_contact_phone,
        field_name="Emergency contact phone",
        maximum_length=40,
    )

    profile.accessibility_requirements = clean_text(
        accessibility_requirements,
        field_name="Accessibility requirements",
        maximum_length=3000,
    )

    try:
        db.commit()
        db.refresh(profile)
    except Exception:
        db.rollback()
        raise

    return profile


# ============================================================
# Dashboard
# ============================================================


def get_tenant_dashboard(
    db: Session,
    tenant_id: str,
) -> dict[str, Any]:
    """Build the tenant dashboard data."""

    tenant = get_tenant_user(
        db,
        tenant_id,
    )

    profile = get_tenant_profile(
        db,
        tenant_id,
    )

    active_lease = get_active_lease(
        db,
        tenant_id,
    )

    property_record = None
    unit = None

    if active_lease is not None:
        property_record = get_lease_property(
            db,
            active_lease,
        )

        unit = get_lease_unit(
            db,
            active_lease,
        )

    payments = list_tenant_payments(
        db,
        tenant_id,
        limit=6,
    )

    maintenance_requests = list_maintenance_requests(
        db,
        tenant_id,
        include_closed=False,
        limit=5,
    )

    complaints = list_complaints(
        db,
        tenant_id,
        include_closed=False,
        limit=5,
    )

    documents = list_tenant_documents(
        db,
        tenant_id,
        limit=5,
    )

    messages = list_tenant_messages(
        db,
        tenant_id,
        limit=5,
    )

    appointments = list_tenant_appointments(
        db,
        tenant_id,
        upcoming_only=True,
        limit=5,
    )

    notifications = list_tenant_notifications(
        db,
        tenant_id,
        unread_only=False,
        limit=10,
    )

    unread_messages = (
        db.query(func.count(Message.id))
        .filter(
            Message.recipient_id == tenant_id,
            Message.read_at.is_(None),
        )
        .scalar()
        or 0
    )

    unread_notifications = (
        db.query(func.count(Notification.id))
        .filter(
            Notification.user_id == tenant_id,
            Notification.is_read.is_(False),
        )
        .scalar()
        or 0
    )

    open_maintenance_count = (
        db.query(func.count(MaintenanceRequest.id))
        .filter(
            MaintenanceRequest.submitted_by_id
            == tenant_id,
            MaintenanceRequest.status.notin_(
                [
                    RequestStatus.RESOLVED,
                    RequestStatus.CLOSED,
                    RequestStatus.CANCELLED,
                ]
            ),
        )
        .scalar()
        or 0
    )

    open_complaints_count = (
        db.query(func.count(Complaint.id))
        .filter(
            Complaint.submitted_by_id == tenant_id,
            Complaint.status.notin_(
                [
                    RequestStatus.RESOLVED,
                    RequestStatus.CLOSED,
                    RequestStatus.CANCELLED,
                ]
            ),
        )
        .scalar()
        or 0
    )

    return {
        "tenant": tenant,
        "profile": profile,
        "active_lease": active_lease,
        "property": property_record,
        "unit": unit,
        "payments": payments,
        "payment_summary": payment_summary(
            db,
            tenant_id,
        ),
        "maintenance_requests": maintenance_requests,
        "complaints": complaints,
        "documents": documents,
        "messages": messages,
        "appointments": appointments,
        "notifications": notifications,
        "statistics": {
            "unread_messages": int(unread_messages),
            "unread_notifications": int(
                unread_notifications
            ),
            "open_maintenance_requests": int(
                open_maintenance_count
            ),
            "open_complaints": int(
                open_complaints_count
            ),
            "upcoming_appointments": len(
                appointments
            ),
        },
    }