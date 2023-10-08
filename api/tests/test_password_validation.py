from typing import ClassVar

from django.core.exceptions import ValidationError
from django.test import TestCase

from api import password_validation
from api.exceptions import UnprocessableContent
from api.models import User


class HasLowercaseValidatorTestCase(TestCase):
    user: ClassVar[User]

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.user = User.objects.create_user("test@test.com", None)

    def test_validate(self):
        validator = password_validation.HasLowercaseValidator()

        validator.validate("a", user=HasLowercaseValidatorTestCase.user)

        with self.assertRaises(ValidationError):
            validator.validate("", user=HasLowercaseValidatorTestCase.user)

        with self.assertRaises(ValidationError):
            validator.validate("A1!", user=HasLowercaseValidatorTestCase.user)


class HasUppercaseValidatorTestCase(TestCase):
    user: ClassVar[User]

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.user = User.objects.create_user("test@test.com", None)

    def test_validate(self):
        validator = password_validation.HasUppercaseValidator()

        validator.validate("A", user=HasUppercaseValidatorTestCase.user)

        with self.assertRaises(ValidationError):
            validator.validate("", user=HasUppercaseValidatorTestCase.user)

        with self.assertRaises(ValidationError):
            validator.validate("a1!", user=HasUppercaseValidatorTestCase.user)


class HasDigitValidatorTestCase(TestCase):
    user: ClassVar[User]

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.user = User.objects.create_user("test@test.com", None)

    def test_validate(self):
        validator = password_validation.HasDigitValidator()

        validator.validate("1", user=HasDigitValidatorTestCase.user)

        with self.assertRaises(ValidationError):
            validator.validate("", user=HasDigitValidatorTestCase.user)

        with self.assertRaises(ValidationError):
            validator.validate("aA!", user=HasDigitValidatorTestCase.user)


class HasSpecialCharacterValidatorTestCase(TestCase):
    user: ClassVar[User]

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.user = User.objects.create_user("test@test.com", None)

    def test_validate(self):
        validator = password_validation.HasSpecialCharacterValidator()

        validator.validate("!", user=HasSpecialCharacterValidatorTestCase.user)

        with self.assertRaises(ValidationError):
            validator.validate("", user=HasSpecialCharacterValidatorTestCase.user)

        with self.assertRaises(ValidationError):
            validator.validate("aA1", user=HasSpecialCharacterValidatorTestCase.user)


class ElevatedCommonPasswordValidatorTestCase(TestCase):
    user: ClassVar[User]

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.user = User.objects.create_user("test@test.com", None)

    def test_validate(self):
        validator = password_validation.ElevatedCommonPasswordValidator()

        with self.assertRaises(UnprocessableContent):
            validator.validate(
                "password1", user=ElevatedCommonPasswordValidatorTestCase.user
            )


class ElevatedUserAttributeSimilarityValidatorTestCase(TestCase):
    user: ClassVar[User]

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.user = User.objects.create_user("test@test.com", None)

    def test_validate(self):
        validator = password_validation.ElevatedUserAttributeSimilarityValidator()

        with self.assertRaises(UnprocessableContent):
            validator.validate(
                "test@test.com",
                user=ElevatedUserAttributeSimilarityValidatorTestCase.user,
            )
