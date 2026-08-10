"""Category and subcategory management.

Deleting a category (or subcategory) never deletes transactions — it only
nullifies the FK on affected rows. See CLAUDE.md "Deleting a category":
`user_categorized` is cleared so the row stays reachable by the rule engine,
except on subcategory deletion, where it's cleared only if the transaction's
`category_id` is also NULL (the parent category is unaffected and still
applies).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from database import get_db
from models import Category, CategoryRule, Subcategory, Transaction
from schemas import Category as CategorySchema
from schemas import CategoryCreate, CategoryUpdate, CategoryWithCount
from schemas import Subcategory as SubcategorySchema
from schemas import SubcategoryCreate

router = APIRouter(prefix="/api/v1", tags=["categories"])


@router.get("/categories", response_model=list[CategoryWithCount])
def list_categories(db: Session = Depends(get_db)) -> list[CategoryWithCount]:
    counts = dict(
        db.execute(
            select(Transaction.category_id, func.count())
            .where(Transaction.category_id.is_not(None))
            .group_by(Transaction.category_id)
        ).all()
    )
    categories = db.scalars(
        select(Category).options(selectinload(Category.subcategories)).order_by(Category.name.asc())
    ).all()
    return [
        CategoryWithCount(
            id=category.id,
            name=category.name,
            color=category.color,
            subcategories=category.subcategories,
            transaction_count=counts.get(category.id, 0),
        )
        for category in categories
    ]


@router.post("/categories", response_model=CategorySchema, status_code=201)
def create_category(data: CategoryCreate, db: Session = Depends(get_db)) -> Category:
    category = Category(name=data.name, color=data.color)
    db.add(category)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Category '{data.name}' already exists") from exc
    db.refresh(category)
    return category


@router.patch("/categories/{category_id}", response_model=CategorySchema)
def update_category(
    category_id: int, data: CategoryUpdate, db: Session = Depends(get_db)
) -> Category:
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")

    fields = data.model_fields_set
    if "name" in fields:
        category.name = data.name
    if "color" in fields:
        category.color = data.color

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Category '{data.name}' already exists") from exc
    db.refresh(category)
    return category


@router.delete("/categories/{category_id}", status_code=204)
def delete_category(category_id: int, db: Session = Depends(get_db)) -> None:
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")

    db.execute(
        update(Transaction)
        .where(Transaction.category_id == category_id)
        .values(category_id=None, subcategory_id=None, user_categorized=False)
    )
    # category_rules.category_id is NOT NULL, so a rule can't be left pointing
    # at a deleted category the way a transaction's FK is nulled out above —
    # it has to go with it.
    db.execute(delete(CategoryRule).where(CategoryRule.category_id == category_id))
    db.delete(category)  # cascades subcategories via the ORM relationship
    db.commit()


@router.post(
    "/categories/{category_id}/subcategories", response_model=SubcategorySchema, status_code=201
)
def create_subcategory(
    category_id: int, data: SubcategoryCreate, db: Session = Depends(get_db)
) -> Subcategory:
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")

    subcategory = Subcategory(category_id=category_id, name=data.name)
    db.add(subcategory)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Subcategory '{data.name}' already exists in this category",
        ) from exc
    db.refresh(subcategory)
    return subcategory


@router.delete("/subcategories/{subcategory_id}", status_code=204)
def delete_subcategory(subcategory_id: int, db: Session = Depends(get_db)) -> None:
    subcategory = db.get(Subcategory, subcategory_id)
    if subcategory is None:
        raise HTTPException(status_code=404, detail="Subcategory not found")

    affected_ids = list(
        db.scalars(select(Transaction.id).where(Transaction.subcategory_id == subcategory_id))
    )
    if affected_ids:
        db.execute(
            update(Transaction)
            .where(Transaction.id.in_(affected_ids))
            .values(subcategory_id=None)
        )
        db.execute(
            update(Transaction)
            .where(Transaction.id.in_(affected_ids), Transaction.category_id.is_(None))
            .values(user_categorized=False)
        )

    db.delete(subcategory)
    db.commit()
