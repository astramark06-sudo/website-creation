"""Server-side scoped operations; caller must use one atomic SQLite transaction."""
from django.contrib.auth import get_user_model
from django.db import connection

from scripts.creator_access import Action, Principal, Role, require_access
from scripts.creator_relational import LIMIT, record_id, validate_schema, table_definition
from .models import Membership, MembershipEvent, Record, Workspace


class NotAuthenticated(Exception):
    pass


class NotMember(Exception):
    pass


def require_transaction():
    if not connection.in_atomic_block or connection.vendor != "sqlite":
        raise RuntimeError("Staging operations require an atomic SQLite transaction")


def authorized_workspace(user, slug, action):
    require_transaction()
    if not user.is_authenticated or not get_user_model().objects.filter(pk=user.pk, is_active=True).exists():
        raise NotAuthenticated()
    member = Membership.objects.select_related("workspace").filter(
        user_id=user.pk, workspace__slug=slug, active=True
    ).first()
    if member is None:
        raise NotMember()
    try:
        role = Role(member.role)
    except ValueError:
        raise NotMember() from None
    workspace = member.workspace
    require_access(Principal(str(user.pk), workspace.slug, role, True), slug, action)
    return workspace


def scoped(workspace, table):
    return Record.objects.filter(workspace=workspace, table_id=table)


def checked_values(workspace, definition, data):
    fields = definition["fields"]
    if not isinstance(data, dict) or set(data) != {field["id"] for field in fields}:
        raise ValueError("Provide exactly the declared fields")
    for field in fields:
        value, kind = data[field["id"]], field["type"]
        if kind == "text":
            if not isinstance(value, str) or len(value) > 160 or any(
                    ord(c) < 32 and c not in "\t\n\r" or 0xD800 <= ord(c) <= 0xDFFF for c in value):
                raise ValueError("Invalid text")
        elif kind == "integer":
            if type(value) is not int or not 0 <= value <= 1000000:
                raise ValueError("Invalid integer")
        elif kind == "choice":
            if not isinstance(value, str) or value not in field["choices"]:
                raise ValueError("Invalid choice")
        elif value is not None:
            record_id(value)
            if not scoped(workspace, field["target"]).filter(pk=value).exists():
                raise ValueError("Invalid related record")
    return data


def records(workspace, table):
    schema = validate_schema(workspace.schema)
    definition = table_definition(schema, table)
    rows = list(scoped(workspace, table).order_by("id")[:LIMIT+1])
    if len(rows) > LIMIT:
        raise ValueError("Record limit exceeded")
    return [{"id": record_id(row.pk), "values": checked_values(workspace, definition, row.data)} for row in rows]


def change_record(workspace, table, payload):
    require_transaction()
    schema = validate_schema(workspace.schema)
    definition = table_definition(schema, table)
    action = payload["action"]
    if action == "add":
        values = checked_values(workspace, definition, payload["values"])
        if scoped(workspace, table).count() >= LIMIT:
            raise ValueError("Record limit exceeded")
        row = Record.objects.create(workspace=workspace, table_id=table, data=values)
        return {"id": record_id(row.pk)}
    row = scoped(workspace, table).filter(pk=record_id(payload["id"])).first()
    if row is None:
        raise NotMember()
    if action == "edit":
        row.data = checked_values(workspace, definition, payload["values"])
        row.save(update_fields=["data"])
        return {"ok": True}
    if action != "delete":
        raise ValueError("Invalid action")
    # Clear links only inside this workspace, in the same transaction.
    for other in schema["tables"]:
        references = [field for field in other["fields"]
                      if field["type"] == "relation" and field["target"] == table]
        if not references:
            continue
        for related in scoped(workspace, other["id"]):
            updated = False
            checked_values(workspace, other, related.data)
            for field in references:
                if related.data[field["id"]] == row.pk:
                    related.data[field["id"]] = None
                    updated = True
            if updated:
                related.save(update_fields=["data"])
    row.delete()
    return {"ok": True}


def set_member(workspace, actor, payload):
    require_transaction()
    if set(payload) != {"user_id", "role", "active"} or type(payload["active"]) is not bool:
        raise ValueError("Invalid membership update")
    target = get_user_model().objects.filter(pk=record_id(payload["user_id"]), is_active=True).first()
    if target is None:
        raise ValueError("Unknown active account")
    role = Role(payload["role"])
    member = Membership.objects.filter(workspace=workspace, user=target).first()
    if member and member.role == Role.OWNER.value and member.active and (role != Role.OWNER or not payload["active"]):
        if not Membership.objects.filter(workspace=workspace, role=Role.OWNER.value, active=True,
                                         user__is_active=True).exclude(pk=member.pk).exists():
            raise ValueError("Cannot remove the last active owner")
    Membership.objects.update_or_create(workspace=workspace, user=target,
                                        defaults={"role": role.value, "active": payload["active"]})
    MembershipEvent.objects.create(workspace=workspace, actor_id=actor.pk, target_id=target.pk,
                                   role=role.value, active=payload["active"])
    return {"ok": True}


def workspace_list(user):
    if not user.is_authenticated:
        return []
    return list(Workspace.objects.filter(membership__user=user, membership__active=True,
                                         membership__user__is_active=True).order_by("slug"))
