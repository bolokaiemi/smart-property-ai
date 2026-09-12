"""
Public property-listing and apartment-search services.

This module contains database operations used by public listing routes.
It does not create HTTP responses and can therefore be reused by API,
HTML, automation and AI-assistant routes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from math import ceil
from typing import Any, Iterable

from sqlalchemy import String, and_, asc, cast, desc, func, or_
from sqlalchemy.orm import Session

from database.models import Property, Unit


@dataclass(slots=True)
class ListingSearchResult:
    """Paginated result returned by listing searches."""

    items: list[dict[str, Any]]
    page: int
    per_page: int
    total: int
    pages: int
    has_previous: bool
    has_next: bool
    previous_page: int | None
    next_page: int | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ListingServiceError(Exception):
    """Base exception for listing-service errors."""


class ListingNotFoundError(ListingServiceError):
    """Raised when a public listing cannot be found."""


class InvalidSearchError(ListingServiceError):
    """Raised when search parameters are invalid."""


# Common column names supported by the service.
PROPERTY_TITLE_FIELDS = ("title", "name", "property_name")
PROPERTY_DESCRIPTION_FIELDS = (
    "description",
    "public_description",
    "summary",
)
PROPERTY_ADDRESS_FIELDS = (
    "address",
    "street_address",
    "address_line_1",
)
PROPERTY_POSTAL_CODE_FIELDS = (
    "postal_code",
    "zip_code",
    "postcode",
)
PROPERTY_IMAGE_FIELDS = (
    "image_url",
    "featured_image",
    "cover_image",
    "main_image",
)
PROPERTY_ACTIVE_FIELDS = (
    "is_active",
    "active",
    "published",
    "is_published",
)
PROPERTY_FEATURED_FIELDS = (
    "is_featured",
    "featured",
)
PROPERTY_CREATED_FIELDS = (
    "created_at",
    "date_created",
)

UNIT_RENT_FIELDS = (
    "monthly_rent",
    "rent_amount",
    "rent",
    "price",
)
UNIT_BEDROOM_FIELDS = (
    "bedrooms",
    "bedroom_count",
    "number_of_bedrooms",
)
UNIT_BATHROOM_FIELDS = (
    "bathrooms",
    "bathroom_count",
    "number_of_bathrooms",
)
UNIT_AREA_FIELDS = (
    "area_sqm",
    "size_sqm",
    "square_meters",
    "floor_area",
)
UNIT_NUMBER_FIELDS = (
    "unit_number",
    "number",
    "name",
)
UNIT_ACTIVE_FIELDS = (
    "is_active",
    "active",
)
UNIT_AVAILABLE_FIELDS = (
    "is_available",
    "available",
)


def _model_attribute(model: Any, names: Iterable[str]) -> Any | None:
    """Return the first SQLAlchemy attribute available on a model."""

    for name in names:
        if hasattr(model, name):
            return getattr(model, name)

    return None


def _object_value(
    instance: Any,
    names: Iterable[str],
    default: Any = None,
) -> Any:
    """Return the first available non-None object attribute."""

    for name in names:
        if hasattr(instance, name):
            value = getattr(instance, name)

            if value is not None:
                return value

    return default


def _enum_value(value: Any) -> Any:
    """Return an enum's stored value or the original value."""

    if value is None:
        return None

    return getattr(value, "value", value)


def _serialize_value(value: Any) -> Any:
    """Convert values into JSON- and Jinja-friendly values."""

    if value is None:
        return None

    if isinstance(value, Decimal):
        return float(value)

    if hasattr(value, "isoformat"):
        return value.isoformat()

    return _enum_value(value)


def _positive_integer(
    value: Any,
    default: int,
    maximum: int | None = None,
) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default

    number = max(1, number)

    if maximum is not None:
        number = min(number, maximum)

    return number


def _decimal_or_none(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None

    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise InvalidSearchError(
            f"Invalid numeric search value: {value}"
        ) from exc

    if number < 0:
        raise InvalidSearchError(
            "Search amounts cannot be negative."
        )

    return number


def _boolean_value(value: Any) -> bool | None:
    if value in (None, ""):
        return None

    if isinstance(value, bool):
        return value

    normalized = str(value).strip().lower()

    if normalized in {"1", "true", "yes", "on"}:
        return True

    if normalized in {"0", "false", "no", "off"}:
        return False

    return None


def _active_expression(model: Any, fields: Iterable[str]) -> Any | None:
    column = _model_attribute(model, fields)

    if column is None:
        return None

    return column.is_(True)


def _status_expression(
    model: Any,
    allowed_values: Iterable[str],
) -> Any | None:
    status_column = _model_attribute(model, ("status",))

    if status_column is None:
        return None

    values = [value.lower() for value in allowed_values]

    return func.lower(cast(status_column, String)).in_(values)


def _public_property_filters() -> list[Any]:
    filters: list[Any] = []

    active_filter = _active_expression(
        Property,
        PROPERTY_ACTIVE_FIELDS,
    )

    if active_filter is not None:
        filters.append(active_filter)

    status_filter = _status_expression(
        Property,
        ("active", "published", "available"),
    )

    if status_filter is not None:
        filters.append(status_filter)

    return filters


def _available_unit_filters() -> list[Any]:
    filters: list[Any] = []

    active_filter = _active_expression(
        Unit,
        UNIT_ACTIVE_FIELDS,
    )

    if active_filter is not None:
        filters.append(active_filter)

    available_filter = _active_expression(
        Unit,
        UNIT_AVAILABLE_FIELDS,
    )

    if available_filter is not None:
        filters.append(available_filter)

    status_filter = _status_expression(
        Unit,
        ("available", "vacant", "ready"),
    )

    if status_filter is not None:
        filters.append(status_filter)

    return filters


def _property_join_condition() -> Any:
    unit_property_id = _model_attribute(
        Unit,
        ("property_id",),
    )
    property_id = _model_attribute(
        Property,
        ("id",),
    )

    if unit_property_id is None or property_id is None:
        raise ListingServiceError(
            "Unit.property_id and Property.id are required."
        )

    return unit_property_id == property_id


def _unit_to_dict(unit: Unit) -> dict[str, Any]:
    """Convert a unit into a public listing dictionary."""

    unit_id = _object_value(unit, ("id",))
    rent = _object_value(unit, UNIT_RENT_FIELDS)
    bedrooms = _object_value(unit, UNIT_BEDROOM_FIELDS)
    bathrooms = _object_value(unit, UNIT_BATHROOM_FIELDS)
    area = _object_value(unit, UNIT_AREA_FIELDS)
    unit_number = _object_value(
        unit,
        UNIT_NUMBER_FIELDS,
        f"Unit {unit_id}",
    )

    return {
        "id": unit_id,
        "property_id": _object_value(unit, ("property_id",)),
        "unit_number": unit_number,
        "monthly_rent": _serialize_value(rent),
        "bedrooms": _serialize_value(bedrooms),
        "bathrooms": _serialize_value(bathrooms),
        "area_sqm": _serialize_value(area),
        "floor": _serialize_value(
            _object_value(unit, ("floor", "floor_number"))
        ),
        "status": _serialize_value(
            _object_value(unit, ("status",))
        ),
        "is_furnished": bool(
            _object_value(
                unit,
                ("is_furnished", "furnished"),
                False,
            )
        ),
        "is_available": bool(
            _object_value(
                unit,
                UNIT_AVAILABLE_FIELDS,
                True,
            )
        ),
        "available_from": _serialize_value(
            _object_value(
                unit,
                ("available_from", "availability_date"),
            )
        ),
        "description": _object_value(
            unit,
            ("description", "public_description"),
            "",
        ),
    }


def _property_to_dict(
    property_record: Property,
    units: list[Unit] | None = None,
) -> dict[str, Any]:
    """Convert a property and its units into a public dictionary."""

    public_units = [
        _unit_to_dict(unit)
        for unit in (units or [])
    ]

    rents = [
        unit["monthly_rent"]
        for unit in public_units
        if unit["monthly_rent"] is not None
    ]

    bedrooms = [
        unit["bedrooms"]
        for unit in public_units
        if unit["bedrooms"] is not None
    ]

    return {
        "id": _object_value(property_record, ("id",)),
        "title": _object_value(
            property_record,
            PROPERTY_TITLE_FIELDS,
            "Property",
        ),
        "description": _object_value(
            property_record,
            PROPERTY_DESCRIPTION_FIELDS,
            "",
        ),
        "property_type": _serialize_value(
            _object_value(
                property_record,
                ("property_type", "type"),
            )
        ),
        "address": _object_value(
            property_record,
            PROPERTY_ADDRESS_FIELDS,
            "",
        ),
        "address_line_2": _object_value(
            property_record,
            ("address_line_2",),
            "",
        ),
        "city": _object_value(
            property_record,
            ("city", "town"),
            "",
        ),
        "state": _object_value(
            property_record,
            ("state", "region"),
            "",
        ),
        "postal_code": _object_value(
            property_record,
            PROPERTY_POSTAL_CODE_FIELDS,
            "",
        ),
        "country": _object_value(
            property_record,
            ("country",),
            "",
        ),
        "image_url": _object_value(
            property_record,
            PROPERTY_IMAGE_FIELDS,
            "/static/images/property-placeholder.jpg",
        ),
        "latitude": _serialize_value(
            _object_value(property_record, ("latitude",))
        ),
        "longitude": _serialize_value(
            _object_value(property_record, ("longitude",))
        ),
        "is_featured": bool(
            _object_value(
                property_record,
                PROPERTY_FEATURED_FIELDS,
                False,
            )
        ),
        "is_active": bool(
            _object_value(
                property_record,
                PROPERTY_ACTIVE_FIELDS,
                True,
            )
        ),
        "status": _serialize_value(
            _object_value(property_record, ("status",))
        ),
        "amenities": _object_value(
            property_record,
            ("amenities",),
            [],
        ),
        "accessibility_features": _object_value(
            property_record,
            ("accessibility_features",),
            [],
        ),
        "created_at": _serialize_value(
            _object_value(
                property_record,
                PROPERTY_CREATED_FIELDS,
            )
        ),
        "available_units": len(public_units),
        "minimum_rent": min(rents) if rents else None,
        "maximum_rent": max(rents) if rents else None,
        "minimum_bedrooms": min(bedrooms) if bedrooms else None,
        "maximum_bedrooms": max(bedrooms) if bedrooms else None,
        "units": public_units,
    }


def _units_by_property(
    db: Session,
    property_ids: list[int],
) -> dict[int, list[Unit]]:
    """Fetch available units and group them by property ID."""

    if not property_ids:
        return {}

    property_id_column = _model_attribute(Unit, ("property_id",))

    if property_id_column is None:
        return {}

    query = db.query(Unit).filter(
        property_id_column.in_(property_ids)
    )

    available_filters = _available_unit_filters()

    if available_filters:
        query = query.filter(and_(*available_filters))

    units = query.all()
    grouped: dict[int, list[Unit]] = {}

    for unit in units:
        property_id = _object_value(unit, ("property_id",))

        if property_id is not None:
            grouped.setdefault(property_id, []).append(unit)

    return grouped


def search_listings(
    db: Session,
    *,
    query_text: str | None = None,
    city: str | None = None,
    property_type: str | None = None,
    minimum_rent: Decimal | float | str | None = None,
    maximum_rent: Decimal | float | str | None = None,
    minimum_bedrooms: int | str | None = None,
    minimum_bathrooms: int | str | None = None,
    minimum_area: Decimal | float | str | None = None,
    furnished: bool | str | None = None,
    accessible: bool | str | None = None,
    pets_allowed: bool | str | None = None,
    parking: bool | str | None = None,
    sort: str = "newest",
    page: int = 1,
    per_page: int = 12,
) -> ListingSearchResult:
    """
    Search public properties that have matching available units.

    Supported sort values:
        newest
        oldest
        rent_low
        rent_high
        bedrooms_high
        city
    """

    page = _positive_integer(page, 1)
    per_page = _positive_integer(per_page, 12, maximum=100)

    minimum_rent_value = _decimal_or_none(minimum_rent)
    maximum_rent_value = _decimal_or_none(maximum_rent)
    minimum_area_value = _decimal_or_none(minimum_area)

    if (
        minimum_rent_value is not None
        and maximum_rent_value is not None
        and minimum_rent_value > maximum_rent_value
    ):
        raise InvalidSearchError(
            "Minimum rent cannot be greater than maximum rent."
        )

    try:
        bedrooms_value = (
            int(minimum_bedrooms)
            if minimum_bedrooms not in (None, "")
            else None
        )
        bathrooms_value = (
            int(minimum_bathrooms)
            if minimum_bathrooms not in (None, "")
            else None
        )
    except (TypeError, ValueError) as exc:
        raise InvalidSearchError(
            "Bedroom and bathroom values must be whole numbers."
        ) from exc

    if bedrooms_value is not None and bedrooms_value < 0:
        raise InvalidSearchError(
            "Minimum bedrooms cannot be negative."
        )

    if bathrooms_value is not None and bathrooms_value < 0:
        raise InvalidSearchError(
            "Minimum bathrooms cannot be negative."
        )

    property_id_column = _model_attribute(Property, ("id",))
    unit_id_column = _model_attribute(Unit, ("id",))

    if property_id_column is None or unit_id_column is None:
        raise ListingServiceError(
            "Property.id and Unit.id are required."
        )

    query = db.query(Property).join(
        Unit,
        _property_join_condition(),
    )

    filters: list[Any] = []
    filters.extend(_public_property_filters())
    filters.extend(_available_unit_filters())

    search_value = (query_text or "").strip()

    if search_value:
        search_columns = [
            _model_attribute(Property, PROPERTY_TITLE_FIELDS),
            _model_attribute(Property, PROPERTY_DESCRIPTION_FIELDS),
            _model_attribute(Property, PROPERTY_ADDRESS_FIELDS),
            _model_attribute(Property, ("city", "town")),
            _model_attribute(Property, PROPERTY_POSTAL_CODE_FIELDS),
        ]

        search_columns = [
            column
            for column in search_columns
            if column is not None
        ]

        if search_columns:
            pattern = f"%{search_value}%"
            filters.append(
                or_(
                    *[
                        cast(column, String).ilike(pattern)
                        for column in search_columns
                    ]
                )
            )

    city_column = _model_attribute(Property, ("city", "town"))

    if city and city_column is not None:
        filters.append(
            cast(city_column, String).ilike(f"%{city.strip()}%")
        )

    type_column = _model_attribute(
        Property,
        ("property_type", "type"),
    )

    if property_type and type_column is not None:
        filters.append(
            func.lower(cast(type_column, String))
            == property_type.strip().lower()
        )

    rent_column = _model_attribute(Unit, UNIT_RENT_FIELDS)

    if minimum_rent_value is not None and rent_column is not None:
        filters.append(rent_column >= minimum_rent_value)

    if maximum_rent_value is not None and rent_column is not None:
        filters.append(rent_column <= maximum_rent_value)

    bedroom_column = _model_attribute(Unit, UNIT_BEDROOM_FIELDS)

    if bedrooms_value is not None and bedroom_column is not None:
        filters.append(bedroom_column >= bedrooms_value)

    bathroom_column = _model_attribute(Unit, UNIT_BATHROOM_FIELDS)

    if bathrooms_value is not None and bathroom_column is not None:
        filters.append(bathroom_column >= bathrooms_value)

    area_column = _model_attribute(Unit, UNIT_AREA_FIELDS)

    if minimum_area_value is not None and area_column is not None:
        filters.append(area_column >= minimum_area_value)

    furnished_value = _boolean_value(furnished)
    furnished_column = _model_attribute(
        Unit,
        ("is_furnished", "furnished"),
    )

    if furnished_value is not None and furnished_column is not None:
        filters.append(furnished_column.is_(furnished_value))

    accessible_value = _boolean_value(accessible)

    if accessible_value:
        accessibility_columns = [
            _model_attribute(
                Property,
                ("is_accessible", "wheelchair_accessible"),
            ),
            _model_attribute(
                Unit,
                ("is_accessible", "wheelchair_accessible"),
            ),
        ]

        accessibility_columns = [
            column
            for column in accessibility_columns
            if column is not None
        ]

        if accessibility_columns:
            filters.append(
                or_(
                    *[
                        column.is_(True)
                        for column in accessibility_columns
                    ]
                )
            )

    pets_value = _boolean_value(pets_allowed)
    pets_column = _model_attribute(
        Property,
        ("pets_allowed", "allows_pets"),
    ) or _model_attribute(
        Unit,
        ("pets_allowed", "allows_pets"),
    )

    if pets_value is not None and pets_column is not None:
        filters.append(pets_column.is_(pets_value))

    parking_value = _boolean_value(parking)
    parking_column = _model_attribute(
        Property,
        ("has_parking", "parking_available"),
    ) or _model_attribute(
        Unit,
        ("has_parking", "parking_available"),
    )

    if parking_value is not None and parking_column is not None:
        filters.append(parking_column.is_(parking_value))

    if filters:
        query = query.filter(and_(*filters))

    query = query.distinct()

    count_query = query.with_entities(
        func.count(func.distinct(property_id_column))
    )

    total = int(count_query.scalar() or 0)

    created_column = _model_attribute(
        Property,
        PROPERTY_CREATED_FIELDS,
    )

    if sort == "oldest" and created_column is not None:
        query = query.order_by(asc(created_column))
    elif sort == "rent_low" and rent_column is not None:
        query = query.order_by(asc(rent_column))
    elif sort == "rent_high" and rent_column is not None:
        query = query.order_by(desc(rent_column))
    elif sort == "bedrooms_high" and bedroom_column is not None:
        query = query.order_by(desc(bedroom_column))
    elif sort == "city" and city_column is not None:
        query = query.order_by(asc(city_column))
    elif created_column is not None:
        query = query.order_by(desc(created_column))
    else:
        query = query.order_by(desc(property_id_column))

    offset = (page - 1) * per_page

    properties = query.offset(offset).limit(per_page).all()

    property_ids = [
        _object_value(property_record, ("id",))
        for property_record in properties
    ]

    units = _units_by_property(db, property_ids)

    items = [
        _property_to_dict(
            property_record,
            units.get(
                _object_value(property_record, ("id",)),
                [],
            ),
        )
        for property_record in properties
    ]

    pages = ceil(total / per_page) if total else 0

    return ListingSearchResult(
        items=items,
        page=page,
        per_page=per_page,
        total=total,
        pages=pages,
        has_previous=page > 1,
        has_next=page < pages,
        previous_page=page - 1 if page > 1 else None,
        next_page=page + 1 if page < pages else None,
    )


def get_listing(
    db: Session,
    property_id: int,
) -> dict[str, Any]:
    """Return one public property with its available units."""

    property_id_column = _model_attribute(Property, ("id",))

    if property_id_column is None:
        raise ListingServiceError("Property.id is required.")

    query = db.query(Property).filter(
        property_id_column == property_id
    )

    public_filters = _public_property_filters()

    if public_filters:
        query = query.filter(and_(*public_filters))

    property_record = query.first()

    if property_record is None:
        raise ListingNotFoundError(
            "The requested listing was not found."
        )

    units_by_property = _units_by_property(db, [property_id])

    return _property_to_dict(
        property_record,
        units_by_property.get(property_id, []),
    )


def get_featured_listings(
    db: Session,
    limit: int = 6,
) -> list[dict[str, Any]]:
    """Return featured public properties for the homepage."""

    limit = _positive_integer(limit, 6, maximum=24)

    property_id_column = _model_attribute(Property, ("id",))

    if property_id_column is None:
        return []

    query = db.query(Property)

    public_filters = _public_property_filters()

    if public_filters:
        query = query.filter(and_(*public_filters))

    featured_column = _model_attribute(
        Property,
        PROPERTY_FEATURED_FIELDS,
    )

    if featured_column is not None:
        query = query.filter(featured_column.is_(True))

    created_column = _model_attribute(
        Property,
        PROPERTY_CREATED_FIELDS,
    )

    if created_column is not None:
        query = query.order_by(desc(created_column))
    else:
        query = query.order_by(desc(property_id_column))

    properties = query.limit(limit).all()

    property_ids = [
        _object_value(property_record, ("id",))
        for property_record in properties
    ]

    units = _units_by_property(db, property_ids)

    return [
        _property_to_dict(
            property_record,
            units.get(
                _object_value(property_record, ("id",)),
                [],
            ),
        )
        for property_record in properties
    ]


def get_filter_options(db: Session) -> dict[str, Any]:
    """Return available cities, property types and bedroom values."""

    options: dict[str, Any] = {
        "cities": [],
        "property_types": [],
        "bedrooms": [],
        "rent_range": {
            "minimum": None,
            "maximum": None,
        },
    }

    city_column = _model_attribute(Property, ("city", "town"))

    if city_column is not None:
        options["cities"] = [
            row[0]
            for row in (
                db.query(city_column)
                .filter(city_column.isnot(None))
                .filter(city_column != "")
                .distinct()
                .order_by(asc(city_column))
                .all()
            )
        ]

    type_column = _model_attribute(
        Property,
        ("property_type", "type"),
    )

    if type_column is not None:
        type_values = (
            db.query(type_column)
            .filter(type_column.isnot(None))
            .distinct()
            .all()
        )

        options["property_types"] = sorted(
            {
                str(_enum_value(row[0]))
                for row in type_values
                if row[0] is not None
            }
        )

    bedroom_column = _model_attribute(Unit, UNIT_BEDROOM_FIELDS)

    if bedroom_column is not None:
        options["bedrooms"] = [
            row[0]
            for row in (
                db.query(bedroom_column)
                .filter(bedroom_column.isnot(None))
                .distinct()
                .order_by(asc(bedroom_column))
                .all()
            )
        ]

    rent_column = _model_attribute(Unit, UNIT_RENT_FIELDS)

    if rent_column is not None:
        minimum, maximum = db.query(
            func.min(rent_column),
            func.max(rent_column),
        ).one()

        options["rent_range"] = {
            "minimum": _serialize_value(minimum),
            "maximum": _serialize_value(maximum),
        }

    return options


def get_similar_listings(
    db: Session,
    property_id: int,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Return public listings in the same city or property category."""

    limit = _positive_integer(limit, 3, maximum=12)

    current = get_listing(db, property_id)

    property_id_column = _model_attribute(Property, ("id",))

    if property_id_column is None:
        return []

    query = db.query(Property).filter(
        property_id_column != property_id
    )

    filters = _public_property_filters()

    similarity_filters: list[Any] = []

    city_column = _model_attribute(Property, ("city", "town"))

    if current.get("city") and city_column is not None:
        similarity_filters.append(
            func.lower(cast(city_column, String))
            == str(current["city"]).lower()
        )

    type_column = _model_attribute(
        Property,
        ("property_type", "type"),
    )

    if current.get("property_type") and type_column is not None:
        similarity_filters.append(
            func.lower(cast(type_column, String))
            == str(current["property_type"]).lower()
        )

    if filters:
        query = query.filter(and_(*filters))

    if similarity_filters:
        query = query.filter(or_(*similarity_filters))

    query = query.order_by(desc(property_id_column))

    properties = query.limit(limit).all()

    property_ids = [
        _object_value(property_record, ("id",))
        for property_record in properties
    ]

    units = _units_by_property(db, property_ids)

    return [
        _property_to_dict(
            property_record,
            units.get(
                _object_value(property_record, ("id",)),
                [],
            ),
        )
        for property_record in properties
    ]


def increment_listing_impressions(
    db: Session,
    property_id: int,
) -> bool:
    """
    Increment a property's impression counter when such a field exists.

    This is intentionally separate from get_listing() so automated
    processes do not increase public-view statistics.
    """

    property_id_column = _model_attribute(Property, ("id",))

    if property_id_column is None:
        return False

    property_record = (
        db.query(Property)
        .filter(property_id_column == property_id)
        .first()
    )

    if property_record is None:
        return False

    impression_field = None

    for field_name in (
        "impressions",
        "impression_count",
        "view_count",
        "views",
    ):
        if hasattr(property_record, field_name):
            impression_field = field_name
            break

    if impression_field is None:
        return False

    current_value = getattr(
        property_record,
        impression_field,
        0,
    ) or 0

    setattr(
        property_record,
        impression_field,
        current_value + 1,
    )

    try:
        db.commit()
        db.refresh(property_record)
    except Exception:
        db.rollback()
        raise

    return True