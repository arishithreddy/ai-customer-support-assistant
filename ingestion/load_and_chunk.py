import json

from pathlib import Path

from typing import List, Dict, Any

 

from langchain_core.documents import Document

from langchain_text_splitters import RecursiveCharacterTextSplitter

 

 

PROJECT_ROOT = Path(__file__).resolve().parents[1]

RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"

PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"

OUTPUT_FILE = PROCESSED_DATA_DIR / "chunks.jsonl"

 

 

def extract_title(markdown_text: str, fallback_title: str) -> str:

    """
    Extract the first Markdown H1 title from a document.
    If no H1 title exists, use the file name as fallback.
    """

    for line in markdown_text.splitlines():

        clean_line = line.strip()

        if clean_line.startswith("# "):

            return clean_line.replace("# ", "").strip()

    return fallback_title

 

 

def load_markdown_documents(raw_data_dir: Path) -> List[Document]:

    """

    Load all Markdown files from the raw data directory and convert them

    into LangChain Document objects with metadata.

    """

    documents = []

 

    markdown_files = sorted(raw_data_dir.glob("*.md"))

 

    if not markdown_files:

        raise FileNotFoundError(f"No Markdown files found in {raw_data_dir}")

 

    for file_path in markdown_files:

        text = file_path.read_text(encoding="utf-8")

        title = extract_title(text, fallback_title=file_path.stem)

 

        metadata = {

            "source": file_path.name,

            "source_path": str(file_path.relative_to(PROJECT_ROOT)),

            "document_title": title,

            "document_type": "customer_support_policy",

        }

 

        document = Document(

            page_content=text,

            metadata=metadata,

        )

 

        documents.append(document)

 

    return documents

 

 

def chunk_documents(documents: List[Document]) -> List[Document]:

    """

    Split documents into smaller chunks for retrieval.

    The chunk size is selected to keep enough context while avoiding overly long chunks.

    """

    text_splitter = RecursiveCharacterTextSplitter(

        chunk_size=700,

        chunk_overlap=120,

        separators=[

            "\n## ",

            "\n### ",

            "\n\n",

            "\n",

            ". ",

            " ",

            "",

        ],

    )

 

    chunks = text_splitter.split_documents(documents)

 

    for index, chunk in enumerate(chunks):

        chunk.metadata["chunk_id"] = f"chunk_{index:04d}"

        chunk.metadata["chunk_index"] = index

        chunk.metadata["chunk_char_count"] = len(chunk.page_content)

 

    return chunks

 

 

def document_to_json(document: Document) -> Dict[str, Any]:

    """

    Convert a LangChain Document object into a JSON-serializable dictionary.

    """

    return {

        "page_content": document.page_content,

        "metadata": document.metadata,

    }

 

 

def save_chunks_jsonl(chunks: List[Document], output_file: Path) -> None:

    """

    Save chunks as a JSONL file.

    Each line is one chunk with text and metadata.

    """

    output_file.parent.mkdir(parents=True, exist_ok=True)

 

    with output_file.open("w", encoding="utf-8") as file:

        for chunk in chunks:

            file.write(json.dumps(document_to_json(chunk), ensure_ascii=False) + "\n")

 

 

def print_summary(documents: List[Document], chunks: List[Document]) -> None:

    """

    Print useful ingestion and chunking statistics.

    """

    print("\nDocument Loading Summary")

    print("-" * 80)

    print(f"Raw documents loaded: {len(documents)}")

    print(f"Chunks created: {len(chunks)}")

 

    print("\nDocuments:")

    for document in documents:

        source = document.metadata.get("source")

        title = document.metadata.get("document_title")

        char_count = len(document.page_content)

        print(f"- {source} | {title} | {char_count} characters")

 

    chunk_lengths = [len(chunk.page_content) for chunk in chunks]

 

    if chunk_lengths:

        avg_length = sum(chunk_lengths) / len(chunk_lengths)

        min_length = min(chunk_lengths)

        max_length = max(chunk_lengths)

 

        print("\nChunk Statistics:")

        print(f"- Average chunk length: {avg_length:.2f} characters")

        print(f"- Minimum chunk length: {min_length} characters")

        print(f"- Maximum chunk length: {max_length} characters")

 

    print("\nSample Chunk:")

    print("-" * 80)

    sample_chunk = chunks[0]

    print(f"Chunk ID: {sample_chunk.metadata.get('chunk_id')}")

    print(f"Source: {sample_chunk.metadata.get('source')}")

    print(f"Title: {sample_chunk.metadata.get('document_title')}")

    print("\nText:")

    print(sample_chunk.page_content[:700])

 

    print("\nOutput File:")

    print(f"- {OUTPUT_FILE}")

 

 

def main() -> None:

    documents = load_markdown_documents(RAW_DATA_DIR)

    chunks = chunk_documents(documents)

    save_chunks_jsonl(chunks, OUTPUT_FILE)

    print_summary(documents, chunks)

 

 

if __name__ == "__main__":

    main()