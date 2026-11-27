import re

from django.contrib.auth.models import AbstractBaseUser
from django.core.exceptions import ValidationError


class HasLowercaseValidator:
    def validate(self, password: str, user: AbstractBaseUser | None = None):
        if not re.search(r"[a-z]", password):
            raise ValidationError(
                "This password must contain at least 1 lowercase character.",
                code="password_no_lowercase",
            )

    def get_help_text(self):  # pragma: no cover
        return "Your password must contain at least 1 lowercase letter"


class HasUppercaseValidator:
    def validate(self, password: str, user: AbstractBaseUser | None = None):
        if not re.search(r"[A-Z]", password):
            raise ValidationError(
                "This password must contain at least 1 uppercase character.",
                code="password_no_uppercase",
            )

    def get_help_text(self):  # pragma: no cover
        return "Your password must contain at least 1 uppercase letter"


class HasDigitValidator:
    def validate(self, password: str, user: AbstractBaseUser | None = None):
        if not re.search(r"[0-9]", password):
            raise ValidationError(
                "This password must contain at least 1 digit.",
                code="password_no_digit",
            )

    def get_help_text(self):  # pragma: no cover
        return "Your password must contain at least 1 digit"


class HasSpecialCharacterValidator:
    def __init__(
        self,
        special_characters_regex_tuple: tuple[str, str] = (r"[!@#$%^&?]", "!@#$%^&?"),
    ):
        self.special_characters_regex_str = special_characters_regex_tuple[0]
        self.special_characters = special_characters_regex_tuple[1]

    def validate(self, password: str, user: AbstractBaseUser | None = None):
        if not re.search(self.special_characters_regex_str, password):
            raise ValidationError(
                "This password must contain at least 1 special character (%(special_characters)s).",
                code="password_no_special_character",
                params={"special_characters": "".join(self.special_characters)},
            )

    def get_help_text(self):  # pragma: no cover
        return f"Your password must contain at least 1 special character ({''.join(self.special_characters)})"
