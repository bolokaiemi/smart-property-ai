import enum
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
import builtins

from database.database import Base


def generate_uuid() -> str:
    """Return a random UUID string."""

    return str(uuid.uuid4())


def utc_now() -> datetime:
    """Return the current timezone-aware UTC datetime."""

    return datetime.now(timezone.utc)


class UserRole(str, enum.Enum):
    ADMINISTRATOR = "administrator"
    LANDLORD = "landlord"
    PROPERTY_MANAGER = "property_manager"
    MAINTENANCE_STAFF = "maintenance_staff"
    TENANT = "tenant"
    APPLICANT = "applicant"


class AccountStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class PropertyStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"


class UnitStatus(str, enum.Enum):
    VACANT = "vacant"
    OCCUPIED = "occupied"
    MAINTENANCE = "maintenance"
    UNAVAILABLE = "unavailable"


class ListingStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    PAUSED = "paused"
    RENTED = "rented"
    ARCHIVED = "archived"


class ListingEventType(str, enum.Enum):
    IMPRESSION = "impression"
    LISTING_VIEW = "listing_view"
    LOGIN = "login"
    LOGOUT = "logout"
    SEARCH_CLICK = "search_click"
    APPOINTMENT_REQUEST = "appointment_request"
    APPLICATION_STARTED = "application_started"
    APPLICATION_SUBMITTED = "application_submitted"


class LeaseStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    EXPIRING = "expiring"
    ENDED = "ended"
    TERMINATED = "terminated"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    PARTIALLY_PAID = "partially_paid"
    OVERDUE = "overdue"
    FAILED = "failed"
    REFUNDED = "refunded"


class RequestPriority(str, enum.Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"
    EMERGENCY = "emergency"


class RequestStatus(str, enum.Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    IN_PROGRESS = "in_progress"
    WAITING = "waiting"
    RESOLVED = "resolved"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class AppointmentStatus(str, enum.Enum):
    REQUESTED = "requested"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"


class CommunicationChannel(str, enum.Enum):
    PLATFORM = "platform"
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    SMS = "sms"
    PHONE = "phone"


class DeliveryStatus(str, enum.Enum):
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    READ = "read"


class DocumentType(str, enum.Enum):
    LEASE = "lease"
    APPLICATION = "application"
    INVOICE = "invoice"
    INSPECTION = "inspection"
    IDENTIFICATION = "identification"
    MAINTENANCE = "maintenance"
    OTHER = "other"


class ConsentType(str, enum.Enum):
    PRIVACY_POLICY = "privacy_policy"
    TERMS = "terms"
    MARKETING = "marketing"
    AI_PROCESSING = "ai_processing"
    MODEL_TRAINING = "model_training"
    VOICE_PROCESSING = "voice_processing"
    ANALYTICS = "analytics"


class DeviceStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    OFFLINE = "offline"
    REVOKED = "revoked"


# ==========================================================================
# Users and sessions
# ==========================================================================

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )

    full_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    username: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )

    phone_number: Mapped[Optional[str]] = mapped_column(
        String(40),
        nullable=True,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            native_enum=False,
        ),
        default=UserRole.APPLICANT,
        nullable=False,
        index=True,
    )

    status: Mapped[AccountStatus] = mapped_column(
        Enum(
            AccountStatus,
            native_enum=False,
        ),
        default=AccountStatus.ACTIVE,
        nullable=False,
    )

    preferred_language: Mapped[str] = mapped_column(
        String(10),
        default="en",
        nullable=False,
    )

    email_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    phone_verified: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    session_token_hash: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )

    ip_hash: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    user_agent: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )


# ==========================================================================
# Properties, units and listings
# ==========================================================================

class Property(Base):
    __tablename__ = "properties"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )

    owner_id: Mapped[str] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    manager_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    property_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    street_address: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    postal_code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    city: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    state: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    country: Mapped[str] = mapped_column(
        String(100),
        default="Germany",
        nullable=False,
    )

    latitude: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 7),
        nullable=True,
    )

    longitude: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 7),
        nullable=True,
    )

    status: Mapped[PropertyStatus] = mapped_column(
        Enum(
            PropertyStatus,
            native_enum=False,
        ),
        default=PropertyStatus.DRAFT,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class Unit(Base):
    __tablename__ = "units"

    __table_args__ = (
        UniqueConstraint(
            "property_id",
            "unit_number",
            name="uq_property_unit_number",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )

    property_id: Mapped[str] = mapped_column(
        ForeignKey(
            "properties.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    unit_number: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    floor: Mapped[Optional[str]] = mapped_column(
        String(30),
        nullable=True,
    )

    rooms: Mapped[Decimal] = mapped_column(
        Numeric(4, 1),
        nullable=False,
    )

    bedrooms: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    bathrooms: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    area_square_metres: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )

    monthly_rent: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    deposit_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        default="EUR",
        nullable=False,
    )

    wheelchair_accessible: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    pets_allowed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    status: Mapped[UnitStatus] = mapped_column(
        Enum(
            UnitStatus,
            native_enum=False,
        ),
        default=UnitStatus.VACANT,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )

    property_id: Mapped[str] = mapped_column(
        ForeignKey(
            "properties.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    unit_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey(
            "units.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    created_by_id: Mapped[str] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(220),
        nullable=False,
    )

    slug: Mapped[str] = mapped_column(
        String(250),
        unique=True,
        nullable=False,
        index=True,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    monthly_rent: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        default="EUR",
        nullable=False,
    )

    available_from: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )

    status: Mapped[ListingStatus] = mapped_column(
        Enum(
            ListingStatus,
            native_enum=False,
        ),
        default=ListingStatus.DRAFT,
        nullable=False,
        index=True,
    )

    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class ListingEvent(Base):
    __tablename__ = "listing_events"

    __table_args__ = (
        Index(
            "ix_listing_event_listing_created",
            "listing_id",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )

    listing_id: Mapped[str] = mapped_column(
        ForeignKey(
            "listings.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    user_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    session_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
    )

    event_type: Mapped[ListingEventType] = mapped_column(
        Enum(
            ListingEventType,
            native_enum=False,
        ),
        nullable=False,
        index=True,
    )

    language: Mapped[str] = mapped_column(
        String(10),
        default="en",
        nullable=False,
    )

    ip_hash: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    user_agent: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )


# ==========================================================================
# Tenancies, leases and payments
# ==========================================================================

class TenantProfile(Base):
    __tablename__ = "tenant_profiles"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        unique=True,
        nullable=False,
    )

    emergency_contact_name: Mapped[Optional[str]] = mapped_column(
        String(150),
        nullable=True,
    )

    emergency_contact_phone: Mapped[Optional[str]] = mapped_column(
        String(40),
        nullable=True,
    )

    accessibility_requirements: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )


class Lease(Base):
    __tablename__ = "leases"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )

    property_id: Mapped[str] = mapped_column(
        ForeignKey(
            "properties.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    unit_id: Mapped[str] = mapped_column(
        ForeignKey(
            "units.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    tenant_id: Mapped[str] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    landlord_id: Mapped[str] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    start_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    end_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )

    monthly_rent: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    deposit_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        default="EUR",
        nullable=False,
    )

    payment_due_day: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )

    renewal_reminder_days: Mapped[int] = mapped_column(
        Integer,
        default=60,
        nullable=False,
    )

    status: Mapped[LeaseStatus] = mapped_column(
        Enum(
            LeaseStatus,
            native_enum=False,
        ),
        default=LeaseStatus.DRAFT,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )

    lease_id: Mapped[str] = mapped_column(
        ForeignKey(
            "leases.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    tenant_id: Mapped[str] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        default="EUR",
        nullable=False,
    )

    due_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    paid_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    payment_reference: Mapped[Optional[str]] = mapped_column(
        String(150),
        unique=True,
        nullable=True,
    )

    status: Mapped[PaymentStatus] = mapped_column(
        Enum(
            PaymentStatus,
            native_enum=False,
        ),
        default=PaymentStatus.PENDING,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )


# ==========================================================================
# Maintenance, complaints and expenses
# ==========================================================================

class MaintenanceRequest(Base):
    __tablename__ = "maintenance_requests"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )

    property_id: Mapped[str] = mapped_column(
        ForeignKey(
            "properties.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    unit_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey(
            "units.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    submitted_by_id: Mapped[str] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    assigned_to_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    category: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    priority: Mapped[RequestPriority] = mapped_column(
        Enum(
            RequestPriority,
            native_enum=False,
        ),
        default=RequestPriority.NORMAL,
        nullable=False,
    )

    status: Mapped[RequestStatus] = mapped_column(
        Enum(
            RequestStatus,
            native_enum=False,
        ),
        default=RequestStatus.OPEN,
        nullable=False,
    )

    ai_summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class Complaint(Base):
    __tablename__ = "complaints"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )

    property_id: Mapped[str] = mapped_column(
        ForeignKey(
            "properties.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    submitted_by_id: Mapped[str] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    assigned_to_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    subject: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    priority: Mapped[RequestPriority] = mapped_column(
        Enum(
            RequestPriority,
            native_enum=False,
        ),
        default=RequestPriority.NORMAL,
        nullable=False,
    )

    status: Mapped[RequestStatus] = mapped_column(
        Enum(
            RequestStatus,
            native_enum=False,
        ),
        default=RequestStatus.OPEN,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )

    property_id: Mapped[str] = mapped_column(
        ForeignKey(
            "properties.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    maintenance_request_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey(
            "maintenance_requests.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    recorded_by_id: Mapped[str] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    category: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        default="EUR",
        nullable=False,
    )

    expense_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )


# ==========================================================================
# Documents, messages and appointments
# ==========================================================================

class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )

    uploaded_by_id: Mapped[str] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    property_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey(
            "properties.id",
            ondelete="CASCADE",
        ),
        nullable=True,
        index=True,
    )

    lease_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey(
            "leases.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    maintenance_request_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey(
            "maintenance_requests.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    document_type: Mapped[DocumentType] = mapped_column(
        Enum(
            DocumentType,
            native_enum=False,
        ),
        default=DocumentType.OTHER,
        nullable=False,
    )

    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    stored_filename: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )

    storage_path: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    mime_type: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    file_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    checksum: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
    )

    is_private: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )

    sender_id: Mapped[str] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    recipient_id: Mapped[str] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    property_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey(
            "properties.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    channel: Mapped[CommunicationChannel] = mapped_column(
        Enum(
            CommunicationChannel,
            native_enum=False,
        ),
        default=CommunicationChannel.PLATFORM,
        nullable=False,
    )

    subject: Mapped[Optional[str]] = mapped_column(
        String(200),
        nullable=True,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    language: Mapped[str] = mapped_column(
        String(10),
        default="en",
        nullable=False,
    )

    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )

    listing_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey(
            "listings.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    property_id: Mapped[str] = mapped_column(
        ForeignKey(
            "properties.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    requested_by_id: Mapped[str] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    assigned_to_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    appointment_type: Mapped[str] = mapped_column(
        String(80),
        default="property_viewing",
        nullable=False,
    )

    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    reminder_minutes: Mapped[int] = mapped_column(
        Integer,
        default=30,
        nullable=False,
    )

    reminder_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    status: Mapped[AppointmentStatus] = mapped_column(
        Enum(
            AppointmentStatus,
            native_enum=False,
        ),
        default=AppointmentStatus.REQUESTED,
        nullable=False,
    )

    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    notification_type: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
    )

    is_read: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    action_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )


class CommunicationLog(Base):
    __tablename__ = "communication_logs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )

    user_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    channel: Mapped[CommunicationChannel] = mapped_column(
        Enum(
            CommunicationChannel,
            native_enum=False,
        ),
        nullable=False,
    )

    recipient: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    message_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    provider_reference: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    delivery_status: Mapped[DeliveryStatus] = mapped_column(
        Enum(
            DeliveryStatus,
            native_enum=False,
        ),
        default=DeliveryStatus.QUEUED,
        nullable=False,
    )

    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )


# ==========================================================================
# Smart-home devices
# ==========================================================================

class SmartDevice(Base):
    __tablename__ = "smart_devices"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )

    property_id: Mapped[str] = mapped_column(
        ForeignKey(
            "properties.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    unit_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey(
            "units.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    registered_by_id: Mapped[str] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )

    device_type: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
    )

    provider: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    external_device_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    status: Mapped[DeviceStatus] = mapped_column(
        Enum(
            DeviceStatus,
            native_enum=False,
        ),
        default=DeviceStatus.PENDING,
        nullable=False,
    )

    last_seen_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )


class DeviceAction(Base):
    __tablename__ = "device_actions"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )

    device_id: Mapped[str] = mapped_column(
        ForeignKey(
            "smart_devices.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    requested_by_id: Mapped[str] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    action_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    action_parameters: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    confirmed_by_user: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    succeeded: Mapped[Optional[bool]] = mapped_column(
        Boolean,
        nullable=True,
    )

    result_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )


# ==========================================================================
# Privacy, consent and audit records
# ==========================================================================

class ConsentRecord(Base):
    __tablename__ = "consent_records"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )

    user_id: Mapped[str] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    consent_type: Mapped[ConsentType] = mapped_column(
        Enum(
            ConsentType,
            native_enum=False,
        ),
        nullable=False,
    )

    granted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
    )

    policy_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    ip_hash: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    withdrawn_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )

    user_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    action: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        index=True,
    )

    resource_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    resource_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    result: Mapped[str] = mapped_column(
        String(50),
        default="success",
        nullable=False,
    )

    details: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    ip_hash: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

# ============================================================
# Rental applications
# ============================================================


class RentalApplication(Base):
    """
    A prospective tenant's application for an available rental unit.

    Sensitive application information must only be accessible to the
    applicant, the property's authorized landlord or manager, and an
    administrator with a legitimate business purpose.
    """

    __tablename__ = "rental_applications"

    id = Column(
        String(36),
        primary_key=True,
        default=generate_uuid,
        index=True,
    )

    property_id = Column(
        String(36),
        ForeignKey(
            "properties.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    unit_id = Column(
        String(36),
        ForeignKey(
            "units.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    applicant_user_id = Column(
        String(36),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    # Applicant identity
    first_name = Column(
        String(100),
        nullable=False,
    )

    last_name = Column(
        String(100),
        nullable=False,
    )

    email = Column(
        String(254),
        nullable=False,
        index=True,
    )

    phone = Column(
        String(30),
        nullable=False,
    )

    # Current address
    current_address = Column(
        String(250),
        nullable=False,
    )

    current_city = Column(
        String(120),
        nullable=False,
    )

    postal_code = Column(
        String(20),
        nullable=False,
    )

    # Household
    adult_occupants = Column(
        Integer,
        nullable=False,
        default=1,
    )

    child_occupants = Column(
        Integer,
        nullable=False,
        default=0,
    )

    desired_move_in_date = Column(
        Date,
        nullable=False,
        index=True,
    )

    lease_duration_months = Column(
        Integer,
        nullable=True,
    )

    has_pets = Column(
        Boolean,
        nullable=False,
        default=False,
    )

    pet_details = Column(
        Text,
        nullable=True,
    )

    # Employment and income
    employment_status = Column(
        String(50),
        nullable=False,
    )

    employer_name = Column(
        String(150),
        nullable=True,
    )

    monthly_income = Column(
        Numeric(
            precision=12,
            scale=2,
        ),
        nullable=False,
    )

    employment_length = Column(
        String(100),
        nullable=True,
    )

    message = Column(
        Text,
        nullable=True,
    )

    # Workflow:
    # submitted, under_review, additional_information_required,
    # approved, rejected, withdrawn, archived
    status = Column(
        String(50),
        nullable=False,
        default="submitted",
        index=True,
    )

    landlord_notes = Column(
        Text,
        nullable=True,
    )

    reviewed_by_user_id = Column(
        String(36),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    reviewed_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    rejection_reason = Column(
        Text,
        nullable=True,
    )

    # Consent evidence
    information_confirmed = Column(
        Boolean,
        nullable=False,
        default=False,
    )

    privacy_consent = Column(
        Boolean,
        nullable=False,
        default=False,
    )

    landlord_contact_consent = Column(
        Boolean,
        nullable=False,
        default=False,
    )

    ai_assistance_consent = Column(
        Boolean,
        nullable=False,
        default=False,
    )

    submitted_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships do not use back_populates, so you do not have
    # to modify your existing Property, Unit or User classes yet.
    property = relationship(
        "Property",
        foreign_keys=[property_id],
        lazy="joined",
    )

    unit = relationship(
        "Unit",
        foreign_keys=[unit_id],
        lazy="joined",
    )

    applicant = relationship(
        "User",
        foreign_keys=[applicant_user_id],
        lazy="joined",
    )

    reviewed_by = relationship(
        "User",
        foreign_keys=[reviewed_by_user_id],
        lazy="joined",
    )

    __table_args__ = (
        Index(
            "ix_rental_applications_property_status",
            "property_id",
            "status",
        ),
        Index(
            "ix_rental_applications_unit_status",
            "unit_id",
            "status",
        ),
        Index(
            "ix_rental_applications_applicant_created",
            "applicant_user_id",
            "created_at",
        ),
    )

    @builtins.property
    def applicant_full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @builtins.property
    def is_open(self) -> bool:
        return self.status in {
            "submitted",
            "under_review",
            "additional_information_required",
        }

    def __repr__(self) -> str:
        return (
            f"<RentalApplication("
            f"id={self.id}, "
            f"property_id={self.property_id}, "
            f"unit_id={self.unit_id}, "
            f"status={self.status!r}"
            f")>"
        )


# ============================================================
# Viewing appointments
# ============================================================


class ViewingAppointment(Base):
    """
    A request to view an available property unit.

    The preferred appointment is stored in UTC. The timezone_name
    field preserves the timezone used when the request was submitted.
    """

    __tablename__ = "viewing_appointments"

    id = Column(
        String(36),
        primary_key=True,
        default=generate_uuid,
        index=True,
    )

    property_id = Column(
        String(36),
        ForeignKey(
            "properties.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    unit_id = Column(
        String(36),
        ForeignKey(
            "units.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    requester_user_id = Column(
        String(36),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    # Visitor contact information
    first_name = Column(
        String(100),
        nullable=False,
    )

    last_name = Column(
        String(100),
        nullable=False,
    )

    email = Column(
        String(254),
        nullable=False,
        index=True,
    )

    phone = Column(
        String(30),
        nullable=False,
    )

    preferred_language = Column(
        String(20),
        nullable=False,
        default="en",
    )

    # Appointment times are stored in UTC.
    preferred_datetime = Column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    alternative_datetime = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    timezone_name = Column(
        String(100),
        nullable=False,
        default="UTC",
    )

    # in_person, video_call, recorded_tour
    viewing_type = Column(
        String(50),
        nullable=False,
        default="in_person",
    )

    needs_accommodation = Column(
        Boolean,
        nullable=False,
        default=False,
    )

    accommodation_details = Column(
        Text,
        nullable=True,
    )

    message = Column(
        Text,
        nullable=True,
    )

    # Reminder choices
    reminder_email = Column(
        Boolean,
        nullable=False,
        default=True,
    )

    reminder_sms = Column(
        Boolean,
        nullable=False,
        default=False,
    )

    reminder_whatsapp = Column(
        Boolean,
        nullable=False,
        default=False,
    )

    reminder_phone = Column(
        Boolean,
        nullable=False,
        default=False,
    )

    reminder_at = Column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    reminder_sent = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )

    reminder_sent_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    reminder_error = Column(
        Text,
        nullable=True,
    )

    # requested, confirmed, declined, cancelled,
    # completed, no_show
    status = Column(
        String(50),
        nullable=False,
        default="requested",
        index=True,
    )

    confirmation_message = Column(
        Text,
        nullable=True,
    )

    meeting_url = Column(
        String(500),
        nullable=True,
    )

    confirmed_by_user_id = Column(
        String(36),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    confirmed_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    cancelled_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    cancellation_reason = Column(
        Text,
        nullable=True,
    )

    # Consent evidence
    contact_consent = Column(
        Boolean,
        nullable=False,
        default=False,
    )

    reminder_consent = Column(
        Boolean,
        nullable=False,
        default=False,
    )

    privacy_consent = Column(
        Boolean,
        nullable=False,
        default=False,
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    property = relationship(
        "Property",
        foreign_keys=[property_id],
        lazy="joined",
    )

    unit = relationship(
        "Unit",
        foreign_keys=[unit_id],
        lazy="joined",
    )

    requester = relationship(
        "User",
        foreign_keys=[requester_user_id],
        lazy="joined",
    )

    confirmed_by = relationship(
        "User",
        foreign_keys=[confirmed_by_user_id],
        lazy="joined",
    )

    __table_args__ = (
        Index(
            "ix_viewing_appointments_property_datetime",
            "property_id",
            "preferred_datetime",
        ),
        Index(
            "ix_viewing_appointments_unit_datetime",
            "unit_id",
            "preferred_datetime",
        ),
        Index(
            "ix_viewing_appointments_reminder_queue",
            "reminder_sent",
            "reminder_at",
            "status",
        ),
        Index(
            "ix_viewing_appointments_requester_created",
            "requester_user_id",
            "created_at",
        ),
    )

    @builtins.property
    def requester_full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @builtins.property
    def reminder_requested(self) -> bool:
        return any(
            (
                self.reminder_email,
                self.reminder_sms,
                self.reminder_whatsapp,
                self.reminder_phone,
            )
        )

    @builtins.property
    def is_upcoming(self) -> bool:
        if self.status not in {"requested", "confirmed"}:
            return False

        appointment_time = self.preferred_datetime

        if appointment_time is None:
            return False

        if appointment_time.tzinfo is None:
            appointment_time = appointment_time.replace(
                tzinfo=timezone.utc
            )

        return appointment_time > datetime.now(timezone.utc)

    def __repr__(self) -> str:
        return (
            f"<ViewingAppointment("
            f"id={self.id}, "
            f"property_id={self.property_id}, "
            f"unit_id={self.unit_id}, "
            f"status={self.status!r}, "
            f"preferred_datetime={self.preferred_datetime!r}"
            f")>"
        )
