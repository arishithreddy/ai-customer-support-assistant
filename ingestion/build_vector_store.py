import json

import shutil

from pathlib import Path

from typing import Any

 

import yaml

from langchain_chroma import Chroma

from langchain_core.documents import Document

from langchain_huggingface import HuggingFaceEmbeddings

 

 

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CHUNKS_FILE = PROJECT_ROOT / "data" / "processed" / "chunks.jsonl"

RETRIEVAL_CONFIG_FILE = PROJECT_ROOT / "configs" / "retrieval.yaml"

 

 

def load_config() -> dict[str, Any]:

    with RETRIEVAL_CONFIG_FILE.open("r", encoding="utf-8") as file:

        return yaml.safe_load(file)

 

 

def load_chunks() -> list[Document]:

    if not CHUNKS_FILE.exists():

        raise FileNotFoundError(

            "Processed chunks were not found. Run "

            "`python ingestion/load_and_chunk.py` first."

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

 

    if not documents:

        raise ValueError("No chunks were found in chunks.jsonl.")

 

    return documents

 

 

def create_embedding_model(config: dict[str, Any]) -> HuggingFaceEmbeddings:

    embedding_config = config["embedding"]

 

    return HuggingFaceEmbeddings(

        model_name=embedding_config["model_name"],

        encode_kwargs={

            "normalize_embeddings": embedding_config.get(

                "normalize_embeddings",

                True,

            )

        },

    )

 

 

def rebuild_vector_store(

    documents: list[Document],

    config: dict[str, Any],

) -> Chroma:

    vector_config = config["vector_store"]

    persist_directory = PROJECT_ROOT / vector_config["persist_directory"]

 

    # Rebuild cleanly so deleted or renamed documents do not remain in Chroma.

    if persist_directory.exists():

        shutil.rmtree(persist_directory)

 

    persist_directory.mkdir(parents=True, exist_ok=True)

 

    embedding_model = create_embedding_model(config)

    chunk_ids = [document.metadata["chunk_id"] for document in documents]

 

    vector_store = Chroma.from_documents(

        documents=documents,

        embedding=embedding_model,

        ids=chunk_ids,

        collection_name=vector_config["collection_name"],

        persist_directory=str(persist_directory),

        collection_metadata={

            "hnsw:space": "cosine"

        },

    )

 

    return vector_store

 

 

def print_summary(

    documents: list[Document],

    vector_store: Chroma,

    config: dict[str, Any],

) -> None:

    access_counts: dict[str, int] = {}

 

    for document in documents:

        level = document.metadata["access_level"]

        access_counts[level] = access_counts.get(level, 0) + 1

 

    collection_count = vector_store._collection.count()

 

    print("\nVector Store Build Summary")

    print("-" * 80)

    print(f"Embedding model: {config['embedding']['model_name']}")

    print(f"Collection: {config['vector_store']['collection_name']}")

    print(f"Documents indexed: {collection_count}")

 

    print("\nChunks by access level:")

    for level, count in sorted(access_counts.items()):

        print(f"- {level}: {count}")

 

    print(

        "\nVector store directory: "

        f"{PROJECT_ROOT / config['vector_store']['persist_directory']}"

    )

 

 

def main() -> None:

    config = load_config()

    documents = load_chunks()

    vector_store = rebuild_vector_store(documents, config)

    print_summary(documents, vector_store, config)

 

 

if __name__ == "__main__":

    main()