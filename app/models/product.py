from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.core.database import Base


JSONBCompat = JSON().with_variant(JSONB, "postgresql")


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    external_id: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    group_id: Mapped[str] = mapped_column(String, unique=True, index=True)

    name: Mapped[str] = mapped_column(String, index=True)
    name_ua: Mapped[str | None] = mapped_column(String, nullable=True)
    slug: Mapped[str | None] = mapped_column(String, unique=True, index=True, nullable=True)

    description: Mapped[str | None] = mapped_column(String, nullable=True)
    description_ua: Mapped[str | None] = mapped_column(String, nullable=True)
    url: Mapped[str | None] = mapped_column(String, nullable=True)

    price: Mapped[float] = mapped_column(Float, default=0.0)
    old_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    supplier_price: Mapped[float | None] = mapped_column(Float, nullable=True)

    min_price: Mapped[float | None] = mapped_column(Float, index=True, nullable=True)
    max_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    min_old_price: Mapped[float | None] = mapped_column(Float, nullable=True)

    currency: Mapped[str] = mapped_column(String, default="UAH")

    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True, index=True)
    category_name: Mapped[str | None] = mapped_column(String, index=True, nullable=True)

    vendor: Mapped[str | None] = mapped_column(String, nullable=True)
    vendor_code: Mapped[str | None] = mapped_column(String, nullable=True)

    image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    images: Mapped[list | None] = mapped_column(JSONBCompat, nullable=True)
    params: Mapped[dict | None] = mapped_column(JSONBCompat, nullable=True)

    gender: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    season: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    material: Mapped[str | None] = mapped_column(String, nullable=True)
    composition: Mapped[str | None] = mapped_column(String, nullable=True)
    style: Mapped[str | None] = mapped_column(String, nullable=True)
    color_group: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    country: Mapped[str | None] = mapped_column(String, nullable=True)

    available: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    xml_feed_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    variants = relationship("ProductVariant", back_populates="product", cascade="all, delete-orphan", lazy="selectin")
    category = relationship("Category", back_populates="products", lazy="joined")
