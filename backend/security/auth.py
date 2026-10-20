from __future__ import annotations


import os

from dataclasses import dataclass

from datetime import datetime, timedelta, timezone

from functools import lru_cache

from pathlib import Path

from typing import Optional

from uuid import uuid4


import jwt

from dotenv import load_dotenv

from jwt import InvalidTokenError

from pwdlib import PasswordHash

from sqlalchemy import select

from sqlalchemy.orm import Session


from backend.database.models import AppUser


PROJECT_ROOT = Path(__file__).resolve().parents[2]


load_dotenv(PROJECT_ROOT / ".env")


PASSWORD_HASHER = PasswordHash.recommended()


# Used to reduce username-enumeration timing differences.

DUMMY_PASSWORD_HASH = PASSWORD_HASHER.hash(

    "not-a-real-user-password"

)


class AuthenticationError(Exception):

    """Raised when authentication or token validation fails."""


@dataclass(frozen=True)
class AuthContext:

    identity_subject: str

    token_id: str


@lru_cache(maxsize=1)
def get_jwt_settings() -> dict[str, object]:

    secret_key = os.getenv(

        "JWT_SECRET_KEY",

        "",

    ).strip()

    issuer = os.getenv(

        "JWT_ISSUER",

        "",

    ).strip()

    audience = os.getenv(

        "JWT_AUDIENCE",

        "",

    ).strip()

    expiry_value = os.getenv(

        "ACCESS_TOKEN_EXPIRE_MINUTES",

        "30",

    ).strip()

    if len(secret_key) < 32:

        raise RuntimeError(

            "JWT_SECRET_KEY must be configured with at least "

            "32 characters."

        )

    if not issuer:

        raise RuntimeError("JWT_ISSUER is not configured.")

    if not audience:

        raise RuntimeError("JWT_AUDIENCE is not configured.")

    try:

        expiry_minutes = int(expiry_value)

    except ValueError as error:

        raise RuntimeError(

            "ACCESS_TOKEN_EXPIRE_MINUTES must be an integer."

        ) from error

    if expiry_minutes <= 0:

        raise RuntimeError(

            "ACCESS_TOKEN_EXPIRE_MINUTES must be positive."

        )

    return {

        "secret_key": secret_key,

        "issuer": issuer,

        "audience": audience,

        "expiry_minutes": expiry_minutes,

        "algorithm": "HS256",

    }


def authenticate_user(

    session: Session,

    username: str,

    password: str,

) -> Optional[AppUser]:
    """

    Verify a username and password.



    The same generic failure behavior is used for unknown usernames,

    incorrect passwords, and inactive users.

    """

    normalized_username = username.strip()

    statement = select(AppUser).where(

        AppUser.username == normalized_username

    )

    user = session.scalar(statement)

    if user is None:

        PASSWORD_HASHER.verify(

            password,

            DUMMY_PASSWORD_HASH,

        )

        return None

    try:

        password_valid = PASSWORD_HASHER.verify(

            password,

            user.password_hash,

        )

    except Exception:

        return None

    if not password_valid or not user.is_active:

        return None

    return user


def create_access_token(

    user: AppUser,

    expires_delta: Optional[timedelta] = None,

) -> str:

    settings = get_jwt_settings()

    now = datetime.now(timezone.utc)

    if expires_delta is None:

        expires_delta = timedelta(

            minutes=int(settings["expiry_minutes"])

        )

    expires_at = now + expires_delta

    token_id = uuid4().hex

    payload = {

        "sub": user.identity_subject,

        "iss": settings["issuer"],

        "aud": settings["audience"],

        "iat": now,

        "nbf": now,

        "exp": expires_at,

        "jti": token_id,

        "token_type": "access",

    }

    return jwt.encode(

        payload,

        settings["secret_key"],

        algorithm=settings["algorithm"],

    )


def verify_access_token(token: str) -> AuthContext:
    """

    Verify signature and all required security claims.



    The role and customer ID are intentionally not accepted from the token.

    They are loaded from the current database record after verification.

    """

    if not token or not token.strip():

        raise AuthenticationError(

            "Access token is missing."

        )

    settings = get_jwt_settings()

    try:

        payload = jwt.decode(

            token.strip(),

            settings["secret_key"],

            algorithms=[settings["algorithm"]],

            issuer=settings["issuer"],

            audience=settings["audience"],

            options={

                "require": [

                    "sub",

                    "iss",

                    "aud",

                    "iat",

                    "nbf",

                    "exp",

                    "jti",

                    "token_type",

                ]

            },

        )

    except InvalidTokenError as error:

        raise AuthenticationError(

            "Access token is invalid or expired."

        ) from error

    if payload.get("token_type") != "access":

        raise AuthenticationError(

            "Incorrect token type."

        )

    identity_subject = payload.get("sub")

    token_id = payload.get("jti")

    if not isinstance(identity_subject, str):

        raise AuthenticationError(

            "Token subject is invalid."

        )

    if not isinstance(token_id, str):

        raise AuthenticationError(

            "Token identifier is invalid."

        )

    return AuthContext(

        identity_subject=identity_subject,

        token_id=token_id,

    )
