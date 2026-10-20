from __future__ import annotations


from dataclasses import asdict

from typing import Any


from langchain_core.tools import StructuredTool

from pydantic import BaseModel, Field


from backend.retrieval.hybrid_retriever import (

    SecureHybridRetriever,

)

from backend.retrieval.self_healing import (

    SelfHealingRetriever,

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

    Create a self-healing retrieval tool bound to one authenticated role.



    The role is captured by trusted application code and is not exposed

    as a tool argument.

    """

    self_healing_retriever = SelfHealingRetriever(

        retriever

    )

    def search_knowledge_base(

        query: str,

        use_hyde: bool = False,

    ) -> dict[str, Any]:

        retrieval_result = self_healing_retriever.retrieve(

            query=query,

            role=role,

            use_hyde=use_hyde,

            final_results=final_results,

        )

        formatted_results: list[dict[str, Any]] = []

        total_characters = 0

        for result in retrieval_result.results:

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

            "status": retrieval_result.status,

            "original_query": query,

            "selected_query": retrieval_result.selected_query,

            "rewritten_query": retrieval_result.rewritten_query,

            "result_count": len(formatted_results),

            "attempts": [

                asdict(attempt)

                for attempt in retrieval_result.attempts

            ],

            "results": formatted_results,

            "instruction": (

                "Use only these retrieved passages as policy evidence. "

                "Cite the source title and section. Do not cite a HyDE "

                "passage. If the retrieved evidence is insufficient, "

                "say that the available knowledge base evidence is "

                "insufficient."

            ),

        }

    return StructuredTool.from_function(

        func=search_knowledge_base,

        name="search_knowledge_base",

        description=(

            "Self-healing search over the authorized company knowledge "

            "base for shipping, returns, refunds, damaged items, warranty, "

            "billing, cancellation, troubleshooting, escalation, and support "

            "procedures. The tool grades retrieval quality and may rewrite "

            "the search query once if evidence is weak. Search is always "

            "restricted to documents allowed for the authenticated role."

        ),

        args_schema=KnowledgeSearchInput,

    )
