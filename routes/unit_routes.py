"""
Smart Property AI apartment-unit routes.

File:
    routes/unit_routes.py
"""

import math
from datetime import datetime, timezone
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    Form,
    HTTPException,
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
    Unit,
    UnitStatus,
    User,
)
from security.permissions import (
    require_landlord_or_manager,
)
from services.property_service import PropertyService
from services.unit_service import (
    UnitConflictError,
    UnitData,
    UnitNotFoundError,
    UnitService,
    UnitValidationError,
)


router = APIRouter(
    tags=["Apartment Unit Management"],
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


def checkbox_to_boolean(
    value: Optional[str],
) -> bool:
    """Convert a submitted checkbox value into a Boolean."""

    if value is None:
        return False

    return value.strip().lower() in {
        "true",
        "1",
        "yes",
        "on",
    }


def template_context(
    request: Request,
    current_user: User,
    **extra_context,
) -> dict:
    """Build context shared by apartment-unit templates."""

    context = {
        "request": request,
        "current_user": current_user,
        "current_year": utc_now().year,
        "current_language": request.session.get(
            "language",
            settings.DEFAULT_LANGUAGE,
        ),
        "unit_statuses": list(UnitStatus),
        "currencies": [
            "EUR",
            "USD",
            "GBP",
            "NGN",
            "GHS",
            "CAD",
            "AUD",
        ],
    }

    context.update(extra_context)

    return context


def unit_to_form_data(
    unit: Unit,
) -> dict:
    """Convert a unit model into reusable form values."""

    return {
        "unit_number": unit.unit_number,
        "floor": unit.floor or "",
        "rooms": str(unit.rooms),
        "bedrooms": unit.bedrooms,
        "bathrooms": unit.bathrooms,
        "area_square_metres": (
            str(unit.area_square_metres)
            if unit.area_square_metres is not None
            else ""
        ),
        "monthly_rent": str(unit.monthly_rent),
        "deposit_amount": (
            str(unit.deposit_amount)
            if unit.deposit_amount is not None
            else ""
        ),
        "currency": unit.currency,
        "wheelchair_accessible": (
            unit.wheelchair_accessible
        ),
        "pets_allowed": unit.pets_allowed,
    }


def submitted_unit_form_data(
    unit_number: str,
    floor: Optional[str],
    rooms: str,
    bedrooms: int,
    bathrooms: int,
    area_square_metres: Optional[str],
    monthly_rent: str,
    deposit_amount: Optional[str],
    currency: str,
    wheelchair_accessible: Optional[str],
    pets_allowed: Optional[str],
) -> dict:
    """Preserve submitted form values after validation errors."""

    return {
        "unit_number": unit_number,
        "floor": floor or "",
        "rooms": rooms,
        "bedrooms": bedrooms,
        "bathrooms": bathrooms,
        "area_square_metres": area_square_metres or "",
        "monthly_rent": monthly_rent,
        "deposit_amount": deposit_amount or "",
        "currency": currency,
        "wheelchair_accessible": checkbox_to_boolean(
            wheelchair_accessible
        ),
        "pets_allowed": checkbox_to_boolean(
            pets_allowed
        ),
    }


def build_unit_data(
    unit_number: str,
    floor: Optional[str],
    rooms: str,
    bedrooms: int,
    bathrooms: int,
    area_square_metres: Optional[str],
    monthly_rent: str,
    deposit_amount: Optional[str],
    currency: str,
    wheelchair_accessible: Optional[str],
    pets_allowed: Optional[str],
) -> UnitData:
    """Build a UnitData object from submitted form values."""

    return UnitData(
        unit_number=unit_number,
        floor=floor,
        rooms=rooms,
        bedrooms=bedrooms,
        bathrooms=bathrooms,
        area_square_metres=area_square_metres,
        monthly_rent=monthly_rent,
        deposit_amount=deposit_amount,
        currency=currency,
        wheelchair_accessible=checkbox_to_boolean(
            wheelchair_accessible
        ),
        pets_allowed=checkbox_to_boolean(
            pets_allowed
        ),
    )


def parse_unit_status(
    value: Optional[str],
) -> Optional[UnitStatus]:
    """Convert an optional string into UnitStatus."""

    if not value:
        return None

    try:
        return UnitStatus(
            value.strip().lower()
        )
    except ValueError:
        return None


def unit_list_url(
    request: Request,
    property_id: str,
    message_key: Optional[str] = None,
) -> str:
    """Build the property-unit list URL."""

    url = str(
        request.url_for(
            "units_page",
            property_id=property_id,
        )
    )

    if message_key:
        url = f"{url}?{message_key}=1"

    return url


def load_unit_page_data(
    unit_service: UnitService,
    property_service: PropertyService,
    current_user: User,
    property_id: str,
    page: int = 1,
    page_size: int = 20,
    search: Optional[str] = None,
    selected_status: Optional[UnitStatus] = None,
) -> dict:
    """Load the property, units and statistics for the template."""

    property_record = (
        property_service.get_manageable_property(
            current_user=current_user,
            property_id=property_id,
        )
    )

    units = unit_service.list_units(
        current_user=current_user,
        property_id=property_id,
        page=page,
        page_size=page_size,
        unit_status=selected_status,
        search=search,
    )

    total_units = unit_service.count_units(
        current_user=current_user,
        property_id=property_id,
        unit_status=selected_status,
        search=search,
    )

    statistics = unit_service.get_unit_statistics(
        current_user=current_user,
        property_id=property_id,
    )

    total_pages = (
        math.ceil(total_units / page_size)
        if total_units
        else 1
    )

    return {
        "property": property_record,
        "units": units,
        "statistics": statistics,
        "total_units": total_units,
        "total_pages": total_pages,
    }


# ==========================================================================
# Unit list and add form
# ==========================================================================

@router.get(
    "/landlord/properties/{property_id}/units",
    name="units_page",
)
async def units_page(
    request: Request,
    property_id: str,
    page: int = Query(
        default=1,
        ge=1,
    ),
    search: Optional[str] = Query(
        default=None,
        max_length=100,
    ),
    unit_status: Optional[str] = Query(
        default=None,
        alias="status",
    ),
    created: Optional[bool] = Query(default=False),
    updated: Optional[bool] = Query(default=False),
    removed: Optional[bool] = Query(default=False),
    deactivated: Optional[bool] = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_landlord_or_manager
    ),
):
    """Display all apartment units for a property."""

    unit_service = UnitService(db)
    property_service = PropertyService(db)

    page_size = 20

    selected_status = parse_unit_status(
        unit_status
    )

    page_data = load_unit_page_data(
        unit_service=unit_service,
        property_service=property_service,
        current_user=current_user,
        property_id=property_id,
        page=page,
        page_size=page_size,
        search=search,
        selected_status=selected_status,
    )

    success = None

    if created:
        success = "The apartment unit was created successfully."
    elif updated:
        success = "The apartment unit was updated successfully."
    elif removed:
        success = "The apartment unit was removed successfully."
    elif deactivated:
        success = "The apartment unit was marked unavailable."

    return templates.TemplateResponse(
        request=request,
        name="landlord/units.html",
        context=template_context(
            request=request,
            current_user=current_user,
            **page_data,
            page=page,
            page_size=page_size,
            search=search or "",
            selected_status=(
                selected_status.value
                if selected_status
                else ""
            ),
            form_mode="create",
            form_data={
                "bedrooms": 0,
                "bathrooms": 1,
                "currency": settings.DEFAULT_CURRENCY,
                "wheelchair_accessible": False,
                "pets_allowed": False,
            },
            editing_unit=None,
            success=success,
        ),
        status_code=status.HTTP_200_OK,
    )


@router.post(
    "/landlord/properties/{property_id}/units/add",
    name="add_unit_submit",
)
async def add_unit_submit(
    request: Request,
    property_id: str,
    unit_number: str = Form(...),
    rooms: str = Form(...),
    monthly_rent: str = Form(...),
    floor: Optional[str] = Form(default=None),
    bedrooms: int = Form(default=0),
    bathrooms: int = Form(default=1),
    area_square_metres: Optional[str] = Form(default=None),
    deposit_amount: Optional[str] = Form(default=None),
    currency: str = Form(default="EUR"),
    wheelchair_accessible: Optional[str] = Form(default=None),
    pets_allowed: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_landlord_or_manager
    ),
):
    """Create an apartment unit."""

    unit_service = UnitService(db)
    property_service = PropertyService(db)

    form_data = submitted_unit_form_data(
        unit_number=unit_number,
        floor=floor,
        rooms=rooms,
        bedrooms=bedrooms,
        bathrooms=bathrooms,
        area_square_metres=area_square_metres,
        monthly_rent=monthly_rent,
        deposit_amount=deposit_amount,
        currency=currency,
        wheelchair_accessible=wheelchair_accessible,
        pets_allowed=pets_allowed,
    )

    unit_data = build_unit_data(
        unit_number=unit_number,
        floor=floor,
        rooms=rooms,
        bedrooms=bedrooms,
        bathrooms=bathrooms,
        area_square_metres=area_square_metres,
        monthly_rent=monthly_rent,
        deposit_amount=deposit_amount,
        currency=currency,
        wheelchair_accessible=wheelchair_accessible,
        pets_allowed=pets_allowed,
    )

    try:
        unit_service.create_unit(
            current_user=current_user,
            property_id=property_id,
            unit_data=unit_data,
            request=request,
        )

    except (
        UnitValidationError,
        UnitConflictError,
    ) as error:
        page_data = load_unit_page_data(
            unit_service=unit_service,
            property_service=property_service,
            current_user=current_user,
            property_id=property_id,
        )

        errors = (
            error.errors
            if isinstance(error, UnitValidationError)
            else [str(error)]
        )

        return templates.TemplateResponse(
            request=request,
            name="landlord/units.html",
            context=template_context(
                request=request,
                current_user=current_user,
                **page_data,
                page=1,
                page_size=20,
                search="",
                selected_status="",
                form_mode="create",
                form_data=form_data,
                editing_unit=None,
                errors=errors,
            ),
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
                if isinstance(error, UnitValidationError)
                else status.HTTP_409_CONFLICT
            ),
        )

    return RedirectResponse(
        url=unit_list_url(
            request=request,
            property_id=property_id,
            message_key="created",
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


# ==========================================================================
# Unit details
# ==========================================================================

@router.get(
    "/landlord/units/{unit_id}",
    name="unit_details",
)
async def unit_details(
    request: Request,
    unit_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_landlord_or_manager
    ),
):
    """Display a single apartment unit."""

    unit_service = UnitService(db)

    try:
        unit = unit_service.get_manageable_unit(
            current_user=current_user,
            unit_id=unit_id,
        )
    except UnitNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    active_lease = unit_service.get_active_lease(
        unit_id=unit.id
    )

    has_history, history_message = (
        unit_service.unit_has_history(
            unit.id
        )
    )

    return templates.TemplateResponse(
        request=request,
        name="landlord/unit_details.html",
        context=template_context(
            request=request,
            current_user=current_user,
            unit=unit,
            active_lease=active_lease,
            has_history=has_history,
            history_message=history_message,
        ),
        status_code=status.HTTP_200_OK,
    )


# ==========================================================================
# Edit unit
# ==========================================================================

@router.get(
    "/landlord/units/{unit_id}/edit",
    name="edit_unit_page",
)
async def edit_unit_page(
    request: Request,
    unit_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_landlord_or_manager
    ),
):
    """Display the units page with the edit form open."""

    unit_service = UnitService(db)
    property_service = PropertyService(db)

    try:
        unit = unit_service.get_manageable_unit(
            current_user=current_user,
            unit_id=unit_id,
        )
    except UnitNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    page_data = load_unit_page_data(
        unit_service=unit_service,
        property_service=property_service,
        current_user=current_user,
        property_id=unit.property_id,
    )

    return templates.TemplateResponse(
        request=request,
        name="landlord/units.html",
        context=template_context(
            request=request,
            current_user=current_user,
            **page_data,
            page=1,
            page_size=20,
            search="",
            selected_status="",
            form_mode="edit",
            form_data=unit_to_form_data(unit),
            editing_unit=unit,
        ),
        status_code=status.HTTP_200_OK,
    )


@router.post(
    "/landlord/units/{unit_id}/edit",
    name="edit_unit_submit",
)
async def edit_unit_submit(
    request: Request,
    unit_id: str,
    unit_number: str = Form(...),
    rooms: str = Form(...),
    monthly_rent: str = Form(...),
    floor: Optional[str] = Form(default=None),
    bedrooms: int = Form(default=0),
    bathrooms: int = Form(default=1),
    area_square_metres: Optional[str] = Form(default=None),
    deposit_amount: Optional[str] = Form(default=None),
    currency: str = Form(default="EUR"),
    wheelchair_accessible: Optional[str] = Form(default=None),
    pets_allowed: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_landlord_or_manager
    ),
):
    """Validate and update an apartment unit."""

    unit_service = UnitService(db)
    property_service = PropertyService(db)

    try:
        unit = unit_service.get_manageable_unit(
            current_user=current_user,
            unit_id=unit_id,
        )
    except UnitNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    form_data = submitted_unit_form_data(
        unit_number=unit_number,
        floor=floor,
        rooms=rooms,
        bedrooms=bedrooms,
        bathrooms=bathrooms,
        area_square_metres=area_square_metres,
        monthly_rent=monthly_rent,
        deposit_amount=deposit_amount,
        currency=currency,
        wheelchair_accessible=wheelchair_accessible,
        pets_allowed=pets_allowed,
    )

    unit_data = build_unit_data(
        unit_number=unit_number,
        floor=floor,
        rooms=rooms,
        bedrooms=bedrooms,
        bathrooms=bathrooms,
        area_square_metres=area_square_metres,
        monthly_rent=monthly_rent,
        deposit_amount=deposit_amount,
        currency=currency,
        wheelchair_accessible=wheelchair_accessible,
        pets_allowed=pets_allowed,
    )

    try:
        unit_service.update_unit(
            current_user=current_user,
            unit_id=unit_id,
            unit_data=unit_data,
            request=request,
        )

    except (
        UnitValidationError,
        UnitConflictError,
    ) as error:
        page_data = load_unit_page_data(
            unit_service=unit_service,
            property_service=property_service,
            current_user=current_user,
            property_id=unit.property_id,
        )

        errors = (
            error.errors
            if isinstance(error, UnitValidationError)
            else [str(error)]
        )

        return templates.TemplateResponse(
            request=request,
            name="landlord/units.html",
            context=template_context(
                request=request,
                current_user=current_user,
                **page_data,
                page=1,
                page_size=20,
                search="",
                selected_status="",
                form_mode="edit",
                form_data=form_data,
                editing_unit=unit,
                errors=errors,
            ),
            status_code=(
                status.HTTP_422_UNPROCESSABLE_ENTITY
                if isinstance(error, UnitValidationError)
                else status.HTTP_409_CONFLICT
            ),
        )

    return RedirectResponse(
        url=unit_list_url(
            request=request,
            property_id=unit.property_id,
            message_key="updated",
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


# ==========================================================================
# Status changes
# ==========================================================================

@router.post(
    "/landlord/units/{unit_id}/status",
    name="change_unit_status",
)
async def change_unit_status(
    request: Request,
    unit_id: str,
    new_status: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_landlord_or_manager
    ),
):
    """Change a unit's status."""

    unit_service = UnitService(db)

    try:
        unit = unit_service.get_manageable_unit(
            current_user=current_user,
            unit_id=unit_id,
        )

        property_id = unit.property_id

        unit_service.change_unit_status(
            current_user=current_user,
            unit_id=unit_id,
            new_status=new_status,
            request=request,
        )

    except UnitNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    except (
        UnitValidationError,
        UnitConflictError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    return RedirectResponse(
        url=unit_list_url(
            request=request,
            property_id=property_id,
            message_key="updated",
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/landlord/units/{unit_id}/deactivate",
    name="deactivate_unit",
)
async def deactivate_unit(
    request: Request,
    unit_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_landlord_or_manager
    ),
):
    """Mark an apartment unit as unavailable."""

    unit_service = UnitService(db)

    try:
        unit = unit_service.get_manageable_unit(
            current_user=current_user,
            unit_id=unit_id,
        )

        property_id = unit.property_id

        unit_service.deactivate_unit(
            current_user=current_user,
            unit_id=unit_id,
            request=request,
        )

    except UnitNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    except UnitConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    return RedirectResponse(
        url=unit_list_url(
            request=request,
            property_id=property_id,
            message_key="deactivated",
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )


# ==========================================================================
# Delete unit
# ==========================================================================

@router.post(
    "/landlord/units/{unit_id}/delete",
    name="delete_unit",
)
async def delete_unit(
    request: Request,
    unit_id: str,
    confirm_unit_number: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_landlord_or_manager
    ),
):
    """
    Permanently delete a unit without lease or listing history.

    The user must enter the correct unit number as confirmation.
    """

    unit_service = UnitService(db)

    try:
        unit = unit_service.get_manageable_unit(
            current_user=current_user,
            unit_id=unit_id,
        )
    except UnitNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error

    property_id = unit.property_id

    if (
        confirm_unit_number.strip().lower()
        != unit.unit_number.strip().lower()
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "The confirmation unit number does not match."
            ),
        )

    try:
        unit_service.remove_unit(
            current_user=current_user,
            unit_id=unit_id,
            request=request,
        )
    except UnitConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    return RedirectResponse(
        url=unit_list_url(
            request=request,
            property_id=property_id,
            message_key="removed",
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )