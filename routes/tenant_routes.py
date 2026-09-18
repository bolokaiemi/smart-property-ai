"""
Tenant portal routes.

File:
    routes/tenant_routes.py
"""

from __future__ import annotations

import logging
import secrets
from typing import Any

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database.database import get_db
from services.tenant_service import (
    TenantPermissionError,
    TenantResourceNotFoundError,
    TenantServiceError,
    TenantValidationError,
    cancel_maintenance_request,
    create_complaint,
    create_maintenance_request,
    get_active_lease,
    get_complaint,
    get_maintenance_request,
    get_tenant_appointment,
    get_tenant_dashboard,
    get_tenant_document,
    get_tenant_lease,
    get_tenant_message,
    get_tenant_payment,
    get_tenant_profile,
    get_tenant_user,
    list_complaints,
    list_maintenance_requests,
    list_tenant_appointments,
    list_tenant_documents,
    list_tenant_leases,
    list_tenant_messages,
    list_tenant_notifications,
    list_tenant_payments,
    mark_message_read,
    mark_notification_read,
    payment_summary,
    update_tenant_profile,
)


logger = logging.getLogger("smart_property_ai")

router = APIRouter(
    prefix="/tenant",
    tags=["Tenant portal"],
)

templates = Jinja2Templates(directory="templates")


# ============================================================
# Session and security helpers
# ============================================================


def get_session(request: Request) -> Any:
    """Return the request session."""

    try:
        return request.session
    except (AssertionError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SessionMiddleware is not configured.",
        ) from exc


def get_authenticated_user_id(
    request: Request,
) -> str | None:
    """Return the authenticated user's UUID."""

    state_user = getattr(request.state, "user", None)

    if state_user is not None:
        if isinstance(state_user, dict):
            user_id = state_user.get("id")
        else:
            user_id = getattr(state_user, "id", None)

        if user_id:
            return str(user_id)

    session = get_session(request)

    user_id = (
        session.get("user_id")
        or session.get("authenticated_user_id")
    )

    return str(user_id) if user_id else None


def create_csrf_token(request: Request) -> str:
    """Return or create a session CSRF token."""

    session = get_session(request)
    token = session.get("csrf_token")

    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token

    return token


def validate_csrf_token(
    request: Request,
    submitted_token: str | None,
) -> None:
    """Validate a submitted CSRF token."""

    expected_token = get_session(request).get(
        "csrf_token"
    )

    if not expected_token or not submitted_token:
        raise TenantValidationError(
            "Your form session expired. Refresh the page and try again."
        )

    if not secrets.compare_digest(
        str(expected_token),
        str(submitted_token),
    ):
        raise TenantValidationError(
            "Invalid form security token."
        )


def set_flash(
    request: Request,
    category: str,
    message: str,
) -> None:
    """Store one flash message in the session."""

    get_session(request)["tenant_flash"] = {
        "category": category,
        "message": message,
    }


def pop_flash(
    request: Request,
) -> dict[str, str] | None:
    """Return and remove the current tenant flash message."""

    return get_session(request).pop(
        "tenant_flash",
        None,
    )


def login_redirect(
    request: Request,
) -> RedirectResponse:
    """Redirect unauthenticated visitors to login."""

    login_url = request.url_for("login_page")

    return RedirectResponse(
        url=f"{login_url}?next={request.url.path}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


def require_tenant(
    request: Request,
    db: Session,
):
    """Return the authorized tenant user."""

    user_id = get_authenticated_user_id(request)

    if not user_id:
        return None

    try:
        return get_tenant_user(db, user_id)
    except TenantPermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except TenantServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc


def template_context(
    request: Request,
    tenant: Any,
    **extra: Any,
) -> dict[str, Any]:
    """Create common tenant template context."""

    flash = pop_flash(request)

    context: dict[str, Any] = {
        "request": request,
        "current_user": tenant,
        "tenant": tenant,
        "is_authenticated": tenant is not None,
        "csrf_token": create_csrf_token(request),
        "flash": flash,
        "success_message": (
            flash["message"]
            if flash and flash["category"] == "success"
            else None
        ),
        "error_message": (
            flash["message"]
            if flash and flash["category"] == "error"
            else None
        ),
    }

    context.update(extra)
    return context


def boolean_form_value(
    value: str | bool | None,
) -> bool:
    """Convert an HTML checkbox value to a Boolean."""

    if isinstance(value, bool):
        return value

    return str(value or "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


# ============================================================
# Dashboard
# ============================================================


@router.get(
    "",
    response_class=HTMLResponse,
    name="tenant_dashboard",
)
@router.get(
    "/",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def tenant_dashboard_page(
    request: Request,
    db: Session = Depends(get_db),
):
    """Display the tenant dashboard."""

    tenant = require_tenant(request, db)

    if tenant is None:
        return login_redirect(request)

    try:
        dashboard = get_tenant_dashboard(
            db,
            tenant.id,
        )
    except TenantServiceError as exc:
        logger.exception(
            "Tenant dashboard failed: %s",
            exc,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The tenant dashboard could not be loaded.",
        ) from exc

    return templates.TemplateResponse(
        request=request,
        name="tenant/dashboard.html",
        context=template_context(
            request,
            tenant,
            page_title="Tenant portal",
            dashboard=dashboard,
            active_lease=dashboard["active_lease"],
            property=dashboard["property"],
            unit=dashboard["unit"],
            payments=dashboard["payments"],
            payment_summary=dashboard[
                "payment_summary"
            ],
            maintenance_requests=dashboard[
                "maintenance_requests"
            ],
            complaints=dashboard["complaints"],
            documents=dashboard["documents"],
            messages=dashboard["messages"],
            appointments=dashboard["appointments"],
            notifications=dashboard["notifications"],
            statistics=dashboard["statistics"],
        ),
    )


# ============================================================
# Leases
# ============================================================


@router.get(
    "/leases",
    response_class=HTMLResponse,
    name="tenant_leases",
)
def tenant_leases_page(
    request: Request,
    db: Session = Depends(get_db),
):
    """Display all leases belonging to the tenant."""

    tenant = require_tenant(request, db)

    if tenant is None:
        return login_redirect(request)

    leases = list_tenant_leases(
        db,
        tenant.id,
        include_ended=True,
    )

    return templates.TemplateResponse(
        request=request,
        name="tenant/leases.html",
        context=template_context(
            request,
            tenant,
            page_title="My leases",
            leases=leases,
            active_lease=get_active_lease(
                db,
                tenant.id,
            ),
        ),
    )


@router.get(
    "/leases/{lease_id}",
    response_class=HTMLResponse,
    name="tenant_lease_details",
)
def tenant_lease_details_page(
    lease_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Display one tenant-owned lease."""

    tenant = require_tenant(request, db)

    if tenant is None:
        return login_redirect(request)

    try:
        lease = get_tenant_lease(
            db,
            tenant.id,
            lease_id,
        )
    except TenantResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    payments = list_tenant_payments(
        db,
        tenant.id,
        lease_id=lease.id,
    )

    return templates.TemplateResponse(
        request=request,
        name="tenant/lease_details.html",
        context=template_context(
            request,
            tenant,
            page_title="Lease details",
            lease=lease,
            payments=payments,
        ),
    )


# ============================================================
# Payments
# ============================================================


@router.get(
    "/payments",
    response_class=HTMLResponse,
    name="tenant_payments",
)
def tenant_payments_page(
    request: Request,
    db: Session = Depends(get_db),
):
    """Display tenant payment history."""

    tenant = require_tenant(request, db)

    if tenant is None:
        return login_redirect(request)

    payments = list_tenant_payments(
        db,
        tenant.id,
    )

    return templates.TemplateResponse(
        request=request,
        name="tenant/payments.html",
        context=template_context(
            request,
            tenant,
            page_title="Rent and payments",
            payments=payments,
            payment_summary=payment_summary(
                db,
                tenant.id,
            ),
        ),
    )


@router.get(
    "/payments/{payment_id}",
    response_class=HTMLResponse,
    name="tenant_payment_details",
)
def tenant_payment_details_page(
    payment_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Display one tenant payment record."""

    tenant = require_tenant(request, db)

    if tenant is None:
        return login_redirect(request)

    try:
        payment = get_tenant_payment(
            db,
            tenant.id,
            payment_id,
        )
    except TenantResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return templates.TemplateResponse(
        request=request,
        name="tenant/payment_details.html",
        context=template_context(
            request,
            tenant,
            page_title="Payment details",
            payment=payment,
        ),
    )


# ============================================================
# Maintenance requests
# ============================================================


@router.get(
    "/maintenance",
    response_class=HTMLResponse,
    name="tenant_maintenance_requests",
)
def tenant_maintenance_requests_page(
    request: Request,
    db: Session = Depends(get_db),
):
    """Display tenant maintenance requests."""

    tenant = require_tenant(request, db)

    if tenant is None:
        return login_redirect(request)

    maintenance_requests = list_maintenance_requests(
        db,
        tenant.id,
        include_closed=True,
    )

    return templates.TemplateResponse(
        request=request,
        name="tenant/maintenance_requests.html",
        context=template_context(
            request,
            tenant,
            page_title="Maintenance requests",
            maintenance_requests=maintenance_requests,
        ),
    )


@router.get(
    "/maintenance/new",
    response_class=HTMLResponse,
    name="tenant_add_maintenance_request",
)
def add_maintenance_request_page(
    request: Request,
    db: Session = Depends(get_db),
):
    """Display the maintenance request form."""

    tenant = require_tenant(request, db)

    if tenant is None:
        return login_redirect(request)

    leases = list_tenant_leases(
        db,
        tenant.id,
        include_ended=False,
    )

    return templates.TemplateResponse(
        request=request,
        name="tenant/add_maintenance_request.html",
        context=template_context(
            request,
            tenant,
            page_title="New maintenance request",
            leases=leases,
        ),
    )


@router.post(
    "/maintenance/new",
    name="tenant_add_maintenance_request_submit",
)
def add_maintenance_request_submit(
    request: Request,
    property_id: str = Form(...),
    unit_id: str | None = Form(None),
    title: str = Form(...),
    description: str = Form(...),
    category: str | None = Form(None),
    priority: str = Form("normal"),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    """Create a tenant maintenance request."""

    tenant = require_tenant(request, db)

    if tenant is None:
        return login_redirect(request)

    try:
        validate_csrf_token(
            request,
            csrf_token,
        )

        maintenance_request = (
            create_maintenance_request(
                db,
                tenant_id=tenant.id,
                property_id=property_id,
                unit_id=unit_id or None,
                title=title,
                description=description,
                category=category,
                priority=priority,
            )
        )

        set_flash(
            request,
            "success",
            (
                "Maintenance request submitted. "
                f"Reference: {maintenance_request.id}."
            ),
        )

        return RedirectResponse(
            url=str(
                request.url_for(
                    "tenant_maintenance_request_details",
                    request_id=maintenance_request.id,
                )
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    except (
        TenantValidationError,
        TenantPermissionError,
    ) as exc:
        set_flash(
            request,
            "error",
            str(exc),
        )

        return RedirectResponse(
            url=str(
                request.url_for(
                    "tenant_add_maintenance_request"
                )
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )


@router.get(
    "/maintenance/{request_id}",
    response_class=HTMLResponse,
    name="tenant_maintenance_request_details",
)
def maintenance_request_details_page(
    request_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Display one tenant maintenance request."""

    tenant = require_tenant(request, db)

    if tenant is None:
        return login_redirect(request)

    try:
        maintenance_request = get_maintenance_request(
            db,
            tenant.id,
            request_id,
        )
    except TenantResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return templates.TemplateResponse(
        request=request,
        name="tenant/maintenance_request_details.html",
        context=template_context(
            request,
            tenant,
            page_title="Maintenance request details",
            maintenance_request=maintenance_request,
        ),
    )


@router.post(
    "/maintenance/{request_id}/cancel",
    name="tenant_cancel_maintenance_request",
)
def cancel_maintenance_request_submit(
    request_id: str,
    request: Request,
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    """Cancel an open tenant maintenance request."""

    tenant = require_tenant(request, db)

    if tenant is None:
        return login_redirect(request)

    try:
        validate_csrf_token(
            request,
            csrf_token,
        )

        cancel_maintenance_request(
            db,
            tenant_id=tenant.id,
            request_id=request_id,
        )

        set_flash(
            request,
            "success",
            "Maintenance request cancelled.",
        )

    except TenantServiceError as exc:
        set_flash(
            request,
            "error",
            str(exc),
        )

    return RedirectResponse(
        url=str(
            request.url_for(
                "tenant_maintenance_request_details",
                request_id=request_id,
            )
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


# ============================================================
# Complaints
# ============================================================


@router.get(
    "/complaints",
    response_class=HTMLResponse,
    name="tenant_complaints",
)
def tenant_complaints_page(
    request: Request,
    db: Session = Depends(get_db),
):
    """Display complaints submitted by the tenant."""

    tenant = require_tenant(request, db)

    if tenant is None:
        return login_redirect(request)

    complaints = list_complaints(
        db,
        tenant.id,
        include_closed=True,
    )

    return templates.TemplateResponse(
        request=request,
        name="tenant/complaints.html",
        context=template_context(
            request,
            tenant,
            page_title="My complaints",
            complaints=complaints,
        ),
    )


@router.get(
    "/complaints/new",
    response_class=HTMLResponse,
    name="tenant_add_complaint",
)
def add_complaint_page(
    request: Request,
    db: Session = Depends(get_db),
):
    """Display the complaint form."""

    tenant = require_tenant(request, db)

    if tenant is None:
        return login_redirect(request)

    leases = list_tenant_leases(
        db,
        tenant.id,
        include_ended=False,
    )

    return templates.TemplateResponse(
        request=request,
        name="tenant/add_complaint.html",
        context=template_context(
            request,
            tenant,
            page_title="Submit a complaint",
            leases=leases,
        ),
    )


@router.post(
    "/complaints/new",
    name="tenant_add_complaint_submit",
)
def add_complaint_submit(
    request: Request,
    property_id: str = Form(...),
    subject: str = Form(...),
    description: str = Form(...),
    priority: str = Form("normal"),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    """Create a tenant complaint."""

    tenant = require_tenant(request, db)

    if tenant is None:
        return login_redirect(request)

    try:
        validate_csrf_token(
            request,
            csrf_token,
        )

        complaint = create_complaint(
            db,
            tenant_id=tenant.id,
            property_id=property_id,
            subject=subject,
            description=description,
            priority=priority,
        )

        set_flash(
            request,
            "success",
            (
                "Complaint submitted. "
                f"Reference: {complaint.id}."
            ),
        )

        return RedirectResponse(
            url=str(
                request.url_for(
                    "tenant_complaint_details",
                    complaint_id=complaint.id,
                )
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    except (
        TenantValidationError,
        TenantPermissionError,
    ) as exc:
        set_flash(
            request,
            "error",
            str(exc),
        )

        return RedirectResponse(
            url=str(
                request.url_for(
                    "tenant_add_complaint"
                )
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )


@router.get(
    "/complaints/{complaint_id}",
    response_class=HTMLResponse,
    name="tenant_complaint_details",
)
def complaint_details_page(
    complaint_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Display one tenant complaint."""

    tenant = require_tenant(request, db)

    if tenant is None:
        return login_redirect(request)

    try:
        complaint = get_complaint(
            db,
            tenant.id,
            complaint_id,
        )
    except TenantResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return templates.TemplateResponse(
        request=request,
        name="tenant/complaint_details.html",
        context=template_context(
            request,
            tenant,
            page_title="Complaint details",
            complaint=complaint,
        ),
    )


# ============================================================
# Documents
# ============================================================


@router.get(
    "/documents",
    response_class=HTMLResponse,
    name="tenant_documents",
)
def tenant_documents_page(
    request: Request,
    db: Session = Depends(get_db),
):
    """Display documents available to the tenant."""

    tenant = require_tenant(request, db)

    if tenant is None:
        return login_redirect(request)

    documents = list_tenant_documents(
        db,
        tenant.id,
    )

    return templates.TemplateResponse(
        request=request,
        name="tenant/documents.html",
        context=template_context(
            request,
            tenant,
            page_title="My documents",
            documents=documents,
        ),
    )


@router.get(
    "/documents/{document_id}",
    response_class=HTMLResponse,
    name="tenant_document_details",
)
def tenant_document_details_page(
    document_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Display document metadata.

    Secure file downloads should be implemented separately using the
    file service. Never expose storage_path directly in a template.
    """

    tenant = require_tenant(request, db)

    if tenant is None:
        return login_redirect(request)

    try:
        document = get_tenant_document(
            db,
            tenant.id,
            document_id,
        )
    except TenantResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return templates.TemplateResponse(
        request=request,
        name="tenant/document_details.html",
        context=template_context(
            request,
            tenant,
            page_title="Document details",
            document=document,
        ),
    )


# ============================================================
# Messages
# ============================================================


@router.get(
    "/messages",
    response_class=HTMLResponse,
    name="tenant_messages",
)
def tenant_messages_page(
    request: Request,
    db: Session = Depends(get_db),
):
    """Display tenant messages."""

    tenant = require_tenant(request, db)

    if tenant is None:
        return login_redirect(request)

    messages = list_tenant_messages(
        db,
        tenant.id,
    )

    return templates.TemplateResponse(
        request=request,
        name="tenant/messages.html",
        context=template_context(
            request,
            tenant,
            page_title="Messages",
            messages=messages,
        ),
    )


@router.get(
    "/messages/{message_id}",
    response_class=HTMLResponse,
    name="tenant_message_details",
)
def tenant_message_details_page(
    message_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Display one tenant message."""

    tenant = require_tenant(request, db)

    if tenant is None:
        return login_redirect(request)

    try:
        message = get_tenant_message(
            db,
            tenant.id,
            message_id,
        )

        if (
            message.recipient_id == tenant.id
            and message.read_at is None
        ):
            message = mark_message_read(
                db,
                tenant_id=tenant.id,
                message_id=message.id,
            )

    except TenantResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return templates.TemplateResponse(
        request=request,
        name="tenant/message_details.html",
        context=template_context(
            request,
            tenant,
            page_title=message.subject or "Message",
            message=message,
        ),
    )


# ============================================================
# Appointments
# ============================================================


@router.get(
    "/appointments",
    response_class=HTMLResponse,
    name="tenant_appointments",
)
def tenant_appointments_page(
    request: Request,
    db: Session = Depends(get_db),
):
    """Display tenant appointments."""

    tenant = require_tenant(request, db)

    if tenant is None:
        return login_redirect(request)

    appointments = list_tenant_appointments(
        db,
        tenant.id,
    )

    return templates.TemplateResponse(
        request=request,
        name="tenant/appointments.html",
        context=template_context(
            request,
            tenant,
            page_title="My appointments",
            appointments=appointments,
        ),
    )


@router.get(
    "/appointments/{appointment_id}",
    response_class=HTMLResponse,
    name="tenant_appointment_details",
)
def tenant_appointment_details_page(
    appointment_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Display one tenant appointment."""

    tenant = require_tenant(request, db)

    if tenant is None:
        return login_redirect(request)

    try:
        appointment = get_tenant_appointment(
            db,
            tenant.id,
            appointment_id,
        )
    except TenantResourceNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return templates.TemplateResponse(
        request=request,
        name="tenant/appointment_details.html",
        context=template_context(
            request,
            tenant,
            page_title="Appointment details",
            appointment=appointment,
        ),
    )


# ============================================================
# Notifications
# ============================================================


@router.get(
    "/notifications",
    response_class=HTMLResponse,
    name="tenant_notifications",
)
def tenant_notifications_page(
    request: Request,
    db: Session = Depends(get_db),
):
    """Display tenant notifications."""

    tenant = require_tenant(request, db)

    if tenant is None:
        return login_redirect(request)

    notifications = list_tenant_notifications(
        db,
        tenant.id,
        limit=100,
    )

    return templates.TemplateResponse(
        request=request,
        name="tenant/notifications.html",
        context=template_context(
            request,
            tenant,
            page_title="Notifications",
            notifications=notifications,
        ),
    )


@router.post(
    "/notifications/{notification_id}/read",
    name="tenant_notification_read",
)
def tenant_notification_read_submit(
    notification_id: str,
    request: Request,
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    """Mark a tenant notification as read."""

    tenant = require_tenant(request, db)

    if tenant is None:
        return login_redirect(request)

    try:
        validate_csrf_token(
            request,
            csrf_token,
        )

        notification = mark_notification_read(
            db,
            tenant_id=tenant.id,
            notification_id=notification_id,
        )

        redirect_url = (
            notification.action_url
            if notification.action_url
            and notification.action_url.startswith("/")
            and not notification.action_url.startswith("//")
            else str(
                request.url_for(
                    "tenant_notifications"
                )
            )
        )

    except TenantServiceError as exc:
        set_flash(
            request,
            "error",
            str(exc),
        )

        redirect_url = str(
            request.url_for(
                "tenant_notifications"
            )
        )

    return RedirectResponse(
        url=redirect_url,
        status_code=status.HTTP_303_SEE_OTHER,
    )


# ============================================================
# Profile
# ============================================================


@router.get(
    "/profile",
    response_class=HTMLResponse,
    name="tenant_profile",
)
def tenant_profile_page(
    request: Request,
    db: Session = Depends(get_db),
):
    """Display the tenant profile form."""

    tenant = require_tenant(request, db)

    if tenant is None:
        return login_redirect(request)

    profile = get_tenant_profile(
        db,
        tenant.id,
    )

    return templates.TemplateResponse(
        request=request,
        name="tenant/profile.html",
        context=template_context(
            request,
            tenant,
            page_title="Tenant profile",
            profile=profile,
        ),
    )


@router.post(
    "/profile",
    name="tenant_profile_submit",
)
def tenant_profile_submit(
    request: Request,
    emergency_contact_name: str | None = Form(None),
    emergency_contact_phone: str | None = Form(None),
    accessibility_requirements: str | None = Form(None),
    csrf_token: str = Form(...),
    db: Session = Depends(get_db),
):
    """Create or update a tenant profile."""

    tenant = require_tenant(request, db)

    if tenant is None:
        return login_redirect(request)

    try:
        validate_csrf_token(
            request,
            csrf_token,
        )

        update_tenant_profile(
            db,
            tenant_id=tenant.id,
            emergency_contact_name=emergency_contact_name,
            emergency_contact_phone=emergency_contact_phone,
            accessibility_requirements=(
                accessibility_requirements
            ),
        )

        set_flash(
            request,
            "success",
            "Your tenant profile has been updated.",
        )

    except TenantServiceError as exc:
        set_flash(
            request,
            "error",
            str(exc),
        )

    return RedirectResponse(
        url=str(
            request.url_for(
                "tenant_profile"
            )
        ),
        status_code=status.HTTP_303_SEE_OTHER,


    )
