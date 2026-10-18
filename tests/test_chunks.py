import json

from pathlib import Path

 

 

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CHUNKS_FILE = PROJECT_ROOT / "data" / "processed" / "chunks.jsonl"

 

 

def main():

    if not CHUNKS_FILE.exists():

        raise FileNotFoundError(

            "chunks.jsonl was not found. Run: python ingestion/load_and_chunk.py"

        )

 

    chunks = []

 

    with CHUNKS_FILE.open("r", encoding="utf-8") as file:

        for line in file:

            chunks.append(json.loads(line))

 

    print(f"Total chunks loaded: {len(chunks)}")

 

    if len(chunks) == 0:

        raise ValueError("No chunks found in chunks.jsonl")

 

    required_metadata_fields = [

        "source",

        "source_path",

        "document_title",

        "document_type",

        "chunk_id",

        "chunk_index",

        "chunk_char_count",

    ]

 

    for chunk in chunks:

        if "page_content" not in chunk:

            raise ValueError("A chunk is missing page_content")

 

        if not chunk["page_content"].strip():

            raise ValueError("A chunk has empty page_content")

 

        metadata = chunk.get("metadata", {})

 

        for field in required_metadata_fields:

            if field not in metadata:

                raise ValueError(f"A chunk is missing metadata field: {field}")

 

    sources = sorted(set(chunk["metadata"]["source"] for chunk in chunks))

 

    print("Sources found:")

    for source in sources:

        print(f"- {source}")

 

    print("Chunk validation passed.")

 

 

if __name__ == "__main__":

    main()