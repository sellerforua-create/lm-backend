from fastapi import APIRouter, Depends, HTTPException, Query
import json

from sqlalchemy import func, or_, select, text, cast, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.product import Product
from app.models.product_variant import ProductVariant

router = APIRouter()


def _parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _serialize_variant(variant: ProductVariant) -> dict:
    return {
        "id": variant.id,
        "offer_id": variant.offer_id,
        "size": variant.size,
        "color": variant.color,
        "price": variant.price,
        "old_price": variant.old_price,
        "supplier_price": variant.supplier_price,
        "available": variant.available,
        "quantity": variant.quantity,
    }


def _serialize_product(product: Product) -> dict:
    return {
        "id": product.id,
        "external_id": product.external_id,
        "group_id": product.group_id,
        "name": product.name,
        "name_ua": product.name_ua,
        "slug": product.slug,
        "description": product.description,
        "description_ua": product.description_ua,
        "url": product.url,
        "price": product.price,
        "old_price": product.old_price,
        "supplier_price": product.supplier_price,
        "min_price": product.min_price,
        "max_price": product.max_price,
        "min_old_price": product.min_old_price,
        "currency": product.currency,
        "category_id": product.category_id,
        "category_name": product.category_name,
        "vendor": product.vendor,
        "vendor_code": product.vendor_code,
        "image_url": product.image_url,
        "images": product.images,
        "params": product.params,
        "gender": product.gender,
        "season": product.season,
        "material": product.material,
        "composition": product.composition,
        "style": product.style,
        "color_group": product.color_group,
        "country": product.country,
        "available": product.available,
        "variants": [_serialize_variant(v) for v in product.variants],
    }


@router.get("/")
async def get_products(
    db: AsyncSession = Depends(get_db),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=24, ge=1, le=100),
    category_id: int | None = None,
    gender: str | None = None,
    size: str | None = None,
    color: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    season: str | None = None,
    search: str | None = None,
    viscosity: str | None = None,
    sort: str = "new",
):
    query = select(Product).options(selectinload(Product.variants)).where(Product.available.is_(True))

    if category_id is not None:
        query = query.where(Product.category_id == category_id)

    if gender:
        query = query.where(Product.gender.ilike(f"%{gender}%"))

    if season:
        query = query.where(Product.season.ilike(f"%{season}%"))

    if search:
        query = query.where(
            or_(
                Product.name.ilike(f"%{search}%"),
                Product.description.ilike(f"%{search}%"),
                Product.vendor_code.ilike(f"%{search}%"),
                Product.category_name.ilike(f"%{search}%"),
            )
        )

    if viscosity:
        query = query.where(cast(Product.params, String).ilike(f"%{viscosity}%"))

    if min_price is not None:
        query = query.where(Product.min_price >= min_price)

    if max_price is not None:
        query = query.where(Product.min_price <= max_price)

    sizes = _parse_csv(size)
    colors = _parse_csv(color)
    if sizes or colors:
        query = query.join(ProductVariant, ProductVariant.product_id == Product.id)
        query = query.where(ProductVariant.available.is_(True))
        if sizes:
            query = query.where(ProductVariant.size.in_(sizes))
        if colors:
            query = query.where(ProductVariant.color.in_(colors))
        query = query.distinct()

    if sort == "price_asc":
        query = query.order_by(Product.min_price.asc().nullslast(), Product.id.desc())
    elif sort == "price_desc":
        query = query.order_by(Product.min_price.desc().nullslast(), Product.id.desc())
    elif sort == "popular":
        query = query.order_by(Product.updated_at.desc(), Product.id.desc())
    else:  # new
        query = query.order_by(Product.created_at.desc(), Product.id.desc())

    total_stmt = select(func.count()).select_from(query.order_by(None).subquery())
    total = (await db.execute(total_stmt)).scalar_one()

    result = await db.execute(query.offset((page - 1) * limit).limit(limit))
    products = result.scalars().all()

    return {
        "items": [_serialize_product(product) for product in products],
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit if total else 0,
    }


@router.get("/categories/list")
async def get_categories(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Product.category_id, Product.category_name, func.count(Product.id))
        .where(Product.available.is_(True))
        .group_by(Product.category_id, Product.category_name)
        .order_by(func.count(Product.id).desc())
    )
    return [
        {"id": row[0], "name": row[1], "count": row[2]}
        for row in result.all()
        if row[1]
    ]


@router.get("/viscosities")
async def get_viscosities(db: AsyncSession = Depends(get_db)):
    """Return list of available viscosities from products."""
    result = await db.execute(
        text("SELECT DISTINCT params FROM products WHERE params IS NOT NULL")
    )
    rows = result.fetchall()

    viscosities = set()
    for row in rows:
        try:
            raw = row[0]
            p = json.loads(raw) if isinstance(raw, str) else raw
            if isinstance(p, dict):
                value = p.get("Вязкость масла") or p.get("Вязкость")
                if value:
                    viscosities.add(str(value))
        except Exception:
            pass

    return sorted(viscosities)


@router.get("/{product_id}/variants")
async def get_product_variants(product_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ProductVariant)
        .where(ProductVariant.product_id == product_id)
        .order_by(ProductVariant.available.desc(), ProductVariant.size.asc().nullslast())
    )
    variants = result.scalars().all()
    return [_serialize_variant(v) for v in variants]


@router.get("/{product_id}")
async def get_product(product_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Product)
        .options(selectinload(Product.variants))
        .where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return _serialize_product(product)
