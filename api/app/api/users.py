from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import Session

from app.db import run_transaction
from app.models import User
from app.schemas import UserOut, UserPatch
from app.users import CurrentUser

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me")
def read_me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@router.patch("/me")
def update_me(body: UserPatch, user: CurrentUser) -> UserOut:
    changes = body.model_dump(exclude_unset=True, exclude_none=True)

    def work(session: Session) -> User:
        current = session.get(User, user.id)
        if current is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
        for field, value in changes.items():
            setattr(current, field, value)
        session.flush()
        return current

    return UserOut.model_validate(run_transaction(work))
