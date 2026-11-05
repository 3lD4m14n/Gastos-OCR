import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import run_transaction
from app.models import Category, Expense
from app.schemas import CategoryCreate, CategoryOut, CategoryPatch
from app.text import search_key
from app.users import CurrentUser

router = APIRouter(prefix="/categories", tags=["categories"])

# DSQL admite hasta 3.000 filas por transacción.
MOVE_BATCH_SIZE = 1000
DUPLICATE_NAME = "Ya tenés una categoría con ese nombre"


def _owned(session: Session, user_id: str, category_id: uuid.UUID) -> Category:
    category = session.scalar(
        select(Category).where(Category.id == category_id, Category.user_id == user_id)
    )
    if category is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Categoría no encontrada")
    return category


@router.get("")
def list_categories(user: CurrentUser) -> list[CategoryOut]:
    rows = run_transaction(
        lambda session: session.scalars(select(Category).where(Category.user_id == user.id)).all()
    )
    # Se ordena acá: la collation C de DSQL dejaría "Ñ" y las vocales con acento al final.
    ordered = sorted(rows, key=lambda c: (c.is_fallback, search_key(c.name)))
    return [CategoryOut.model_validate(c) for c in ordered]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_category(body: CategoryCreate, user: CurrentUser) -> CategoryOut:
    def work(session: Session) -> Category:
        category = Category(user_id=user.id, **body.model_dump())
        session.add(category)
        session.flush()
        return category

    try:
        return CategoryOut.model_validate(run_transaction(work))
    except IntegrityError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, DUPLICATE_NAME) from error


@router.patch("/{category_id}")
def update_category(category_id: uuid.UUID, body: CategoryPatch, user: CurrentUser) -> CategoryOut:
    changes = body.model_dump(exclude_unset=True)

    def work(session: Session) -> Category:
        category = _owned(session, user.id, category_id)
        for field, value in changes.items():
            # `icon` se puede quitar; nombre y color siempre deben tener valor.
            if value is not None or field == "icon":
                setattr(category, field, value)
        session.flush()
        return category

    try:
        return CategoryOut.model_validate(run_transaction(work))
    except IntegrityError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, DUPLICATE_NAME) from error


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: uuid.UUID, user: CurrentUser) -> None:
    def prepare(session: Session) -> uuid.UUID:
        category = _owned(session, user.id, category_id)
        if category.is_fallback:
            raise HTTPException(status.HTTP_409_CONFLICT, "La categoría Otros no se puede borrar")
        fallback = session.scalars(
            select(Category.id).where(Category.user_id == user.id, Category.is_fallback)
        ).one()
        return fallback

    fallback_id = run_transaction(prepare)

    def move_batch(session: Session) -> int:
        ids = session.scalars(
            select(Expense.id)
            .where(Expense.user_id == user.id, Expense.category_id == category_id)
            .limit(MOVE_BATCH_SIZE)
        ).all()
        if ids:
            session.execute(
                update(Expense).where(Expense.id.in_(ids)).values(category_id=fallback_id)
            )
        return len(ids)

    # Si se corta a mitad, los gastos ya movidos quedan bien y borrar de nuevo termina el trabajo.
    while run_transaction(move_batch) == MOVE_BATCH_SIZE:
        pass

    def remove(session: Session) -> None:
        session.delete(_owned(session, user.id, category_id))

    try:
        run_transaction(remove)
    except IntegrityError as error:
        # Entró un gasto nuevo en esta categoría mientras se borraba.
        raise HTTPException(
            status.HTTP_409_CONFLICT, "La categoría cambió mientras se borraba; probá de nuevo"
        ) from error
