from fastapi import APIRouter
from sqlalchemy import text, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import engine, Base
from app.models.product import Product
from app.models.category import Category
import httpx
import xml.etree.ElementTree as ET
import os
import re

router = APIRouter()

PRICE_MARKUP = float(os.getenv("PRICE_MARKUP", "0")) / 100
FEED_URL = "https://api.dropshipping.ua/api/feeds/3411.xml"


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")[:200]


@router.post("/import")
async def trigger_import():
    """Download XML feed and insert all products into DB using ORM."""

    # 1. Fetch XML
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.get(FEED_URL)

    root = ET.fromstring(resp.text)
    shop = root.find("shop")
    if shop is None:
        return {"error": "no <shop> element in XML"}

    # 2. Build category map
    cat_map = {}
    cats_el = shop.find("categories")
    if cats_el is not None:
        for cat in cats_el.findall("category"):
            cat_id = cat.get("id", "")
            cat_name = cat.text or cat_id
            cat_map[cat_id] = cat_name

    offers_el = shop.find("offers")
    if offers_el is None:
        return {"error": "no <offers> element in XML"}

    offers = offers_el.findall("offer")
    if not offers:
        return {"error": "0 offers found"}

    # 3. Ensure tables exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 4. Build category id → DB id mapping
    async with AsyncSession(engine) as session:
        # Clear existing products
        await session.execute(text("DELETE FROM products"))
        await session.execute(text("DELETE FROM categories"))
        await session.commit()

        # Insert categories
        cat_db_ids = {}
        for cat_id_str, cat_name in cat_map.items():
            if not cat_id_str.isdigit():
                continue
            cat = Category(
                id=int(cat_id_str),
                name=cat_name,
                slug=slugify(cat_name) + f"-{cat_id_str}",
                product_count=0,
            )
            session.add(cat)
        await session.commit()

        for cat_id_str in cat_map:
            if cat_id_str.isdigit():
                cat_db_ids[cat_id_str] = int(cat_id_str)

    # 5. Insert products
    inserted = 0
    used_group_ids = set()
    used_slugs = set()

    async with AsyncSession(engine) as session:
        for offer in offers:
            ext_id = offer.get("id", "")
            name_el = offer.find("name")
            price_el = offer.find("price")
            if name_el is None or price_el is None:
                continue
            name = (name_el.text or "").strip()
            if not name:
                continue
            try:
                supplier_price = float(price_el.text or 0)
            except (ValueError, TypeError):
                continue
            price = round(supplier_price * (1 + PRICE_MARKUP), 2)

            desc = ""
            d = offer.find("description")
            if d is not None and d.text:
                # Strip HTML tags
                desc = re.sub(r"<[^>]+>", "", d.text).strip()

            cat_id_str = ""
            cat_name = ""
            c = offer.find("categoryId")
            if c is not None and c.text:
                cat_id_str = c.text.strip()
                cat_name = cat_map.get(cat_id_str, cat_id_str)

            vendor = "LIQUI MOLY"
            vendor_code = ""
            vc = offer.find("vendorCode")
            if vc is not None and vc.text:
                vendor_code = vc.text.strip()

            # Collect params from XML
            params = {}
            for p_el in offer.findall("param"):
                pname = p_el.get("name", "")
                pval = p_el.text or ""
                if pname and pval:
                    params[pname] = pval

            # All pictures
            pictures = [p.text for p in offer.findall("picture") if p.text]
            image_url = pictures[0] if pictures else ""

            avail = offer.get("available", "true") == "true"
            cat_id_int = int(cat_id_str) if cat_id_str.isdigit() else None

            # Unique group_id and slug
            base_group = f"lm-{ext_id}" if ext_id else f"lm-{inserted}"
            group_id = base_group
            counter = 1
            while group_id in used_group_ids:
                group_id = f"{base_group}-{counter}"
                counter += 1
            used_group_ids.add(group_id)

            base_slug = slugify(name)
            slug = base_slug
            counter = 1
            while slug in used_slugs:
                slug = f"{base_slug}-{counter}"
                counter += 1
            used_slugs.add(slug)

            product = Product(
                external_id=ext_id,
                group_id=group_id,
                name=name,
                slug=slug,
                description=desc,
                price=price,
                supplier_price=supplier_price,
                min_price=price,
                max_price=price,
                currency="UAH",
                category_id=cat_id_int,
                category_name=cat_name,
                vendor=vendor,
                vendor_code=vendor_code,
                image_url=image_url,
                images=pictures if pictures else None,
                params=params if params else None,
                available=avail,
            )
            session.add(product)
            inserted += 1

            if inserted % 100 == 0:
                await session.commit()

        await session.commit()

    # 6. Update category product counts
    async with AsyncSession(engine) as session:
        for cat_id_str in cat_map:
            if cat_id_str.isdigit():
                result = await session.execute(
                    text("SELECT COUNT(*) FROM products WHERE category_id = :cid"),
                    {"cid": int(cat_id_str)}
                )
                count = result.scalar() or 0
                await session.execute(
                    text("UPDATE categories SET product_count = :cnt WHERE id = :cid"),
                    {"cnt": count, "cid": int(cat_id_str)}
                )
        await session.commit()

    return {"imported": inserted, "categories": len(cat_map)}


@router.get("/stats")
async def stats():
    async with AsyncSession(engine) as session:
        result = await session.execute(text("SELECT COUNT(*) FROM products"))
        count = result.scalar()
    return {"products": count}
