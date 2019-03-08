import argon2


_password_hasher = None
def password_hasher():
    global _password_hasher

    if _password_hasher is None:
        _password_hasher = argon2.PasswordHasher()

    return _password_hasher
