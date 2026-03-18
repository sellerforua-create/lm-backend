from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.category import Category
from app.models.product import Product
from app.models.product_variant import ProductVariant

router = APIRouter()


def _collect_descendants(category_id: int, categories: list[tuple[int, int | None]]) -> list[int]:
    by_parent: dict[int | None, list[int]] = {}
    for cid, parent_id in categories:
        by_parent.setdefault(parent_id, []).append(cid)

    result: list[int] = []
    stack = [category_id]

    while stack:
        current = stack.pop()
        result.append(current)
        stack.extend(by_parent.get(current, []))

    return result


@router.get("/")
async def get_available_filters(
    category_id: int | None = None,
    db: AsyncSession = Depends(get_db),
):
    category_ids: list[int] | None = None
    if category_id is not None:
        categories_result = await db.execute(select(Category.id, Category.parent_id))
        categories = [(row[0], row[1]) for row in categories_result.all()]
        category_ids = _collect_descendants(category_id, categories)

    product_conditions = [Product.available.is_(True)]
    if category_ids:
        product_conditions.append(Product.category_id.in_(category_ids))

    variant_query = (
        select(ProductVariant.size, ProductVariant.color)
        .join(Product, ProductVariant.product_id == Product.id)
        .where(ProductVariant.available.is_(True), *product_conditions)
    )
    variants_result = await db.execute(variant_query)
    variant_rows = variants_result.all()

    sizes = sorted({row[0] for row in variant_rows if row[0]})
    colors = sorted({row[1] for row in variant_rows if row[1]})

    price_query = select(func.min(Product.min_price), func.max(Product.max_price)).where(*product_conditions)
    price_result = await db.execute(price_query)
    min_price, max_price = price_result.one()

    genders_result = await db.execute(
        select(Product.gender).where(*product_conditions, Product.gender.is_not(None)).distinct()
    )
    seasons_result = await db.execute(
        select(Product.season).where(*product_conditions, Product.season.is_not(None)).distinct()
    )

    return {
        "sizes": sizes,
        "colors": colors,
        "price_range": [min_price or 0, max_price or 0],
        "genders": sorted([row[0] for row in genders_result.all() if row[0]]),
        "seasons": sorted([row[0] for row in seasons_result.all() if row[0]]),
    }
