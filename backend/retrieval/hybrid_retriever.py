import json

import math

import os

import re

from collections import defaultdict

from pathlib import Path

from typing import Any

 

import yaml

from dotenv import load_dotenv

from langchain_chroma import Chroma

from langchain_core.documents import Document

from langchain_core.prompts import ChatPromptTemplate

from langchain_huggingface import HuggingFaceEmbeddings

from backend.llm.provider import create_chat_model

from rank_bm25 import BM25Okapi

from sentence_transformers import CrossEncoder

 

from backend.security.rbac import (

    build_chroma_access_filter,

    get_allowed_access_levels,

)

 

 

PROJECT_ROOT = Path(__file__).resolve().parents[2]

CHUNKS_FILE = PROJECT_ROOT / "data" / "processed" / "chunks.jsonl"

RETRIEVAL_CONFIG_FILE = PROJECT_ROOT / "configs" / "retrieval.yaml"

 

load_dotenv(PROJECT_ROOT / ".env")

 

 

def tokenize(text: str) -> list[str]:

    """

    Lightweight tokenizer for BM25.

 

    It preserves product and order identifiers reasonably well while

    normalizing ordinary words to lowercase.

    """

    return re.findall(r"[a-zA-Z0-9]+(?:-[a-zA-Z0-9]+)*", text.lower())

 

 

class SecureHybridRetriever:

    def __init__(self) -> None:

        self.config = self._load_config()

        self.all_documents = self._load_documents()

 

        embedding_config = self.config["embedding"]

        vector_config = self.config["vector_store"]

        reranker_config = self.config["reranker"]

 

        self.embedding_model = HuggingFaceEmbeddings(

            model_name=embedding_config["model_name"],

            encode_kwargs={

                "normalize_embeddings": embedding_config.get(

                    "normalize_embeddings",

                    True,

                )

            },

        )

 

        self.vector_store = Chroma(

            collection_name=vector_config["collection_name"],

            embedding_function=self.embedding_model,

            persist_directory=str(

                PROJECT_ROOT / vector_config["persist_directory"]

            ),

        )

 

        self.reranker = CrossEncoder(

            reranker_config["model_name"]

        )

 

        # Build one authorized BM25 index per role.

        self.role_bm25_indexes: dict[

            str,

            tuple[BM25Okapi, list[Document]],

        ] = {}

 

    def _load_config(self) -> dict[str, Any]:

        with RETRIEVAL_CONFIG_FILE.open("r", encoding="utf-8") as file:

            return yaml.safe_load(file)

 

    def _load_documents(self) -> list[Document]:

        if not CHUNKS_FILE.exists():

            raise FileNotFoundError(

                "chunks.jsonl was not found. Run the ingestion pipeline first."

            )

 

        documents: list[Document] = []

 

        with CHUNKS_FILE.open("r", encoding="utf-8") as file:

            for line in file:

                record = json.loads(line)

                documents.append(

                    Document(

                        page_content=record["page_content"],

                        metadata=record["metadata"],

                    )

                )

 

        return documents

 

    def _get_authorized_documents(self, role: str) -> list[Document]:

        allowed_levels = set(get_allowed_access_levels(role))

 

        if not allowed_levels:

            return []

 

        return [

            document

            for document in self.all_documents

            if document.metadata.get("access_level") in allowed_levels

        ]

 

    def _get_bm25_index(

        self,

        role: str,

    ) -> tuple[BM25Okapi, list[Document]] | None:

        """

        BM25 is built only from documents the role may access.

 

        This prevents restricted chunks from entering the lexical candidate

        set, even temporarily.

        """

        if role in self.role_bm25_indexes:

            return self.role_bm25_indexes[role]

 

        authorized_documents = self._get_authorized_documents(role)

 

        if not authorized_documents:

            return None

 

        tokenized_corpus = [

            tokenize(document.page_content)

           for document in authorized_documents

        ]

 

        index = BM25Okapi(tokenized_corpus)

        result = (index, authorized_documents)

        self.role_bm25_indexes[role] = result

 

        return result

 

    def _dense_search(

        self,

        query: str,

        role: str,

        limit: int,

    ) -> list[Document]:

        access_filter = build_chroma_access_filter(role)

 

        # Critical: never replace this with an unfiltered search.

        if access_filter is None:

            return []

 

        return self.vector_store.similarity_search(

            query=query,

            k=limit,

            filter=access_filter,

        )

 

    def _bm25_search(

        self,

        query: str,

        role: str,

        limit: int,

    ) -> list[Document]:

        index_data = self._get_bm25_index(role)

 

        if index_data is None:

            return []

 

        index, documents = index_data

        scores = index.get_scores(tokenize(query))

 

        ranked_indexes = sorted(

            range(len(scores)),

            key=lambda index_value: scores[index_value],

            reverse=True,

        )

 

        results: list[Document] = []

 

        for index_value in ranked_indexes:

            if scores[index_value] <= 0:

                continue

 

            results.append(documents[index_value])

 

            if len(results) >= limit:

                break

 

        return results

 

    def _generate_hyde_passage(

        self,

        query: str,

    ) -> str:

        """

        Generate a hypothetical support passage used only for retrieval.

 

        The generated passage is never returned as evidence and never used

        as an answer. Final responses must use retrieved company documents.

        """

        hyde_config = self.config["hyde"]
        provider = hyde_config.get(
            "provider",
            os.getenv("LLM_PROVIDER", "google")
        ).lower()

        if provider in {"google", "gemini"} and not os.getenv("GOOGLE_API_KEY"):
            raise RuntimeError(
                "GOOGLE_API_KEY is required when HyDE is enabled with Gemini."
            )
        if provider == "openai" and not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError(
                "OPENAI_API_KEY is required when HyDE is enabled with OpenAI."
            )
        model = create_chat_model(
            provider=provider,
            model_name=hyde_config["model_name"],
            temperature=hyde_config.get("temperature", 0.0),
        )


 

        prompt = ChatPromptTemplate.from_messages(

            [

                (

                    "system",

                    """

Write a short hypothetical customer-support knowledge-base passage

that would answer the user's question.

 

The passage is only a search query expansion. It is not a final answer.

 

Requirements:

- Use neutral policy-style language.

- Do not invent order details, customer data, credentials, or private data.

- Do not claim access to internal company rules.

- Do not include source citations.

- Keep the passage under 140 words.

""".strip(),

                ),

                (

                    "human",

                    "{query}",

                ),

            ]

        )

 

        response = (prompt | model).invoke({"query": query})

        return response.content.strip()

 

    def _reciprocal_rank_fusion(

        self,

        ranked_lists: list[tuple[str, list[Document], float]],

    ) -> list[dict[str, Any]]:

        """

        Combine rankings using weighted Reciprocal Rank Fusion.

 

        RRF score:

            sum(weight / (constant + rank))

 

        Raw dense, BM25 and HyDE scores are not directly comparable.

        RRF combines their positions instead of their raw scores.

        """

        fusion_config = self.config["rank_fusion"]

        rrf_constant = fusion_config.get("rrf_constant", 60)

 

        fused_scores: dict[str, float] = defaultdict(float)

        documents_by_id: dict[str, Document] = {}

        rank_sources: dict[str, dict[str, int]] = defaultdict(dict)

 

        for source_name, documents, weight in ranked_lists:

            for rank, document in enumerate(documents, start=1):

                chunk_id = document.metadata["chunk_id"]

 

                fused_scores[chunk_id] += weight / (

                    rrf_constant + rank

                )

                documents_by_id[chunk_id] = document

                rank_sources[chunk_id][source_name] = rank

 

        ordered_ids = sorted(

            fused_scores,

            key=fused_scores.get,

            reverse=True,

        )

 

        return [

            {

                "document": documents_by_id[chunk_id],

                "fusion_score": fused_scores[chunk_id],

                "rank_sources": rank_sources[chunk_id],

            }

            for chunk_id in ordered_ids

        ]

 

    def _rerank(

        self,

        query: str,

        fused_results: list[dict[str, Any]],

        limit: int,

    ) -> list[dict[str, Any]]:

        if not fused_results:

            return []

 

        pairs = [

            [query, result["document"].page_content]

            for result in fused_results

        ]

 

        reranker_scores = self.reranker.predict(pairs)

 

        for result, score in zip(fused_results, reranker_scores):

            result["reranker_score"] = float(score)

 

        reranked = sorted(

            fused_results,

            key=lambda result: result["reranker_score"],

            reverse=True,

        )

 

        return reranked[:limit]

 

    def retrieve(

        self,

        query: str,

        role: str,

        use_hyde: bool | None = None,

        final_results: int | None = None,

    ) -> list[dict[str, Any]]:

        """

        Run secure hybrid retrieval.

 

        Authorization is enforced before retrieval. Unknown roles receive

        no results.

        """

        query = query.strip()

 

        if not query:

            raise ValueError("Query cannot be empty.")

 

        allowed_levels = get_allowed_access_levels(role)

 

        if not allowed_levels:

            return []

 

        retrieval_config = self.config["retrieval"]

        fusion_config = self.config["rank_fusion"]

        hyde_config = self.config["hyde"]

 

        if use_hyde is None:

            use_hyde = hyde_config.get(

                "enabled_by_default",

                False,

            )

 

        dense_results = self._dense_search(

            query=query,

            role=role,

            limit=retrieval_config["dense_candidates"],

        )

 

        bm25_results = self._bm25_search(

            query=query,

            role=role,

            limit=retrieval_config["bm25_candidates"],

        )

 

        ranked_lists: list[tuple[str, list[Document], float]] = [

            (

                "dense",

                dense_results,

                fusion_config.get("dense_weight", 1.0),

            ),

            (

                "bm25",

                bm25_results,

                fusion_config.get("bm25_weight", 1.0),

            ),

        ]

 

        hyde_passage = None

 

        if use_hyde:

            hyde_passage = self._generate_hyde_passage(query)

 

            hyde_results = self._dense_search(

                query=hyde_passage,

                role=role,

                limit=retrieval_config["dense_candidates"],

            )

 

            ranked_lists.append(

                (

                    "hyde",

                    hyde_results,

                    fusion_config.get("hyde_weight", 0.7),

                )

            )

 

        fused_results = self._reciprocal_rank_fusion(ranked_lists)

 

        fused_limit = retrieval_config["fused_candidates"]

        fused_results = fused_results[:fused_limit]

 

        final_limit = (

            final_results

            if final_results is not None

            else retrieval_config["final_results"]

        )

 

        reranked_results = self._rerank(

            query=query,

            fused_results=fused_results,

            limit=final_limit,

        )

 

        authorized_levels = set(allowed_levels)

 

        # Defense in depth: verify authorization after reranking as well.

        for result in reranked_results:

            access_level = result["document"].metadata.get(

                "access_level"

            )

 

            if access_level not in authorized_levels:

                raise PermissionError(

                    "Unauthorized document entered the retrieval result."

                )

 

            result["hyde_used"] = use_hyde

            result["hyde_passage"] = hyde_passage

 

        return reranked_results

 

 

def format_result(

    result: dict[str, Any],

    position: int,

) -> str:

    document = result["document"]

    metadata = document.metadata

 

    return (

        f"\nResult {position}\n"

        f"{'-' * 80}\n"

        f"Title: {metadata['document_title']}\n"

        f"Section: {metadata['section']}\n"

        f"Source: {metadata['source']}\n"

        f"Access level: {metadata['access_level']}\n"

        f"Chunk ID: {metadata['chunk_id']}\n"

        f"Fusion score: {result['fusion_score']:.6f}\n"

        f"Reranker score: {result['reranker_score']:.6f}\n"

        f"Found by: {result['rank_sources']}\n\n"

        f"{document.page_content}\n"

    )

 

 

def main() -> None:

    retriever = SecureHybridRetriever()

 

    query = input("Query: ").strip()

    role = input(

        "Role [customer/support_agent/supervisor/app_admin]: "

    ).strip()

 

    use_hyde_input = input(

        "Use HyDE? [y/N]: "

    ).strip().lower()

 

    use_hyde = use_hyde_input == "y"

 

    results = retriever.retrieve(

        query=query,

        role=role,

        use_hyde=use_hyde,

    )

 

    if not results:

        print("No authorized results were found.")

        return

 

    if use_hyde:

        print("\nHyDE passage:")

        print("-" * 80)

        print(results[0]["hyde_passage"])

 

    for position, result in enumerate(results, start=1):

        print(format_result(result, position))

if __name__ == "__main__":
    main()