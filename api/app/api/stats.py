from datetime import date, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import run_transaction
from app.models import Category, Expense
from app.schemas import CategoryTotal, MonthTotal, StatsSummary
from app.users import CurrentUser

router = APIRouter(prefix="/stats", tags=["stats"])

MONTHS_IN_CHART = 6


def month_start(day: date, months_back: int = 0) -> date:
    index = day.year * 12 + (day.month - 1) - months_back
    return date(index // 12, index % 12 + 1, 1)


def next_month_start(day: date) -> date:
    return month_start(day, months_back=-1)


@router.get("/summary")
def summary(
    user: CurrentUser,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
) -> StatsSummary:
    # Sin rango, el mes en curso según la zona horaria del usuario.
    today = datetime.now(ZoneInfo(user.timezone)).date()
    start = date_from if date_from is not None else month_start(date_to or today)
    end = date_to if date_to is not None else today
    if start > end:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "La fecha inicial es posterior a la final"
        )

    chart_start = month_start(end, months_back=MONTHS_IN_CHART - 1)
    month_label = func.to_char(func.date_trunc("month", Expense.spent_at), "YYYY-MM")

    def work(session: Session) -> tuple[list[tuple[Category, int]], list[tuple[str, int]]]:
        by_category = session.execute(
            select(Category, func.sum(Expense.amount))
            .join(Expense, Expense.category_id == Category.id)
            .where(Expense.user_id == user.id, Expense.spent_at.between(start, end))
            .group_by(Category.id)
            .order_by(func.sum(Expense.amount).desc())
        ).all()
        by_month = session.execute(
            select(month_label, func.sum(Expense.amount))
            .where(
                Expense.user_id == user.id,
                Expense.spent_at >= chart_start,
                Expense.spent_at < next_month_start(end),
            )
            .group_by(month_label)
        ).all()
        return (
            [(category, total) for category, total in by_category],
            [(label, total) for label, total in by_month],
        )

    by_category, by_month = run_transaction(work)
    # SUM de BIGINT llega como Decimal: los montos siempre salen enteros.
    months = {label: int(total) for label, total in by_month}
    labels = [
        month_start(end, months_back=back).strftime("%Y-%m")
        for back in range(MONTHS_IN_CHART - 1, -1, -1)
    ]
    categories = [
        CategoryTotal(category_id=c.id, name=c.name, color=c.color, total=int(total))
        for c, total in by_category
    ]
    return StatsSummary(
        date_from=start,
        date_to=end,
        total=sum(c.total for c in categories),
        by_category=categories,
        by_month=[MonthTotal(month=label, total=months.get(label, 0)) for label in labels],
    )
