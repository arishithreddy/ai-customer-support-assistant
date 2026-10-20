import asyncio

from getpass import getpass


from backend.agent.graph import (

    create_agent_runtime,

)

from backend.database.session import SessionLocal

from backend.security.auth import (

    authenticate_user,

    create_access_token,

)


async def authenticate() -> str:

    print("Secure Customer Support Agent")

    print("-" * 60)

    username = input("Username: ").strip()

    password = getpass("Password: ")

    with SessionLocal() as session:

        user = authenticate_user(

            session,

            username,

            password,

        )

        if user is None:

            raise PermissionError(

                "Authentication failed."

            )

        return create_access_token(user)


async def main() -> None:

    try:

        access_token = await authenticate()

        print("\nLoading authenticated agent...")

        runtime = await create_agent_runtime(

            access_token

        )

        print(

            f"Authenticated as: "

            f"{runtime.identity.username}"

        )

        print(

            f"Role: {runtime.identity.role}"

        )

        print(

            "Available tools: "

            + ", ".join(runtime.tool_names)

        )

        print(

            "\nType a customer-support question."

        )

        print("Type 'exit' to stop.\n")

        while True:

            question = input("You: ").strip()

            if question.lower() in {

                "exit",

                "quit",

            }:

                print("Session ended.")

                break

            if not question:

                continue

            try:

                response = await runtime.ask(

                    question

                )

                print(f"\nAssistant: {response}\n")

            except Exception as exc:
                print(
                   "\nAssistant: I could not safely "
                    "complete that request. Please try "
                     "again or contact support.\n"
                )
                print(f"DEBUG ERROR: {type(exc).__name__}: {exc}")

    except PermissionError:

        print("Authentication failed.")

    except Exception as error:

        print(

            "The agent could not start. "

            f"Error type: {type(error).__name__}"

        )


if __name__ == "__main__":

    asyncio.run(main())
