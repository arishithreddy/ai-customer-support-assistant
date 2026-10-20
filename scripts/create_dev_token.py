from getpass import getpass


from backend.database.session import SessionLocal

from backend.security.auth import (

    authenticate_user,

    create_access_token,

)


def main() -> None:

    print("Local Development Login")

    print("-" * 50)

    username = input("Username: ").strip()

    password = getpass("Password: ")

    with SessionLocal() as session:

        user = authenticate_user(

            session,

            username,

            password,

        )

        if user is None:

            print("Authentication failed.")

            raise SystemExit(1)

        token = create_access_token(user)

    print("\nAuthentication successful.")

    print("Copy this short-lived token into MCP_ACCESS_TOKEN:\n")

    print(token)


if __name__ == "__main__":

    main()
