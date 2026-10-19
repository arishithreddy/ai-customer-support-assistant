from functools import lru_cache

from pathlib import Path

from typing import Any

 

import yaml

 

 

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RBAC_POLICY_FILE = PROJECT_ROOT / "configs" / "rbac_policy.yaml"

 

 

@lru_cache(maxsize=1)

def load_rbac_policy() -> dict[str, Any]:

    if not RBAC_POLICY_FILE.exists():

        raise FileNotFoundError(

            f"RBAC policy was not found: {RBAC_POLICY_FILE}"

        )

 

    with RBAC_POLICY_FILE.open("r", encoding="utf-8") as file:

        policy = yaml.safe_load(file)

 

    if not isinstance(policy, dict):

        raise ValueError("RBAC policy must contain a YAML object.")

 

    return policy

 

 

def get_allowed_access_levels(role: str) -> list[str]:

    """

    Return document access levels allowed for a role.

 

    Unknown roles fail closed and receive no permissions.

    """

    if not role:

        return []

 

    policy = load_rbac_policy()

    role_config = policy.get("roles", {}).get(role)

 

    if role_config is None:

        return []

 

    valid_levels = set(policy.get("access_levels", []))

    configured_levels = role_config.get("allowed_access_levels", [])

 

    return [

        level

        for level in configured_levels

        if level in valid_levels

    ]

 

 

def build_chroma_access_filter(role: str) -> dict[str, Any] | None:

    """

    Build a Chroma metadata filter for authorized access levels.

 

    None means the role has no permissions. Callers must not perform

    unfiltered retrieval when this function returns None.

    """

    allowed_levels = get_allowed_access_levels(role)

 

    if not allowed_levels:

        return None

 

    if len(allowed_levels) == 1:

        return {

            "access_level": allowed_levels[0]

        }

 

    return {

        "access_level": {

            "$in": allowed_levels

        }

    }

 

 

def is_access_allowed(role: str, access_level: str) -> bool:

    return access_level in get_allowed_access_levels(role)