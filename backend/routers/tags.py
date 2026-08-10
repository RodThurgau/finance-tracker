"""Tag CRUD and transaction-tag linking.

Tag deletion cascades into `transaction_tags` explicitly: SQLite foreign keys
are not enforced by this app's engine (no `PRAGMA foreign_keys`), and the
`transaction_tags` FKs carry no `ON DELETE CASCADE`, so an orphaned link row
would otherwise survive the tag it points to.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from models import Tag, Transaction, TransactionTag
from schemas import Tag as TagSchema
from schemas import TagCreate, TagLink, TagWithCount
from schemas import Transaction as TransactionSchema

router = APIRouter(prefix="/api/v1", tags=["tags"])


@router.get("/tags", response_model=list[TagWithCount])
def list_tags(db: Session = Depends(get_db)) -> list[TagWithCount]:
    counts = dict(
        db.execute(
            select(TransactionTag.tag_id, func.count()).group_by(TransactionTag.tag_id)
        ).all()
    )
    tags = db.scalars(select(Tag).order_by(Tag.name.asc())).all()
    return [
        TagWithCount(id=tag.id, name=tag.name, color=tag.color, usage_count=counts.get(tag.id, 0))
        for tag in tags
    ]


@router.post("/tags", response_model=TagSchema, status_code=201)
def create_tag(data: TagCreate, db: Session = Depends(get_db)) -> Tag:
    tag = Tag(name=data.name, color=data.color)
    db.add(tag)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Tag '{data.name}' already exists") from exc
    db.refresh(tag)
    return tag


@router.delete("/tags/{tag_id}", status_code=204)
def delete_tag(tag_id: int, db: Session = Depends(get_db)) -> None:
    tag = db.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(status_code=404, detail="Tag not found")

    db.execute(delete(TransactionTag).where(TransactionTag.tag_id == tag_id))
    db.delete(tag)
    db.commit()


@router.post("/transactions/{transaction_id}/tags", response_model=TransactionSchema)
def add_tag_to_transaction(
    transaction_id: int, link: TagLink, db: Session = Depends(get_db)
) -> Transaction:
    transaction = db.get(Transaction, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    tag = db.get(Tag, link.tag_id)
    if tag is None:
        raise HTTPException(status_code=404, detail="Tag not found")

    if tag not in transaction.tags:
        transaction.tags.append(tag)
        db.commit()
        db.refresh(transaction)
    return transaction


@router.delete("/transactions/{transaction_id}/tags/{tag_id}", response_model=TransactionSchema)
def remove_tag_from_transaction(
    transaction_id: int, tag_id: int, db: Session = Depends(get_db)
) -> Transaction:
    transaction = db.get(Transaction, transaction_id)
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    tag = db.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(status_code=404, detail="Tag not found")

    if tag in transaction.tags:
        transaction.tags.remove(tag)
        db.commit()
        db.refresh(transaction)
    return transaction
