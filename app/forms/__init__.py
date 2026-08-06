"""WTForms definitions for user input and validation."""

from .auth import LoginForm, RegistrationForm
from .owner_application import OwnerApplicationForm, ReviewOwnerApplicationForm

__all__ = [
    "LoginForm",
    "OwnerApplicationForm",
    "RegistrationForm",
    "ReviewOwnerApplicationForm",
]
