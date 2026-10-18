import json

from pathlib import Path

 

import yaml

 

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CHUNKS_FILE = PROJECT_ROOT / "data" / "processed" / "chunks.jsonl"

RBAC_POLICY_FILE = PROJECT_ROOT / "configs" / "rbac_policy.yaml"

 

REQUIRED_METADATA = [

    "doc_id", "source", "source_path", "document_title", "document_type",

    "access_level", "department", "owner", "version", "content_hash",

    "chunk_id", "chunk_index", "chunk_char_count", "section",

]

 

EXPECTED_LEVELS = {

    "shipping_policy": "public",

    "support_escalation_policy": "internal",

    "agent_troubleshooting_playbook": "internal",

    "ticket_handling_sop": "internal",

    "refund_exception_playbook": "restricted",

    "fraud_detection_guidelines": "restricted",

}

 

 

def load_chunks():

    if not CHUNKS_FILE.exists():

        raise FileNotFoundError("Run: python ingestion/load_and_chunk.py")

    with CHUNKS_FILE.open(encoding="utf-8") as f:

        return [json.loads(line) for line in f]

 

 

def main():

    policy = yaml.safe_load(RBAC_POLICY_FILE.read_text(encoding="utf-8"))

    valid_levels = set(policy["access_levels"])

    chunks = load_chunks()

    assert chunks, "No chunks found"

 

    chunk_ids = set()

    for c in chunks:

        m = c["metadata"]

        assert c["page_content"].strip(), f"Empty chunk: {m.get('chunk_id')}"

        assert not c["page_content"].startswith("---"), f"Frontmatter leaked into text: {m['chunk_id']}"

        for field in REQUIRED_METADATA:

            assert field in m, f"{m.get('chunk_id')} missing metadata field: {field}"

        assert m["access_level"] in valid_levels, f"Invalid access_level in {m['chunk_id']}"

        assert m["chunk_id"] not in chunk_ids, f"Duplicate chunk_id {m['chunk_id']}"

        chunk_ids.add(m["chunk_id"])

 

        # Canary markers must only live in restricted chunks

        if "CANARY" in c["page_content"]:

            assert m["access_level"] == "restricted", f"Canary found in non-restricted chunk {m['chunk_id']}"

 

    for doc_id, expected in EXPECTED_LEVELS.items():

        levels = {c["metadata"]["access_level"] for c in chunks if c["metadata"]["doc_id"] == doc_id}

        assert levels == {expected}, f"{doc_id}: expected {expected}, got {levels}"

 

    print(f"Total chunks: {len(chunks)}")

    print(f"Documents: {len({c['metadata']['doc_id'] for c in chunks})}")

    print("Chunk validation passed.")

 

 

if __name__ == "__main__":
    main()

