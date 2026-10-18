import json

from pathlib import Path

 

import yaml

 

PROJECT_ROOT = Path(__file__).resolve().parents[1]

CHUNKS_FILE = PROJECT_ROOT / "data" / "processed" / "chunks.jsonl"

RBAC_POLICY_FILE = PROJECT_ROOT / "configs" / "rbac_policy.yaml"

 

CANARIES = ["RX-CANARY-7731", "FD-CANARY-4420"]

 

 

def visible_chunks(chunks, role, policy):

    """Fail-closed: unknown role sees nothing."""

    role_cfg = policy["roles"].get(role)

    if role_cfg is None:

        return []

    allowed = set(role_cfg["allowed_access_levels"])

    return [c for c in chunks if c["metadata"]["access_level"] in allowed]

 

 

def main():

    policy = yaml.safe_load(RBAC_POLICY_FILE.read_text(encoding="utf-8"))

    with CHUNKS_FILE.open(encoding="utf-8") as f:

        chunks = [json.loads(line) for line in f]

 

    print(f"{'role':<16}{'visible chunks':<16}canary visible")

    for role in list(policy["roles"]) + ["hacker_unknown_role"]:

        visible = visible_chunks(chunks, role, policy)

        text = " ".join(c["page_content"] for c in visible)

        canary_seen = any(canary in text for canary in CANARIES)

        print(f"{role:<16}{len(visible):<16}{canary_seen}")

 

        if role == "supervisor":

            assert canary_seen, "Supervisor should be able to access restricted docs"

        else:

            assert not canary_seen, f"LEAK: role '{role}' can see restricted content"

 

    customer_levels = {c["metadata"]["access_level"] for c in visible_chunks(chunks, "customer", policy)}

    assert customer_levels == {"public"}, f"Customer sees non-public levels: {customer_levels}"

 

    print("\nAccess filtering test passed. No unauthorized exposure.")

if __name__ == "__main__":
    main()