import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from app.db import run_transaction
from app.models import Category, Expense
from app.schemas import ExpenseCreate, ExpenseOut, ExpensePage, ExpensePatch
from app.text import search_key
from app.users import CurrentUser

router = APIRouter(prefix="/expenses", tags=["expenses"])


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _require_category(session: Session, user_id: str, category_id: uuid.UUID) -> None:
    owned = session.scalar(
        select(Category.id).where(Category.id == category_id, Category.user_id == user_id)
    )
    if owned is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Categoría no encontrada")


def _owned(session: Session, user_id: str, expense_id: uuid.UUID) -> Expense:
    expense = session.scalar(
        select(Expense).where(Expense.id == expense_id, Expense.user_id == user_id)
    )
    if expense is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Gasto no encontrado")
    return expense


@router.get("")
def list_expenses(
    user: CurrentUser,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    category_id: uuid.UUID | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ExpensePage:
    filters: list[ColumnElement[bool]] = [Expense.user_id == user.id]
    if date_from is not None:
        filters.append(Expense.spent_at >= date_from)
    if date_to is not None:
        filters.append(Expense.spent_at <= date_to)
    if category_id is not None:
        filters.append(Expense.category_id == category_id)
    key = search_key(q) if q else ""
    if key:
        filters.append(Expense.search_key.like(f"%{_escape_like(key)}%", escape="\\"))

    def work(session: Session) -> tuple[list[Expense], int]:
        total = session.scalar(select(func.count()).select_from(Expense).where(*filters)) or 0
        items = session.scalars(
            select(Expense)
            .where(*filters)
            .order_by(Expense.spent_at.desc(), Expense.created_at.desc(), Expense.id)
            .limit(page_size)
            .offset((page - 1) * page_size)
        ).all()
        return list(items), total

    items, total = run_transaction(work)
    return ExpensePage(
        items=[ExpenseOut.model_validate(e) for e in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def create_expense(body: ExpenseCreate, user: CurrentUser) -> ExpenseOut:
    def work(session: Session) -> Expense:
        _require_category(session, user.id, body.category_id)
        expense = Expense(
            user_id=user.id,
            search_key=search_key(body.description),
            quantity=1,
            **body.model_dump(),
        )
        session.add(expense)
        session.flush()
        return expense

    return ExpenseOut.model_validate(run_transaction(work))


@router.patch("/{expense_id}")
def update_expense(expense_id: uuid.UUID, body: ExpensePatch, user: CurrentUser) -> ExpenseOut:
    changes = body.model_dump(exclude_unset=True)

    def work(session: Session) -> Expense:
        expense = _owned(session, user.id, expense_id)
        if changes.get("category_id") is not None:
            _require_category(session, user.id, changes["category_id"])
        for field, value in changes.items():
            # `notes` se puede vaciar; los demás campos siempre deben tener valor.
            if value is not None or field == "notes":
                setattr(expense, field, value)
        if changes.get("description") is not None:
            expense.search_key = search_key(changes["description"])
        session.flush()
        return expense

    return ExpenseOut.model_validate(run_transaction(work))


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(expense_id: uuid.UUID, user: CurrentUser) -> None:
    def work(session: Session) -> None:
        session.delete(_owned(session, user.id, expense_id))

    run_transaction(work)
