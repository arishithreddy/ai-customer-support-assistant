from backend.llm import create_chat_model


def main() -> None:

    model = create_chat_model(

        provider="google",

        model_name="gemini-3.8-flash",

        temperature=0.0,

    )

    response = model.invoke(

        "Reply with exactly: Gemini is working"

    )

    print(response.content)


if __name__ == "__main__":

    main()
