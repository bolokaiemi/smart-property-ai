"""
Public apartment-listing routes for Smart Property AI.
"""

from __future__ import annotations

import logging
import secrets
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

from fastapi.responses import HTMLResponse, RedirectResponse
from decimal import Decimal, InvalidOperation
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_
from sqlalchemy.orm import Session

from database.database import get_db
from database.models import Listing, ListingStatus, Property, Unit


from database.database import get_db
from services.listing_service import (
    InvalidSearchError,
    ListingNotFoundError,
    ListingServiceError,
    get_featured_listings,
    get_filter_options,
    get_listing,
    get_similar_listings,
    increment_listing_impressions,
    search_listings,
)

logger = logging.getLogger("smart_property_ai")

router = APIRouter(
    prefix="/listings",
    tags=["Listings"],
)

templates = Jinja2Templates(directory="templates")


def _session(request: Request) -> dict[str, Any]:
    """
    Return the request session safely.

    SessionMiddleware must be installed in app.py.
    """

    try:
        return request.session
    except (AssertionError, RuntimeError):
        return {}


def _current_user(request: Request) -> Any | None:
    """
    Return the authenticated user stored by the authentication system.
    """

    user = getattr(request.state, "user", None)

    if user is not None:
        return user

    return _session(request).get("user")


def _csrf_token(request: Request) -> str:
    """
    Return or create a CSRF token for public forms.
    """

    session = _session(request)

    if not session:
        return ""

    token = session.get("csrf_token")

    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token

    return token


def _base_context(
    request: Request,
    **extra: Any,
) -> dict[str, Any]:
    """
    Build the common Jinja2 template context.
    """

    session = _session(request)

    context: dict[str, Any] = {
        "request": request,
        "current_user": _current_user(request),
        "is_authenticated": bool(
            session.get("user_id") or _current_user(request)
        ),
        "csrf_token": _csrf_token(request),
        "success_message": session.pop("success_message", None)
        if session
        else None,
        "error_message": session.pop("error_message", None)
        if session
        else None,
    }

    context.update(extra)
    return context


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None

    cleaned = value.strip()
    return cleaned or None


def _search_parameters(
    *,
    q: str | None,
    city: str | None,
    property_type: str | None,
    minimum_rent: Decimal | None,
    maximum_rent: Decimal | None,
    bedrooms: int | None,
    bathrooms: int | None,
    minimum_area: Decimal | None,
    furnished: bool | None,
    accessible: bool | None,
    pets_allowed: bool | None,
    parking: bool | None,
    sort: str,
) -> dict[str, Any]:
    """
    Create one normalized search-parameter dictionary.
    """

    return {
        "query_text": _clean_text(q),
        "city": _clean_text(city),
        "property_type": _clean_text(property_type),
        "minimum_rent": minimum_rent,
        "maximum_rent": maximum_rent,
        "minimum_bedrooms": bedrooms,
        "minimum_bathrooms": bathrooms,
        "minimum_area": minimum_area,
        "furnished": furnished,
        "accessible": accessible,
        "pets_allowed": pets_allowed,
        "parking": parking,
        "sort": sort,
    }


def _query_values(
    parameters: dict[str, Any],
) -> dict[str, str]:
    """
    Convert search parameters into pagination-friendly URL values.
    """

    values: dict[str, str] = {}

    field_names = {
        "query_text": "q",
        "city": "city",
        "property_type": "property_type",
        "minimum_rent": "minimum_rent",
        "maximum_rent": "maximum_rent",
        "minimum_bedrooms": "bedrooms",
        "minimum_bathrooms": "bathrooms",
        "minimum_area": "minimum_area",
        "furnished": "furnished",
        "accessible": "accessible",
        "pets_allowed": "pets_allowed",
        "parking": "parking",
        "sort": "sort",
    }

    for internal_name, public_name in field_names.items():
        value = parameters.get(internal_name)

        if value is None or value == "":
            continue

        if isinstance(value, bool):
            values[public_name] = "true" if value else "false"
        else:
            values[public_name] = str(value)

    return values


def _pagination_url(
    request: Request,
    query_values: dict[str, str],
    page: int,
) -> str:
    parameters = dict(query_values)
    parameters["page"] = str(page)

    return f"{request.url.path}?{urlencode(parameters)}"


@router.get(
    "",
    response_class=HTMLResponse,
    name="listings_page",
)
@router.get(
    "/",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def listings_page(
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """
    Display the public listing landing page.
    """

    try:
        featured_listings = get_featured_listings(
            db,
            limit=6,
        )
        filter_options = get_filter_options(db)
    except ListingServiceError as exc:
        logger.exception("Could not load public listings: %s", exc)

        featured_listings = []
        filter_options = {
            "cities": [],
            "property_types": [],
            "bedrooms": [],
            "rent_range": {
                "minimum": None,
                "maximum": None,
            },
        }

    return templates.TemplateResponse(
        request=request,
        name="listings/listings.html",
        context=_base_context(
            request,
            page_title="Find an apartment",
            page_description=(
                "Search accessible rental properties with "
                "Smart Property AI."
            ),
            featured_listings=featured_listings,
            filter_options=filter_options,
        ),
    )


@router.get(
    "/search",
    response_class=HTMLResponse,
    name="search_listings",
)
def search_listings_page(
    request: Request,
    q: str | None = Query(default=None, max_length=200),
    city: str | None = Query(default=None, max_length=120),
    property_type: str | None = Query(
        default=None,
        max_length=80,
    ),
    minimum_rent: Decimal | None = Query(
        default=None,
        ge=0,
    ),
    maximum_rent: Decimal | None = Query(
        default=None,
        ge=0,
    ),
    bedrooms: int | None = Query(default=None, ge=0, le=50),
    bathrooms: int | None = Query(default=None, ge=0, le=50),
    minimum_area: Decimal | None = Query(default=None, ge=0),
    furnished: bool | None = Query(default=None),
    accessible: bool | None = Query(default=None),
    pets_allowed: bool | None = Query(default=None),
    parking: bool | None = Query(default=None),
    sort: str = Query(
        default="newest",
        pattern=(
            "^(newest|oldest|rent_low|rent_high|"
            "bedrooms_high|city)$"
        ),
    ),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=12, ge=1, le=100),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """
    Search and filter available public listings.
    """

    parameters = _search_parameters(
        q=q,
        city=city,
        property_type=property_type,
        minimum_rent=minimum_rent,
        maximum_rent=maximum_rent,
        bedrooms=bedrooms,
        bathrooms=bathrooms,
        minimum_area=minimum_area,
        furnished=furnished,
        accessible=accessible,
        pets_allowed=pets_allowed,
        parking=parking,
        sort=sort,
    )

    error_message = None

    try:
        results = search_listings(
            db,
            **parameters,
            page=page,
            per_page=per_page,
        )
    except InvalidSearchError as exc:
        error_message = str(exc)

        results = search_listings(
            db,
            page=1,
            per_page=per_page,
        )
    except ListingServiceError as exc:
        logger.exception("Listing search failed: %s", exc)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The apartment search is temporarily unavailable.",
        ) from exc

    filter_options = get_filter_options(db)
    url_values = _query_values(parameters)

    pagination = {
        "page": results.page,
        "pages": results.pages,
        "total": results.total,
        "per_page": results.per_page,
        "has_previous": results.has_previous,
        "has_next": results.has_next,
        "previous_page": results.previous_page,
        "next_page": results.next_page,
        "previous_url": (
            _pagination_url(
                request,
                url_values,
                results.previous_page,
            )
            if results.previous_page
            else None
        ),
        "next_url": (
            _pagination_url(
                request,
                url_values,
                results.next_page,
            )
            if results.next_page
            else None
        ),
    }

    return templates.TemplateResponse(
        request=request,
        name="listings/search_results.html",
        context=_base_context(
            request,
            page_title="Apartment search results",
            page_description=(
                f"{results.total} rental properties found."
            ),
            listings=results.items,
            results=results,
            pagination=pagination,
            filters=parameters,
            query_values=url_values,
            filter_options=filter_options,
            error_message=error_message,
        ),
    )


@router.get(
    "/guided_search_page",
    response_class=HTMLResponse,
    name="guided_search_page",
)
def guided_search_page(
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """
    Display the accessible step-by-step apartment search.
    """

    try:
        filter_options = get_filter_options(db)
    except ListingServiceError as exc:
        logger.exception(
            "Could not load guided-search options: %s",
            exc,
        )

        filter_options = {
            "cities": [],
            "property_types": [],
            "bedrooms": [],
            "rent_range": {
                "minimum": None,
                "maximum": None,
            },
        }

    return templates.TemplateResponse(
        request=request,
        name="listings/guided_search.html",
        context=_base_context(
            request,
            page_title="Guided apartment search",
            page_description=(
                "Find a suitable apartment using accessible "
                "step-by-step guidance."
            ),
            filter_options=filter_options,
        ),
    )


@router.get(
    "/{property_id}",
    response_class=HTMLResponse,
    name="listing_details",
)
def listing_details_page(
    property_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """
    Display one public property listing.
    """

    try:
        listing = get_listing(db, property_id)
        similar_listings = get_similar_listings(
            db,
            property_id,
            limit=3,
        )

        try:
            increment_listing_impressions(db, property_id)
        except Exception as exc:
            # Impression tracking must never prevent page access.
            logger.warning(
                "Could not record impression for property %s: %s",
                property_id,
                exc,
            )

    except ListingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The requested property listing was not found.",
        ) from exc
    except ListingServiceError as exc:
        logger.exception(
            "Could not load listing %s: %s",
            property_id,
            exc,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The property listing could not be loaded.",
        ) from exc

    return templates.TemplateResponse(
        request=request,
        name="listings/listing_details.html",
        context=_base_context(
            request,
            page_title=listing["title"],
            page_description=listing.get("description", ""),
            listing=listing,
            property=listing,
            units=listing.get("units", []),
            similar_listings=similar_listings,
        ),
    )


@router.get(
    "/{property_id}/apply",
    response_class=HTMLResponse,
    name="listing_application",
)
def application_page(
    property_id: int,
    request: Request,
    unit_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """
    Display the rental application form.

    The POST handler will be added with the application service.
    """

    try:
        listing = get_listing(db, property_id)
    except ListingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The requested property listing was not found.",
        ) from exc

    selected_unit = None

    if unit_id is not None:
        selected_unit = next(
            (
                unit
                for unit in listing.get("units", [])
                if unit.get("id") == unit_id
            ),
            None,
        )

        if selected_unit is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="The selected unit is not available.",
            )

    return templates.TemplateResponse(
        request=request,
        name="listings/application.html",
        context=_base_context(
            request,
            page_title=f"Apply for {listing['title']}",
            listing=listing,
            property=listing,
            units=listing.get("units", []),
            selected_unit=selected_unit,
        ),
    )


@router.get(
    "/{property_id}/appointment",
    response_class=HTMLResponse,
    name="listing_appointment",
)
def appointment_page(
    property_id: int,
    request: Request,
    unit_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """
    Display the viewing-appointment request form.

    Appointment storage and 30-minute reminders are added in the
    appointment service stage.
    """

    try:
        listing = get_listing(db, property_id)
    except ListingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The requested property listing was not found.",
        ) from exc

    selected_unit = None

    if unit_id is not None:
        selected_unit = next(
            (
                unit
                for unit in listing.get("units", [])
                if unit.get("id") == unit_id
            ),
            None,
        )

        if selected_unit is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="The selected unit is not available.",
            )

    return templates.TemplateResponse(
        request=request,
        name="listings/appointment.html",
        context=_base_context(
            request,
            page_title=f"Book a viewing for {listing['title']}",
            listing=listing,
            property=listing,
            units=listing.get("units", []),
            selected_unit=selected_unit,
        ),
    )


@router.post(
    "/{property_id}/apply",
    name="listing_application_submit",
)




@router.post(
    "/{property_id}/appointment",
    name="listing_appointment_submit",
)

@router.get(
    "/api/search/suggestions",
    name="listing_search_suggestions",
)
def listing_search_suggestions(
    q: str = Query(min_length=2, max_length=100),
    limit: int = Query(default=6, ge=1, le=20),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Return lightweight listing suggestions for autocomplete.
    """

    try:
        results = search_listings(
            db,
            query_text=q,
            page=1,
            per_page=limit,
        )
    except ListingServiceError as exc:
        logger.exception(
            "Search-suggestion request failed: %s",
            exc,
        )

        return {
            "query": q,
            "suggestions": [],
        }

    suggestions = [
        {
            "id": listing["id"],
            "title": listing["title"],
            "city": listing.get("city"),
            "address": listing.get("address"),
            "minimum_rent": listing.get("minimum_rent"),
            "image_url": listing.get("image_url"),
            "url": str(
                request_url_for_listing(
                    listing["id"]
                )
            ),
        }
        for listing in results.items
    ]

    return {
        "query": q,
        "suggestions": suggestions,
    }


def request_url_for_listing(property_id: int) -> str:
    """
    Return a relative public listing URL.

    Keeping this relative makes it usable in development and production.
    """

    return f"/listings/{property_id}"





templates = Jinja2Templates(directory="templates")


def _decimal_or_none(value: Optional[str]) -> Optional[Decimal]:
    if value is None or not value.strip():
        return None

    try:
        amount = Decimal(value.strip())
    except (InvalidOperation, ValueError):
        return None

    return amount if amount >= 0 else None


def _listing_context(
    request: Request,
    listings: list[Listing],
    properties: list[Property],
    units: list[Unit],
    **extra: object,
) -> dict:
    context = {
        "request": request,
        "listings": listings,
        "properties_by_id": {item.id: item for item in properties},
        "units_by_id": {item.id: item for item in units},
        "current_user": request.session.get("user"),
        "is_authenticated": bool(
            request.session.get("user_id")
            or request.session.get("username")
            or request.session.get("user")
        ),
    }
    context.update(extra)
    return context


def _filter_options(db: Session) -> dict:
    cities = [
        city
        for (city,) in (
            db.query(Property.city)
            .filter(Property.city.isnot(None))
            .distinct()
            .order_by(Property.city.asc())
            .all()
        )
        if city
    ]

    bedroom_values = [
        bedrooms
        for (bedrooms,) in (
            db.query(Unit.bedrooms)
            .filter(Unit.bedrooms.isnot(None))
            .distinct()
            .order_by(Unit.bedrooms.asc())
            .all()
        )
    ]

    return {
        "cities": cities,
        "bedrooms": bedroom_values,
        "property_types": [
            value
            for (value,) in (
                db.query(Property.property_type)
                .filter(Property.property_type.isnot(None))
                .distinct()
                .order_by(Property.property_type.asc())
                .all()
            )
            if value
        ],
    }


def _search_published_listings(
    db: Session,
    search_text: Optional[str] = None,
    city: Optional[str] = None,
    property_type: Optional[str] = None,
    min_rent: Optional[str] = None,
    max_rent: Optional[str] = None,
    bedrooms: Optional[int] = None,
    wheelchair_accessible: bool = False,
    pets_allowed: bool = False,
) -> tuple[list[Listing], list[Property], list[Unit]]:
    query = (
        db.query(Listing)
        .join(Property, Property.id == Listing.property_id)
        .outerjoin(Unit, Unit.id == Listing.unit_id)
        .filter(Listing.status == ListingStatus.PUBLISHED)
    )

    if search_text and search_text.strip():
        term = f"%{search_text.strip()}%"
        query = query.filter(
            or_(
                Listing.title.ilike(term),
                Listing.description.ilike(term),
                Property.name.ilike(term),
                Property.city.ilike(term),
                Property.postal_code.ilike(term),
            )
        )

    if city and city.strip():
        query = query.filter(Property.city.ilike(city.strip()))

    if property_type and property_type.strip():
        query = query.filter(Property.property_type == property_type.strip())

    minimum = _decimal_or_none(min_rent)
    maximum = _decimal_or_none(max_rent)

    if minimum is not None:
        query = query.filter(Listing.monthly_rent >= minimum)

    if maximum is not None:
        query = query.filter(Listing.monthly_rent <= maximum)

    if bedrooms is not None and bedrooms >= 0:
        query = query.filter(Unit.bedrooms >= bedrooms)

    if wheelchair_accessible:
        query = query.filter(Unit.wheelchair_accessible.is_(True))

    if pets_allowed:
        query = query.filter(Unit.pets_allowed.is_(True))

    listings = (
        query.order_by(
            Listing.published_at.desc(),
            Listing.created_at.desc(),
        )
        .distinct()
        .all()
    )

    property_ids = {listing.property_id for listing in listings}
    unit_ids = {listing.unit_id for listing in listings if listing.unit_id}

    properties = (
        db.query(Property).filter(Property.id.in_(property_ids)).all()
        if property_ids
        else []
    )
    units = (
        db.query(Unit).filter(Unit.id.in_(unit_ids)).all()
        if unit_ids
        else []
    )

    return listings, properties, units


@router.get("/apartments", name="listings_page")
def listings_page(
    request: Request,
    db: Session = Depends(get_db),
):
    listings, properties, units = _search_published_listings(db)

    return templates.TemplateResponse(
        request=request,
        name="listings/listings.html",
        context=_listing_context(
            request,
            listings,
            properties,
            units,
            filter_options=_filter_options(db),
            filters={},
        ),
    )


@router.get("/find-an-apartment", name="find_apartment")
def find_apartment():
    return RedirectResponse(
        url="/apartments",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/find-apartment", name="find_apartment_alias")
def find_apartment_alias():
    return RedirectResponse(
        url="/apartments",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/listings", name="listings_alias")
def listings_alias():
    return RedirectResponse(
        url="/apartments",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/apartments/search", name="search_results")
def search_results(
    request: Request,
    q: Optional[str] = Query(default=None, max_length=150),
    city: Optional[str] = Query(default=None, max_length=100),
    property_type: Optional[str] = Query(default=None, max_length=50),
    min_rent: Optional[str] = Query(default=None, max_length=20),
    max_rent: Optional[str] = Query(default=None, max_length=20),
    bedrooms: Optional[int] = Query(default=None, ge=0, le=20),
    wheelchair_accessible: bool = Query(default=False),
    pets_allowed: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    listings, properties, units = _search_published_listings(
        db=db,
        search_text=q,
        city=city,
        property_type=property_type,
        min_rent=min_rent,
        max_rent=max_rent,
        bedrooms=bedrooms,
        wheelchair_accessible=wheelchair_accessible,
        pets_allowed=pets_allowed,
    )

    filters = {
        "q": q or "",
        "city": city or "",
        "property_type": property_type or "",
        "min_rent": min_rent or "",
        "max_rent": max_rent or "",
        "bedrooms": bedrooms,
        "wheelchair_accessible": wheelchair_accessible,
        "pets_allowed": pets_allowed,
    }

    return templates.TemplateResponse(
        request=request,
        name="listings/search_results.html",
        context=_listing_context(
            request,
            listings,
            properties,
            units,
            query=q or "",
            filters=filters,
            filter_options=_filter_options(db),
            result_count=len(listings),
        ),
    )


@router.get("/guided-search", name="guided_search")
def guided_search(
    request: Request,
    db: Session = Depends(get_db),
):
    return templates.TemplateResponse(
        request=request,
        name="listings/guided_search.html",
        context={
            "request": request,
            "filter_options": _filter_options(db),
            "current_user": request.session.get("user"),
            "is_authenticated": bool(
                request.session.get("user_id")
                or request.session.get("username")
                or request.session.get("user")
            ),
        },
    )


@router.get("/apartments/{listing_id}", name="listing_details")
def listing_details(
    listing_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    listing = (
        db.query(Listing)
        .filter(
            Listing.id == listing_id,
            Listing.status == ListingStatus.PUBLISHED,
        )
        .first()
    )

    if listing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found.",
        )

    property_item = (
        db.query(Property)
        .filter(Property.id == listing.property_id)
        .first()
    )
    unit = (
        db.query(Unit)
        .filter(Unit.id == listing.unit_id)
        .first()
        if listing.unit_id
        else None
    )

    return templates.TemplateResponse(
        request=request,
        name="listings/listing_details.html",
        context={
            "request": request,
            "listing": listing,
            "property": property_item,
            "unit": unit,
            "current_user": request.session.get("user"),
            "is_authenticated": bool(
                request.session.get("user_id")
                or request.session.get("username")
                or request.session.get("user")
            ),
        },
    )
