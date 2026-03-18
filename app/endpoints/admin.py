from fastapi import APIRouter
from sqlalchemy import text
from app.core.database import engine
import httpx
import xml.etree.ElementTree as ET
import os

router = APIRouter()

PRICE_MARKUP = float(os.getenv("PRICE_MARKUP", "20")) / 100
FEED_URL = "https://api.dropshipping.ua/api/feeds/3411.xml"


@router.post("/import")
async def trigger_import():
    """Download XML feed and insert all products into DB."""

    # 1. Fetch XML
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.get(FEED_URL)

    root = ET.fromstring(resp.text)
    shop = root.find("shop")
    if shop is None:
        return {"error": "no <shop> element in XML"}

    # 2. Build category ID → name mapping
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

    # 3. Drop and recreate table
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS products CASCADE"))
        await conn.execute(text("""
            CREATE TABLE products (
                id SERIAL PRIMARY KEY,
                external_id VARCHAR(255),
                name TEXT NOT NULL,
                description TEXT,
                price FLOAT NOT NULL,
                old_price FLOAT,
                supplier_price FLOAT,
                currency VARCHAR(10) DEFAULT 'UAH',
                category_id INTEGER,
                category_name VARCHAR(255),
                vendor VARCHAR(255),
                vendor_code VARCHAR(255),
                image_url TEXT,
                images JSONB,
                available BOOLEAN DEFAULT true,
                xml_feed_id INTEGER,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """))

    # 4. Insert products with real category names
    inserted = 0
    async with engine.begin() as conn:
        for offer in offers:
            ext_id = offer.get("id", "")
            name_el = offer.find("name")
            price_el = offer.find("price")
            if name_el is None or price_el is None:
                continue
            name = name_el.text or ""
            try:
                supplier_price = float(price_el.text or 0)
            except (ValueError, TypeError):
                continue
            price = round(supplier_price * (1 + PRICE_MARKUP), 2)

            desc = ""
            d = offer.find("description")
            if d is not None and d.text:
                desc = d.text

            # Map category ID to human-readable name
            cat_id_str = ""
            cat_name = ""
            c = offer.find("categoryId")
            if c is not None and c.text:
                cat_id_str = c.text
                cat_name = cat_map.get(cat_id_str, cat_id_str)

            vendor = ""
            v = offer.find("vendor")
            if v is not None and v.text:
                vendor = v.text

            vendor_code = ""
            vc = offer.find("vendorCode")
            if vc is not None and vc.text:
                vendor_code = vc.text

            image_url = ""
            p = offer.find("picture")
            if p is not None and p.text:
                image_url = p.text

            avail = offer.get("available", "true") == "true"

            cat_id_int = int(cat_id_str) if cat_id_str.isdigit() else None

            await conn.execute(text(
                "INSERT INTO products "
                "(external_id, name, description, price, supplier_price, "
                "category_id, category_name, vendor, vendor_code, image_url, "
                "available, xml_feed_id, currency) "
                "VALUES (:eid, :name, :desc, :price, :sp, :cid, :cname, "
                ":ven, :vc, :img, :avail, 3411, 'UAH')"
            ), {
                "eid": ext_id, "name": name, "desc": desc,
                "price": price, "sp": supplier_price,
                "cid": cat_id_int, "cname": cat_name,
                "ven": vendor, "vc": vendor_code,
                "img": image_url, "avail": avail,
            })
            inserted += 1

    return {"imported": inserted, "categories": len(cat_map)}


@router.get("/stats")
async def stats():
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT COUNT(*) FROM products"))
        count = result.scalar()
    return {"products": count}
