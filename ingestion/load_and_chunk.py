import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


PROJECT_ROOT = Path(__file__).resolve().parents[1]

RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"

PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"

OUTPUT_FILE = PROCESSED_DATA_DIR / "chunks.jsonl"

RBAC_POLICY_FILE = PROJECT_ROOT / "configs" / "rbac_policy.yaml"


FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

REQUIRED_FRONTMATTER_FIELDS = ["doc_id", "title",
                               "access_level", "department", "owner", "version"]


def load_rbac_policy(path: Path = RBAC_POLICY_FILE) -> Dict[str, Any]:
    """Load the central RBAC policy (single source of truth for access levels)."""

    if not path.exists():

        raise FileNotFoundError(f"RBAC policy not found: {path}")

    with path.open("r", encoding="utf-8") as file:

        return yaml.safe_load(file)


def parse_frontmatter(text: str) -> Tuple[Dict[str, Any], str]:
    """Split YAML frontmatter from Markdown body. Returns (metadata, body)."""

    text = text.replace("\r\n", "\n").lstrip("\ufeff")

    match = FRONTMATTER_PATTERN.match(text)

    if not match:

        return {}, text

    metadata = yaml.safe_load(match.group(1)) or {}

    body = text[match.end():].strip() + "\n"

    return metadata, body


def resolve_access_level(frontmatter: Dict[str, Any], file_name: str,

                         valid_levels: List[str], default_level: str) -> str:
    """Fail-closed access resolution: missing label -> default (restricted); invalid label -> error."""

    level = frontmatter.get("access_level")

    if level is None:

        print(
            f"WARNING: {file_name} has no access_level. Defaulting to '{default_level}' (fail-closed).")

        return default_level

    level = str(level).strip().lower()

    if level not in valid_levels:

        raise ValueError(
            f"{file_name}: invalid access_level '{level}'. Allowed: {valid_levels}")

    return level


def extract_title(markdown_text: str, fallback_title: str) -> str:

    for line in markdown_text.splitlines():

        if line.strip().startswith("# "):

            return line.strip()[2:].strip()

    return fallback_title


def extract_section(chunk_text: str) -> str:
    """Return the first '## ' heading inside a chunk, used for precise citations."""

    for line in chunk_text.splitlines():

        if line.strip().startswith("## "):

            return line.strip()[3:].strip()

    return "Overview"


def load_markdown_documents(raw_data_dir: Path, policy: Dict[str, Any]) -> List[Document]:

    valid_levels = policy["access_levels"]

    default_level = policy["default_access_level"]

    markdown_files = sorted(raw_data_dir.glob("*.md"))

    if not markdown_files:

        raise FileNotFoundError(f"No Markdown files found in {raw_data_dir}")

    documents = []

    seen_doc_ids = set()

    for file_path in markdown_files:

        raw_text = file_path.read_text(encoding="utf-8")

        frontmatter, body = parse_frontmatter(raw_text)

        missing = [f for f in REQUIRED_FRONTMATTER_FIELDS if f not in frontmatter]

        if missing:

            print(
                f"WARNING: {file_path.name} is missing frontmatter fields: {missing}")

        doc_id = str(frontmatter.get("doc_id", file_path.stem))

        if doc_id in seen_doc_ids:

            raise ValueError(
                f"Duplicate doc_id '{doc_id}' in {file_path.name}")

        seen_doc_ids.add(doc_id)

        access_level = resolve_access_level(
            frontmatter, file_path.name, valid_levels, default_level)

        # All metadata values are strings/ints so they are compatible with vector DB metadata.

        metadata = {

            "doc_id": doc_id,

            "source": file_path.name,

            "source_path": file_path.relative_to(PROJECT_ROOT).as_posix(),

            "document_title": str(frontmatter.get("title", extract_title(body, file_path.stem))),

            "document_type": "customer_support_knowledge",

            "access_level": access_level,

            "department": str(frontmatter.get("department", "unknown")),

            "owner": str(frontmatter.get("owner", "unknown")),

            "version": str(frontmatter.get("version", "0.0")),

            "last_reviewed": str(frontmatter.get("last_reviewed", "unknown")),

            "content_hash": hashlib.sha256(body.encode("utf-8")).hexdigest()[:16],

        }

        documents.append(Document(page_content=body, metadata=metadata))

    return documents


def chunk_documents(documents: List[Document]) -> List[Document]:

    splitter = RecursiveCharacterTextSplitter(

        chunk_size=700,

        chunk_overlap=120,

        separators=["\n## ", "\n### ", "\n\n", "\n", ". ", " ", ""],

    )

    all_chunks: List[Document] = []

    for document in documents:

        doc_chunks = splitter.split_documents([document])

        for index, chunk in enumerate(doc_chunks):

            chunk.metadata["chunk_id"] = f"{document.metadata['doc_id']}::chunk_{index:03d}"

            chunk.metadata["chunk_index"] = index

            chunk.metadata["chunk_char_count"] = len(chunk.page_content)

            chunk.metadata["section"] = extract_section(chunk.page_content)

            all_chunks.append(chunk)

    return all_chunks


def save_chunks_jsonl(chunks: List[Document], output_file: Path) -> None:

    output_file.parent.mkdir(parents=True, exist_ok=True)

    with output_file.open("w", encoding="utf-8") as file:

        for chunk in chunks:

            record = {"page_content": chunk.page_content,
                      "metadata": chunk.metadata}

            file.write(json.dumps(record, ensure_ascii=False) + "\n")


def print_summary(documents: List[Document], chunks: List[Document]) -> None:

    print("\nDocument Loading Summary")

    print("-" * 90)

    print(f"Documents loaded: {len(documents)}")

    print(f"Chunks created:   {len(chunks)}\n")

    print(f"{'source':<38}{'access_level':<14}{'department':<20}chunks")

    chunk_counts = Counter(c.metadata["doc_id"] for c in chunks)

    for doc in documents:

        m = doc.metadata

        print(
            f"{m['source']:<38}{m['access_level']:<14}{m['department']:<20}{chunk_counts[m['doc_id']]}")

    print("\nChunks per access level:")

    for level, count in sorted(Counter(c.metadata["access_level"] for c in chunks).items()):

        print(f"- {level}: {count}")

    lengths = [len(c.page_content) for c in chunks]

    print(f"\nAvg chunk length: {sum(lengths) / len(lengths):.0f} chars "

          f"(min {min(lengths)}, max {max(lengths)})")

    print(f"\nOutput: {OUTPUT_FILE}")


def main() -> None:

    policy = load_rbac_policy()

    documents = load_markdown_documents(RAW_DATA_DIR, policy)

    chunks = chunk_documents(documents)

    save_chunks_jsonl(chunks, OUTPUT_FILE)

    print_summary(documents, chunks)


if __name__ == "__main__":

    main()
