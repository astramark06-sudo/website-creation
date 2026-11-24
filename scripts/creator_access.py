"""Framework-neutral, deny-by-default workspace authorization contract.

This module does not authenticate callers, issue sessions, or expose HTTP routes.
Only trusted server-side membership lookup may construct a Principal.
"""
from dataclasses import dataclass
from enum import Enum
import re


class Role(str, Enum):
    VIEWER = "viewer"
    EDITOR = "editor"
    OWNER = "owner"


class Action(str, Enum):
    READ_RECORDS = "read_records"
    READ_RELATIONS = "read_relations"
    CREATE_RECORD = "create_record"
    EDIT_RECORD = "edit_record"
    DELETE_RECORD = "delete_record"
    EXPORT_DATA = "export_data"
    MANAGE_MEMBERS = "manage_members"
    MANAGE_SCHEMA = "manage_schema"


READ = frozenset({Action.READ_RECORDS, Action.READ_RELATIONS})
EDIT = READ | frozenset({Action.CREATE_RECORD, Action.EDIT_RECORD})
PERMISSIONS = {
    Role.VIEWER: READ,
    Role.EDITOR: EDIT,
    Role.OWNER: EDIT | frozenset({Action.DELETE_RECORD, Action.EXPORT_DATA,
                                  Action.MANAGE_MEMBERS, Action.MANAGE_SCHEMA}),
}
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z")


def valid_identifier(value):
    return isinstance(value, str) and IDENTIFIER.fullmatch(value) is not None


@dataclass(frozen=True)
class Principal:
    """Resolved by a future trusted identity/membership adapter, never from JSON."""
    subject: str
    workspace: str
    role: Role
    active: bool


def allowed(principal, workspace, action):
    """Return False for anonymous, inactive, mismatched or unknown requests.

    Each workspace has one shared dataset; there is no row- or table-level ACL.
    Membership must be reloaded on every protected operation. This pure check
    cannot itself establish membership freshness or authenticate a subject.
    """
    if type(principal) is not Principal or principal.active is not True:
        return False
    if not all(valid_identifier(value) for value in (principal.subject, principal.workspace, workspace)):
        return False
    if principal.workspace != workspace:
        return False
    if not isinstance(principal.role, Role) or not isinstance(action, Action):
        return False
    return action in PERMISSIONS.get(principal.role, frozenset())


def require_access(principal, workspace, action):
    if not allowed(principal, workspace, action):
        raise PermissionError("Workspace operation not permitted")
