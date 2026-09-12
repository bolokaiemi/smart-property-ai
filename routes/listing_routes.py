"""
Public apartment-listing routes for Smart Property AI.
"""

from __future__ import annotations

import logging
import secrets
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

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
    "/guided-search",
    response_class=HTMLResponse,
    name="guided_search",
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