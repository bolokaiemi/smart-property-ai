"""
Smart Property AI property-management routes.

File:
    routes/property_routes.py
"""

import math
from datetime import datetime, timezone
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    Form,
    Query,
    Request,
    status,
)
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from config import settings
from database.database import get_db
from database.models import (
    PropertyStatus,
    User,
)
from security.permissions import (
    require_landlord_or_manager,
)
from services.property_service import (
    PropertyConflictError,
    PropertyData,
    PropertyNotFoundError,
    PropertyPermissionError,
    PropertyService,
    PropertyValidationError,
)


router = APIRouter(
    prefix="/landlord/properties",
    tags=["Property Management"],
)

templates = Jinja2Templates(
    directory=str(settings.TEMPLATES_DIR)
)


# ==========================================================================
# Shared helpers
# ==========================================================================

def utc_now() -> datetime:
    """Return the current timezone-aware UTC time."""

    return datetime.now(timezone.utc)


def template_context(
    request: Request,
    current_user: User,
    **extra_context,
) -> dict:
    """Build context shared by property templates."""

    context = {
        "request": request,
        "current_user": current_user,
        "current_year": utc_now().year,
        "current_language": request.session.get(
            "language",
            settings.DEFAULT_LANGUAGE,
        ),
        "property_types": {
            "apartment_building": "Apartment building",
            "house": "House",
            "duplex": "Duplex",
            "townhouse": "Townhouse",
            "student_housing": "Student housing",
            "senior_housing": "Senior housing",
            "commercial": "Commercial property",
            "mixed_use": "Mixed-use property",
            "other": "Other",
        },
        "property_statuses": list(PropertyStatus),
    }

    context.update(extra_context)

    return context


def property_to_form_data(
    property_record,
) -> dict:
    """Convert a property model into form values."""

    return {
        "name": property_record.name,
        "property_type": property_record.property_type,
        "description": property_record.description or "",
        "street_address": property_record.street_address,
        "postal_code": property_record.postal_code,
        "city": property_record.city,
        "state": property_record.state or "",
        "country": property_record.country,
        "latitude": (
            str(property_record.latitude)
            if property_record.latitude is not None
            else ""
        ),
        "longitude": (
            str(property_record.longitude)
            if property_record.longitude is not None
            else ""
        ),
    }


def submitted_property_form_data(
    name: str,
    property_type: str,
    description: Optional[str],
    street_address: str,
    postal_code: str,
    city: str,
    state_name: Optional[str],
    country: str,
    latitude: Optional[str],
    longitude: Optional[str],
) -> dict:
    """Preserve submitted values when validation fails."""

    return {
        "name": name,
        "property_type": property_type,
        "description": description or "",
        "street_address": street_address,
        "postal_code": postal_code,
        "city": city,
        "state": state_name or "",
        "country": country,
        "latitude": latitude or "",
        "longitude": longitude or "",
    }


def parse_property_status(
    value: Optional[str],
) -> Optional[PropertyStatus]:
    """Convert an optional query value into PropertyStatus."""

    if not value:
        return None

    try:
        return PropertyStatus(
            value.strip().lower()
        )
    except ValueError:
        return None


# ==========================================================================
# Property list
# ==========================================================================

@router.get(
    "",
    name="properties_page",
)
async def properties_page(
    request: Request,
    page: int = Query(
        default=1,
        ge=1,
    ),
    search: Optional[str] = Query(
        default=None,
        max_length=150,
    ),
    property_status: Optional[str] = Query(
        default=None,
        alias="status",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_landlord_or_manager
    ),
):
    """Display properties available to the current user."""

    property_service = PropertyService(db)

    page_size = 12

    selected_status = parse_property_status(
        property_status
    )

    try:
        properties = property_service.list_properties(
            current_user=current_user,
            page=page,
            page_size=page_size,
            search=search,
            property_status=selected_status,
        )

        total_properties = property_service.count_properties(
            current_user=current_user,
            search=search,
            property_status=selected_status,
        )

        summary = property_service.get_management_summary(
            current_user=current_user
        )

    except PropertyPermissionError as error:
        return templates.TemplateResponse(
            request=request,
            name="landlord/properties.html",
            context=template_context(
                request=request,
                current_user=current_user,
                properties=[],
                total_properties=0,
                total_pages=0,
                page=1,
                page_size=page_size,
                search=search or "",
                selected_status=property_status or "",
                summary={},
                error=str(error),
            ),
            status_code=status.HTTP_403_FORBIDDEN,
        )

    total_pages = (
        math.ceil(
            total_properties / page_size
        )
        if total_properties
        else 1
    )

    return templates.TemplateResponse(
        request=request,
        name="landlord/properties.html",
        context=template_context(
            request=request,
            current_user=current_user,
            properties=properties,
            total_properties=total_properties,
            total_pages=total_pages,
            page=page,
            page_size=page_size,
            search=search or "",
            selected_status=(
                selected_status.value
                if selected_status
                else ""
            ),
            summary=summary,
        ),
        status_code=status.HTTP_200_OK,
    )


# ==========================================================================
# Add property
# ==========================================================================

@router.get(
    "/add",
    name="add_property_page",
)
async def add_property_page(
    request: Request,
    current_user: User = Depends(
        require_landlord_or_manager
    ),
):
    """Display the add-property form."""

    return templates.TemplateResponse(
        request=request,
        name="landlord/add_property.html",
        context=template_context(
            request=request,
            current_user=current_user,
            form_data={
                "country": "Germany",
            },
        ),
        status_code=status.HTTP_200_OK,
    )


@router.post(
    "/add",
    name="add_property_submit",
)
async def add_property_submit(
    request: Request,
    name: str = Form(...),
    property_type: str = Form(...),
    street_address: str = Form(...),
    postal_code: str = Form(...),
    city: str = Form(...),
    country: str = Form(default="Germany"),
    state_name: Optional[str] = Form(
        default=None,
        alias="state",
    ),
    description: Optional[str] = Form(default=None),
    latitude: Optional[str] = Form(default=None),
    longitude: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_landlord_or_manager
    ),
):
    """Validate and create a new property."""

    property_service = PropertyService(db)

    form_data = submitted_property_form_data(
        name=name,
        property_type=property_type,
        description=description,
        street_address=street_address,
        postal_code=postal_code,
        city=city,
        state_name=state_name,
        country=country,
        latitude=latitude,
        longitude=longitude,
    )

    property_data = PropertyData(
        name=name,
        property_type=property_type,
        description=description,
        street_address=street_address,
        postal_code=postal_code,
        city=city,
        state=state_name,
        country=country,
        latitude=latitude,
        longitude=longitude,
    )

    try:
        property_record = property_service.create_property(
            current_user=current_user,
            property_data=property_data,
            request=request,
        )

    except PropertyValidationError as error:
        return templates.TemplateResponse(
            request=request,
            name="landlord/add_property.html",
            context=template_context(
                request=request,
                current_user=current_user,
                form_data=form_data,
                errors=error.errors,
            ),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    except PropertyConflictError as error:
        return templates.TemplateResponse(
            request=request,
            name="landlord/add_property.html",
            context=template_context(
                request=request,
                current_user=current_user,
                form_data=form_data,
                error=str(error),
            ),
            status_code=status.HTTP_409_CONFLICT,
        )

    except PropertyPermissionError as error:
        return templates.TemplateResponse(
            request=request,
            name="landlord/add_property.html",
            context=template_context(
                request=request,
                current_user=current_user,
                form_data=form_data,
                error=str(error),
            ),
            status_code=status.HTTP_403_FORBIDDEN,
        )

    return RedirectResponse(
        url=str(
            request.url_for(
                "property_details",
                property_id=property_record.id,
            )
        ) + "?created=1",
        status_code=status.HTTP_303_SEE_OTHER,
    )


# ==========================================================================
# Property details
# ==========================================================================

@router.get(
    "/{property_id}",
    name="property_details",
)
async def property_details(
    request: Request,
    property_id: str,
    created: Optional[bool] = Query(default=False),
    updated: Optional[bool] = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_landlord_or_manager
    ),
):
    """Display an individual property and its statistics."""

    property_service = PropertyService(db)

    property_record = property_service.get_manageable_property(
        current_user=current_user,
        property_id=property_id,
    )

    statistics = property_service.get_property_statistics(
        current_user=current_user,
        property_id=property_id,
    )

    available_managers = (
        property_service.list_available_managers()
    )

    success = None

    if created:
        success = "The property was created successfully."
    elif updated:
        success = "The property was updated successfully."

    return templates.TemplateResponse(
        request=request,
        name="landlord/property_details.html",
        context=template_context(
            request=request,
            current_user=current_user,
            property=property_record,
            statistics=statistics,
            available_managers=available_managers,
            success=success,
        ),
        status_code=status.HTTP_200_OK,
    )


# ==========================================================================
# Edit property
# ==========================================================================

@router.get(
    "/{property_id}/edit",
    name="edit_property_page",
)
async def edit_property_page(
    request: Request,
    property_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_landlord_or_manager
    ),
):
    """Display the property-editing form."""

    property_service = PropertyService(db)

    property_record = property_service.get_manageable_property(
        current_user=current_user,
        property_id=property_id,
    )

    return templates.TemplateResponse(
        request=request,
        name="landlord/edit_property.html",
        context=template_context(
            request=request,
            current_user=current_user,
            property=property_record,
            form_data=property_to_form_data(
                property_record
            ),
        ),
        status_code=status.HTTP_200_OK,
    )


@router.post(
    "/{property_id}/edit",
    name="edit_property_submit",
)
async def edit_property_submit(
    request: Request,
    property_id: str,
    name: str = Form(...),
    property_type: str = Form(...),
    street_address: str = Form(...),
    postal_code: str = Form(...),
    city: str = Form(...),
    country: str = Form(default="Germany"),
    state_name: Optional[str] = Form(
        default=None,
        alias="state",
    ),
    description: Optional[str] = Form(default=None),
    latitude: Optional[str] = Form(default=None),
    longitude: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_landlord_or_manager
    ),
):
    """Validate and update a property."""

    property_service = PropertyService(db)

    property_record = property_service.get_manageable_property(
        current_user=current_user,
        property_id=property_id,
    )

    form_data = submitted_property_form_data(
        name=name,
        property_type=property_type,
        description=description,
        street_address=street_address,
        postal_code=postal_code,
        city=city,
        state_name=state_name,
        country=country,
        latitude=latitude,
        longitude=longitude,
    )

    property_data = PropertyData(
        name=name,
        property_type=property_type,
        description=description,
        street_address=street_address,
        postal_code=postal_code,
        city=city,
        state=state_name,
        country=country,
        latitude=latitude,
        longitude=longitude,
    )

    try:
        property_service.update_property(
            current_user=current_user,
            property_id=property_id,
            property_data=property_data,
            request=request,
        )

    except PropertyValidationError as error:
        return templates.TemplateResponse(
            request=request,
            name="landlord/edit_property.html",
            context=template_context(
                request=request,
                current_user=current_user,
                property=property_record,
                form_data=form_data,
                errors=error.errors,
            ),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    except PropertyConflictError as error:
        return templates.TemplateResponse(
            request=request,
            name="landlord/edit_property.html",
            context=template_context(
                request=request,
                current_user=current_user,
                property=property_record,
                form_data=form_data,
                error=str(error),
            ),
            status_code=status.HTTP_409_CONFLICT,
        )

    return RedirectResponse(
        url=str(
            request.url_for(
                "property_details",
                property_id=property_id,
            )
        ) + "?updated=1",
        status_code=status.HTTP_303_SEE_OTHER,
    )


# ==========================================================================
# Property status
# ==========================================================================

@router.post(
    "/{property_id}/activate",
    name="activate_property",
)
async def activate_property(
    request: Request,
    property_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_landlord_or_manager
    ),
):
    """Activate a property."""

    property_service = PropertyService(db)

    property_service.activate_property(
        current_user=current_user,
        property_id=property_id,
        request=request,
    )

    return RedirectResponse(
        url=str(
            request.url_for(
                "property_details",
                property_id=property_id,
            )
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/{property_id}/deactivate",
    name="deactivate_property",
)
async def deactivate_property(
    request: Request,
    property_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_landlord_or_manager
    ),
):
    """Deactivate a property and pause its published listings."""

    property_service = PropertyService(db)

    property_service.deactivate_property(
        current_user=current_user,
        property_id=property_id,
        request=request,
    )

    return RedirectResponse(
        url=str(
            request.url_for(
                "property_details",
                property_id=property_id,
            )
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


# ==========================================================================
# Property-manager assignment
# ==========================================================================

@router.post(
    "/{property_id}/manager",
    name="assign_property_manager",
)
async def assign_property_manager(
    request: Request,
    property_id: str,
    manager_id: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_landlord_or_manager
    ),
):
    """Assign a property manager to a property."""

    property_service = PropertyService(db)

    property_service.assign_manager(
        current_user=current_user,
        property_id=property_id,
        manager_id=manager_id,
        request=request,
    )

    return RedirectResponse(
        url=str(
            request.url_for(
                "property_details",
                property_id=property_id,
            )
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/{property_id}/manager/remove",
    name="remove_property_manager",
)
async def remove_property_manager(
    request: Request,
    property_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_landlord_or_manager
    ),
):
    """Remove a property's assigned manager."""

    property_service = PropertyService(db)

    property_service.remove_manager(
        current_user=current_user,
        property_id=property_id,
        request=request,
    )

    return RedirectResponse(
        url=str(
            request.url_for(
                "property_details",
                property_id=property_id,
            )
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )