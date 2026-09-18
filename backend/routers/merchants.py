"""Merchant name mappings: override the display name for a counter_account value.

The raw `counter_account` stays on the transaction row. The mapping is resolved
at query time (a LEFT JOIN + COALESCE in `stats.py`), so adding or changing a
mapping takes effect immediately everywhere that shows merchant names.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from models import MerchantMapping
from schemas import (
    MerchantMapping as MerchantMappingSchema,
    MerchantMappingCreate,
    MerchantMappingUpdate,
)

router = APIRouter(prefix="/api/v1/merchants", tags=["merchants"])


@router.get("", response_model=list[MerchantMappingSchema])
def list_mappings(db: Session = Depends(get_db)) -> list[MerchantMapping]:
    """All merchant name mappings, ordered by display name."""
    return list(db.scalars(select(MerchantMapping).order_by(MerchantMapping.display_name)).all())


@router.post("", response_model=MerchantMappingSchema, status_code=201)
def create_mapping(body: MerchantMappingCreate, db: Session = Depends(get_db)) -> MerchantMapping:
    """Create or update a mapping. If `raw_name` already has a mapping, its
    display_name is updated rather than returning a conflict error — the
    TopMerchants inline rename always sends a POST and should not care whether
    the merchant was mapped before."""
    existing = db.scalar(select(MerchantMapping).where(MerchantMapping.raw_name == body.raw_name))
    if existing:
        existing.display_name = body.display_name
        db.commit()
        db.refresh(existing)
        return existing
    mapping = MerchantMapping(raw_name=body.raw_name, display_name=body.display_name)
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return mapping


@router.patch("/{mapping_id}", response_model=MerchantMappingSchema)
def update_mapping(
    mapping_id: int, body: MerchantMappingUpdate, db: Session = Depends(get_db)
) -> MerchantMapping:
    mapping = db.get(MerchantMapping, mapping_id)
    if not mapping:
        raise HTTPException(status_code=404, detail="Mapping not found")
    mapping.display_name = body.display_name
    db.commit()
    db.refresh(mapping)
    return mapping


@router.delete("/{mapping_id}", status_code=204)
def delete_mapping(mapping_id: int, db: Session = Depends(get_db)) -> None:
    mapping = db.get(MerchantMapping, mapping_id)
    if not mapping:
        raise HTTPException(status_code=404, detail="Mapping not found")
    db.delete(mapping)
    db.commit()
