from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import Base, engine
from app.endpoints import admin, categories, filters, orders, products, promo
from app.models import category as _category_model  # noqa: F401
from app.models import order as _order_model  # noqa: F401
from app.models import product as _product_model  # noqa: F401
from app.models import product_variant as _product_variant_model  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="Dropshipping Shop API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(products.router, prefix="/api/products", tags=["products"])
app.include_router(categories.router, prefix="/api/categories", tags=["categories"])
app.include_router(filters.router, prefix="/api/filters", tags=["filters"])
app.include_router(orders.router, prefix="/api/orders", tags=["orders"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(promo.router, prefix="/api/promo", tags=["promo"])


@app.get("/health")
async def health():
    return {"status": "ok"}
