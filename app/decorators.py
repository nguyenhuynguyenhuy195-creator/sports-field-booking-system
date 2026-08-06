from functools import wraps
from typing import Callable, TypeVar

from flask import abort
from flask_login import current_user, login_required

from app.models import UserRole


ViewFunction = TypeVar("ViewFunction", bound=Callable)


def roles_required(*roles: UserRole | str):
    """Require authentication and one of the allowed backend roles."""
    allowed_roles = {
        role.value if isinstance(role, UserRole) else role for role in roles
    }

    def decorator(view: ViewFunction) -> ViewFunction:
        @wraps(view)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.role not in allowed_roles:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator
