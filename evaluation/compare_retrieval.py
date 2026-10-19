from backend.retrieval.hybrid_retriever import SecureHybridRetriever

 

 

QUERIES = [

    "How long does standard shipping take?",

    "What should I do if my package has not moved for eight days?",

    "Can a premium customer get a late return exception?",

    "What is the known pairing issue for PROD-101?",

    "What fraud signals require manual review?",

]

 

 

def print_results(results) -> None:

    for position, result in enumerate(results, start=1):

        metadata = result["document"].metadata

 

        print(

            f"{position}. "

            f"{metadata['document_title']} | "

            f"{metadata['section']} | "

            f"{metadata['access_level']} | "

            f"{metadata['chunk_id']} | "

            f"reranker={result['reranker_score']:.4f}"

        )

 

 

def main() -> None:

    retriever = SecureHybridRetriever()

 

    for query in QUERIES:

        print("\n" + "=" * 100)

        print(f"QUERY: {query}")

 

        for role in ["customer", "support_agent", "supervisor", "app_admin"]:

            print(f"\nROLE: {role}")

 

            results = retriever.retrieve(

                query=query,

                role=role,

                use_hyde=False,

                final_results=5,

            )

 

            print_results(results)


if __name__ == "__main__":
    main()  