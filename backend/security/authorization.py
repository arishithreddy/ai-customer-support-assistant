from functools import lru_cache

from pathlib import Path

from typing import Any


import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[2]

PERMISSIONS_FILE = (

    PROJECT_ROOT

    / "configs"

    / "tool_permissions.yaml"

)


@lru_cache(maxsize=1)
def load_permission_policy() -> dict[str, Any]:

    if not PERMISSIONS_FILE.exists():

        raise FileNotFoundError(

            f"Permission policy not found: {PERMISSIONS_FILE}"

        )

    with PERMISSIONS_FILE.open(

        "r",

        encoding="utf-8",

    ) as file:

        policy = yaml.safe_load(file)

    if not isinstance(policy, dict):

        raise ValueError(

            "Tool permission policy must be a YAML object."

        )

    return policy


def has_permission(

    role: str,

    permission: str,

) -> bool:
    """

    Return True only when the role is explicitly allowed.



    Unknown roles, unknown permissions, and malformed policy entries

    always fail closed.

    """

    if not role or not permission:

        return False

    policy = load_permission_policy()

    permission_config = policy.get(

        "permissions",

        {},

    ).get(permission)

    if not isinstance(permission_config, dict):

        return False

    allowed_roles = permission_config.get(

        "allowed_roles",

        [],

    )

    if not isinstance(allowed_roles, list):

        return False

    return role in allowed_roles


def get_role_permissions(role: str) -> set[str]:
    """

    Return all explicitly permitted operations for a role.

    """

    if not role:

        return set()

    policy = load_permission_policy()

    permissions: set[str] = set()

    for permission, config in policy.get(

        "permissions",

        {},

    ).items():

        if not isinstance(config, dict):

            continue

        allowed_roles = config.get(

            "allowed_roles",

            [],

        )

        if role in allowed_roles:

            permissions.add(permission)

    return permissions
