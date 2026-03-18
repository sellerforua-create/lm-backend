"""Promo code validation endpoint — reads from Telegram bot's promo data."""
import json
import os

from fastapi import APIRouter, Query

router = APIRouter()

# The promo codes are stored by the Telegram bot
PROMO_FILE = os.getenv("PROMO_FILE", "/Users/acab/.openclaw/workspace/shop/telegram-bot/data/promo_codes.json")


def _load_promos() -> dict:
    try:
        with open(PROMO_FILE) as f:
            return json.load(f)
    except Exception:
        return {"codes": {}, "users": {}}


@router.get("/validate")
async def validate_promo(code: str = Query(...)):
    data = _load_promos()
    code = code.upper().strip()
    info = data.get("codes", {}).get(code)

    if not info:
        return {"valid": False, "message": "Промокод не знайдено"}

    if info.get("used"):
        return {"valid": False, "message": "Промокод вже використано"}

    return {
        "valid": True,
        "discount": info.get("discount", 10),
        "message": f"Знижка {info.get('discount', 10)}% застосована!",
    }


@router.post("/use")
async def use_promo(code: str = Query(...)):
    data = _load_promos()
    code = code.upper().strip()
    info = data.get("codes", {}).get(code)

    if not info:
        return {"ok": False, "message": "Промокод не знайдено"}
    if info.get("used"):
        return {"ok": False, "message": "Промокод вже використано"}

    info["used"] = True
    try:
        with open(PROMO_FILE, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

    return {"ok": True, "discount": info.get("discount", 10)}
