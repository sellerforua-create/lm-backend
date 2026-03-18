from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ProductVariant(Base):
    __tablename__ = "product_variants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    offer_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)

    size: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    color: Mapped[str | None] = mapped_column(String, index=True, nullable=True)

    price: Mapped[float] = mapped_column(Float)
    old_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    supplier_price: Mapped[float | None] = mapped_column(Float, nullable=True)

    available: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    product = relationship("Product", back_populates="variants")
