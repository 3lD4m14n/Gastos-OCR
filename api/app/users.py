"""Alta del usuario en su primera petición autenticada."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.auth import Identity, get_identity
from app.db import run_transaction
from app.models import Category, User

FALLBACK_CATEGORY = "Otros"
# Tonos de la paleta categórica validada para daltonismo. Los dos últimos son neutros: esa paleta
# tiene ocho tonos, y "Otros" y "Hogar" no necesitan uno propio para identificarse.
DEFAULT_CATEGORIES: tuple[tuple[str, str], ...] = (
    ("Supermercado", "#2a78d6"),
    ("Limpieza", "#1baf7a"),
    ("Higiene", "#e87ba4"),
    ("Bebidas", "#6250d6"),
    ("Almacén", "#eda100"),
    ("Carnes", "#e34948"),
    ("Verdulería", "#008300"),
    ("Farmacia", "#eb6834"),
    ("Hogar", "#475569"),
    (FALLBACK_CATEGORY, "#94a3b8"),
)


def ensure_user(session: Session, sub: str) -> User:
    """Crea el usuario y sus categorías una sola vez, aunque lleguen pedidos simultáneos."""
    user = session.get(User, sub)
    if user is not None:
        return user

    # Sin `preserve_rowcount`, SQLAlchemy informa -1 en este insert.
    statement = (
        insert(User)
        .values(id=sub)
        .on_conflict_do_nothing()
        .execution_options(preserve_rowcount=True)
    )
    # rowcount 0: otro pedido lo creó primero, y también sus categorías.
    if session.connection().execute(statement).rowcount == 1:
        session.add_all(
            Category(
                user_id=sub,
                name=name,
                color=color,
                is_default=True,
                is_fallback=name == FALLBACK_CATEGORY,
            )
            for name, color in DEFAULT_CATEGORIES
        )
        session.flush()
    created = session.execute(select(User).where(User.id == sub)).scalar_one()
    return created


def get_current_user(identity: Annotated[Identity, Depends(get_identity)]) -> User:
    return run_transaction(lambda session: ensure_user(session, identity.sub))


CurrentUser = Annotated[User, Depends(get_current_user)]
