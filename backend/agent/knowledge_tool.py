from __future__ import annotations


from typing import Any


from langchain_core.tools import StructuredTool

from pydantic import BaseModel, Field


from backend.retrieval.hybrid_retriever import (

    SecureHybridRetriever,

)


class KnowledgeSearchInput(BaseModel):

    query: str = Field(

        min_length=2,

        max_length=1000,

        description=(

            "A focused search query about company policies, "

            "support procedures, warranties, returns, shipping, "

            "billing, troubleshooting, or escalation."

        ),

    )

    use_hyde: bool = Field(

        default=False,

        description=(

            "Whether to use HyDE query expansion. Use only for "

            "vague or difficult policy questions."

        ),

    )


def create_knowledge_search_tool(

    role: str,

    retriever: SecureHybridRetriever,

    *,

    final_results: int = 5,

    max_result_characters: int = 6000,

) -> StructuredTool:
    """

    Create a retrieval tool permanently bound to one authenticated role.



    The role is captured by the application and is not exposed as an

    LLM-controlled tool argument.

    """

    def search_knowledge_base(

        query: str,

        use_hyde: bool = False,

    ) -> dict[str, Any]:

        results = retriever.retrieve(

            query=query,

            role=role,

            use_hyde=use_hyde,

            final_results=final_results,

        )

        formatted_results: list[dict[str, Any]] = []

        total_characters = 0

        for result in results:

            document = result["document"]

            metadata = document.metadata

            content = document.page_content.strip()

            remaining_characters = (

                max_result_characters - total_characters

            )

            if remaining_characters <= 0:

                break

            content = content[:remaining_characters]

            total_characters += len(content)

            formatted_results.append(

                {

                    "content": content,

                    "citation": {

                        "title": metadata[

                            "document_title"

                        ],

                        "section": metadata["section"],

                        "source": metadata["source"],

                        "chunk_id": metadata["chunk_id"],

                    },

                    "access_level": metadata[

                        "access_level"

                    ],

                    "retrieval": {

                        "reranker_score": result[

                            "reranker_score"

                        ],

                        "rank_sources": result[

                            "rank_sources"

                        ],

                        "hyde_used": result["hyde_used"],

                    },

                }

            )

        return {

            "status": "success",

            "query": query,

            "result_count": len(formatted_results),

            "results": formatted_results,

            "instruction": (

                "Use only these retrieved passages as policy "

                "evidence. Cite the source title and section. "

                "Do not cite a HyDE passage."

            ),

        }

    return StructuredTool.from_function(

        func=search_knowledge_base,

        name="search_knowledge_base",

        description=(

            "Search the authorized company knowledge base for "

            "shipping, returns, refunds, damaged items, warranty, "

            "billing, cancellation, troubleshooting, escalation, "

            "and support procedures. The search is automatically "

            "restricted to documents allowed for the authenticated "

            "role. Use this tool for policy or procedural questions."

        ),

        args_schema=KnowledgeSearchInput,
    )
