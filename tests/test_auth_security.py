import os

from datetime import timedelta


from dotenv import load_dotenv


from backend.database.session import SessionLocal

from backend.security.auth import (

    AuthenticationError,

    authenticate_user,

    create_access_token,

    verify_access_token,

)

from backend.security.authorization import (

    get_role_permissions,

    has_permission,

)


load_dotenv()


DEMO_PASSWORD = os.getenv(

    "DEMO_USER_PASSWORD",

    "",

)


def test_valid_login() -> None:

    with SessionLocal() as session:

        user = authenticate_user(

            session,

            "customer_ava",

            DEMO_PASSWORD,

        )

        assert user is not None

        assert user.identity_subject == "local-customer-ava"

        assert user.role == "customer"


def test_invalid_password() -> None:

    with SessionLocal() as session:

        user = authenticate_user(

            session,

            "customer_ava",

            "definitely-the-wrong-password",

        )

        assert user is None


def test_unknown_username() -> None:

    with SessionLocal() as session:

        user = authenticate_user(

            session,

            "unknown_user",

            "definitely-the-wrong-password",

        )

        assert user is None


def test_valid_token() -> None:

    with SessionLocal() as session:

        user = authenticate_user(

            session,

            "customer_ava",

            DEMO_PASSWORD,

        )

        assert user is not None

        token = create_access_token(user)

        context = verify_access_token(token)

        assert context.identity_subject == (

            "local-customer-ava"

        )

        assert context.token_id


def test_tampered_token_is_rejected() -> None:

    with SessionLocal() as session:

        user = authenticate_user(

            session,

            "customer_ava",

            DEMO_PASSWORD,

        )

        assert user is not None

        token = create_access_token(user)

    replacement = (

        "a"

        if token[-1] != "a"

        else "b"

    )

    tampered_token = token[:-1] + replacement

    try:

        verify_access_token(tampered_token)

    except AuthenticationError:

        return

    raise AssertionError(

        "Tampered JWT was accepted."

    )


def test_expired_token_is_rejected() -> None:

    with SessionLocal() as session:

        user = authenticate_user(

            session,

            "customer_ava",

            DEMO_PASSWORD,

        )

        assert user is not None

        token = create_access_token(

            user,

            expires_delta=timedelta(seconds=-1),

        )

    try:

        verify_access_token(token)

    except AuthenticationError:

        return

    raise AssertionError(

        "Expired JWT was accepted."

    )


def test_permissions() -> None:

    assert has_permission(

        "customer",

        "read_order",

    )

    assert not has_permission(

        "customer",

        "approve_refund",

    )

    assert has_permission(

        "supervisor",

        "approve_refund",

    )

    assert has_permission(

        "app_admin",

        "read_audit_logs",

    )

    assert not has_permission(

        "app_admin",

        "read_order",

    )

    assert not has_permission(

        "unknown_role",

        "read_order",

    )

    assert not has_permission(

        "customer",

        "unknown_permission",

    )


def test_role_permission_listing() -> None:

    customer_permissions = get_role_permissions(

        "customer"

    )

    assert "read_order" in customer_permissions

    assert "read_refund" in customer_permissions

    assert "approve_refund" not in customer_permissions

    unknown_permissions = get_role_permissions(

        "unknown_role"

    )

    assert unknown_permissions == set()


def main() -> None:

    if len(DEMO_PASSWORD) < 12:

        raise RuntimeError(

            "Configure DEMO_USER_PASSWORD in .env "

            "before running this test."

        )

    tests = [

        test_valid_login,

        test_invalid_password,

        test_unknown_username,

        test_valid_token,

        test_tampered_token_is_rejected,

        test_expired_token_is_rejected,

        test_permissions,

        test_role_permission_listing,

    ]

    for test in tests:

        test()

        print(f"{test.__name__}: passed")

    print("All authentication and authorization tests passed.")

if __name__ == "__main__":
    main()
