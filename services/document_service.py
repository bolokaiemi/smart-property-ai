"""Secure document metadata services. Physical file validation belongs in security/file_validation.py."""
from __future__ import annotations

from typing import Any, Mapping
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from database.models import Document, DocumentType, Property

FIELDS = {
    "property_id", "lease_id", "maintenance_request_id", "document_type",
    "original_filename", "stored_filename", "storage_path", "mime_type",
    "file_size", "checksum", "is_private", "expires_at",
}


def list_landlord_documents(db: Session, landlord_id: str) -> list[Document]:
    owned_properties = select(Property.id).where(Property.owner_id == landlord_id)
    statement = select(Document).where(or_(Document.uploaded_by_id == landlord_id, Document.property_id.in_(owned_properties))).order_by(Document.created_at.desc())
    return list(db.scalars(statement).all())


def get_document(db: Session, document_id: str, landlord_id: str) -> Document | None:
    owned_properties = select(Property.id).where(Property.owner_id == landlord_id)
    return db.scalar(select(Document).where(Document.id == document_id, or_(Document.uploaded_by_id == landlord_id, Document.property_id.in_(owned_properties))))


def create_document_metadata(db: Session, uploaded_by_id: str, data: Mapping[str, Any]) -> Document:
    values = {key: value for key, value in data.items() if key in FIELDS}
    if values.get("document_type") and not isinstance(values["document_type"], DocumentType): values["document_type"] = DocumentType(values["document_type"])
    item = Document(uploaded_by_id=uploaded_by_id, **values)
    try:
        db.add(item); db.commit(); db.refresh(item); return item
    except Exception:
        db.rollback(); raise


def delete_document_metadata(db: Session, document_id: str, landlord_id: str) -> Document | None:
    item = get_document(db, document_id, landlord_id)
    if item is None: return None
    try:
        db.delete(item); db.commit(); return item
    except Exception:
        db.rollback(); raise
