import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    # El `sub` de Cognito.
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    # El access token no los trae: la web los muestra desde el ID token.
    email: Mapped[str | None] = mapped_column(Text)
    name: Mapped[str | None] = mapped_column(Text)
    currency: Mapped[str] = mapped_column(Text, server_default="PYG")
    timezone: Mapped[str] = mapped_column(Text, server_default="America/Asuncion")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_categories_user_name"),
        Index(
            "uq_categories_one_fallback",
            "user_id",
            unique=True,
            postgresql_where=text("is_fallback"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    color: Mapped[str] = mapped_column(Text)
    icon: Mapped[str | None] = mapped_column(Text)
    is_default: Mapped[bool] = mapped_column(server_default=text("false"))
    # "Otros": recibe los gastos de las categorías borradas y no se puede borrar.
    is_fallback: Mapped[bool] = mapped_column(server_default=text("false"))


class Expense(Base):
    __tablename__ = "expenses"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_expenses_amount_positive"),
        Index("ix_expenses_user_spent_at", "user_id", "spent_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    category_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("categories.id"))
    description: Mapped[str] = mapped_column(Text)
    search_key: Mapped[str] = mapped_column(Text)
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3), server_default="1")
    # Montos en guaraníes enteros.
    unit_price: Mapped[int | None] = mapped_column(BigInteger)
    amount: Mapped[int] = mapped_column(BigInteger)
    iva_rate: Mapped[int | None] = mapped_column(SmallInteger)
    spent_at: Mapped[date] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
