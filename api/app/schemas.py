import uuid
from datetime import date
from typing import Annotated, Literal
from zoneinfo import available_timezones

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StrictInt, StringConstraints

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Notes = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]
Color = Annotated[str, StringConstraints(pattern=r"^#[0-9a-fA-F]{6}$")]
Icon = Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)]
# Guaraníes enteros: StrictInt rechaza decimales y textos. El tope entra holgado en BIGINT.
Amount = Annotated[StrictInt, Field(gt=0, le=1_000_000_000_000_000)]


def _known_timezone(value: str) -> str:
    if value not in available_timezones():
        raise ValueError("Zona horaria desconocida")
    return value


Timezone = Annotated[str, AfterValidator(_known_timezone)]


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    currency: str
    timezone: str


class UserPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Multi-moneda queda fuera del MVP.
    currency: Literal["PYG"] | None = None
    timezone: Timezone | None = None


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    color: str
    icon: str | None
    is_default: bool
    is_fallback: bool


class CategoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    color: Color = "#64748b"
    icon: Icon | None = None


class CategoryPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name | None = None
    color: Color | None = None
    icon: Icon | None = None


class ExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category_id: uuid.UUID
    description: str
    amount: int
    spent_at: date
    notes: str | None


class ExpenseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: uuid.UUID
    description: Description
    amount: Amount
    spent_at: date
    notes: Notes | None = None


class ExpensePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category_id: uuid.UUID | None = None
    description: Description | None = None
    amount: Amount | None = None
    spent_at: date | None = None
    notes: Notes | None = None


class ExpensePage(BaseModel):
    items: list[ExpenseOut]
    total: int
    page: int
    page_size: int


class CategoryTotal(BaseModel):
    category_id: uuid.UUID
    name: str
    color: str
    total: int


class MonthTotal(BaseModel):
    # "2026-11"
    month: str
    total: int


class StatsSummary(BaseModel):
    date_from: date
    date_to: date
    total: int
    by_category: list[CategoryTotal]
    by_month: list[MonthTotal]
