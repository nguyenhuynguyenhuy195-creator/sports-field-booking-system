from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import User, UserRole, UserStatus


class DuplicateEmailError(ValueError):
    """Raised when a normalized email already belongs to another account."""


def normalize_email(email: str) -> str:
    return email.strip().lower()


def normalize_full_name(full_name: str) -> str:
    return " ".join(full_name.split())


def normalize_phone(phone: str | None) -> str | None:
    normalized = phone.strip() if phone else ""
    return normalized or None


def find_user_by_email(email: str) -> User | None:
    return db.session.scalar(
        db.select(User).where(User.email == normalize_email(email))
    )


def register_user(
    *,
    full_name: str,
    email: str,
    phone: str | None,
    password: str,
) -> User:
    normalized_email = normalize_email(email)
    if find_user_by_email(normalized_email) is not None:
        raise DuplicateEmailError("Email đã được sử dụng.")

    user = User(
        full_name=normalize_full_name(full_name),
        email=normalized_email,
        phone=normalize_phone(phone),
        role=UserRole.USER.value,
        status=UserStatus.ACTIVE.value,
    )
    user.set_password(password)
    db.session.add(user)

    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise DuplicateEmailError("Email đã được sử dụng.") from exc

    return user
