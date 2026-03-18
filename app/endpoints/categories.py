from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.category import Category

router = APIRouter()


def _serialize_category(category: Category) -> dict:
    return {
        "id": category.id,
        "name": category.name,
        "slug": category.slug,
        "parent_id": category.parent_id,
        "level": category.level,
        "product_count": category.product_count,
        "sort_order": category.sort_order,
        "image_url": category.image_url,
    }


def _build_tree(categories: list[Category]) -> list[dict]:
    by_id: dict[int, dict] = {}
    roots: list[dict] = []

    for c in categories:
        node = _serialize_category(c)
        node["children"] = []
        by_id[c.id] = node

    for c in categories:
        node = by_id[c.id]
        if c.parent_id and c.parent_id in by_id:
            by_id[c.parent_id]["children"].append(node)
        else:
            roots.append(node)

    return roots


def _build_breadcrumbs(category_id: int, categories_map: dict[int, Category]) -> list[dict]:
    crumbs: list[dict] = []
    current = categories_map.get(category_id)

    while current:
        crumbs.append({"id": current.id, "name": current.name, "slug": current.slug})
        if current.parent_id is None:
            break
        current = categories_map.get(current.parent_id)

    crumbs.reverse()
    return crumbs


@router.get("/tree")
async def get_categories_tree(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Category).order_by(Category.level, Category.sort_order, Category.name))
    categories = result.scalars().all()
    return _build_tree(categories)


@router.get("/{id_or_slug}/breadcrumbs")
async def get_category_breadcrumbs(id_or_slug: str, db: AsyncSession = Depends(get_db)):
    all_result = await db.execute(select(Category))
    categories = all_result.scalars().all()
    categories_map = {c.id: c for c in categories}

    category: Category | None = None
    if id_or_slug.isdigit():
        category = categories_map.get(int(id_or_slug))
    if category is None:
        category = next((c for c in categories if c.slug == id_or_slug), None)

    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")

    return _build_breadcrumbs(category.id, categories_map)


@router.get("/{id_or_slug}")
async def get_category(id_or_slug: str, db: AsyncSession = Depends(get_db)):
    all_result = await db.execute(select(Category))
    categories = all_result.scalars().all()
    categories_map = {c.id: c for c in categories}

    category: Category | None = None
    if id_or_slug.isdigit():
        category = categories_map.get(int(id_or_slug))
    if category is None:
        category = next((c for c in categories if c.slug == id_or_slug), None)

    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")

    return {
        **_serialize_category(category),
        "breadcrumbs": _build_breadcrumbs(category.id, categories_map),
    }
