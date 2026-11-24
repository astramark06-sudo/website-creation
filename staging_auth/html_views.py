"""Role-aware HTML views using the same guarded transactions as the JSON API."""
from functools import wraps
from pathlib import Path

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import RequestDataTooBig
from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, HttpResponseNotFound
from django.shortcuts import render, redirect
from django.views.decorators.http import require_GET, require_http_methods

from scripts.creator_access import Action, allowed, require_access
from scripts.creator_relational import record_id, table_definition, validate_schema
from .forms import RecordForm, MemberForm, related_options
from .models import Membership
from .services import NotAuthenticated, NotMember, resolve_membership, records, change_record, set_member


def protected_html(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        try:
            with transaction.atomic():
                workspace, principal = resolve_membership(request.user, kwargs["slug"])
                return view(request, workspace=workspace, principal=principal, **kwargs)
        except NotAuthenticated:
            return redirect_to_login(request.path)
        except NotMember:
            return HttpResponseNotFound("Workspace or record not found.")
        except PermissionError:
            return HttpResponseForbidden("Operation not permitted.")
        except (ValueError, TypeError, KeyError, RequestDataTooBig, RecursionError):
            return HttpResponseBadRequest("Invalid request or workspace data.")
    return wrapped


def checked_post(request, required, optional=()):
    # Reject unexpected or repeated form fields instead of silently discarding them.
    keys = set(request.POST) - {"csrfmiddlewaretoken"}
    if not set(required) <= keys <= set(required) | set(optional):
        raise ValueError("Unexpected form fields")
    if request.FILES or any(len(request.POST.getlist(key)) != 1 for key in request.POST):
        raise ValueError("Invalid form data")


def table_data(workspace, table):
    schema = validate_schema(workspace.schema)
    definition = table_definition(schema, table)
    return definition, related_options(workspace, definition)


def item_for(workspace, table, item_id):
    record_id(item_id)
    row = next((row for row in records(workspace, table) if row["id"] == item_id), None)
    if row is None:
        raise NotMember()
    return row


@require_GET
def stylesheet(request):
    path = Path(__file__).with_name("staging.css")
    return HttpResponse(path.read_bytes(), content_type="text/css; charset=utf-8")


@require_GET
@protected_html
def workspace_page(request, slug, workspace, principal):
    require_access(principal, slug, Action.READ_RECORDS)
    return render(request, "staging_auth/workspace.html", {
        "workspace": workspace, "role": principal.role.value,
        "tables": validate_schema(workspace.schema)["tables"],
        "can_manage": allowed(principal, slug, Action.MANAGE_MEMBERS),
        "can_export": allowed(principal, slug, Action.EXPORT_DATA),
    })


@require_http_methods(["GET", "POST"])
@protected_html
def collection_page(request, slug, table, workspace, principal):
    require_access(principal, slug, Action.CREATE_RECORD if request.method == "POST" else Action.READ_RECORDS)
    definition, options = table_data(workspace, table)
    can_add = allowed(principal, slug, Action.CREATE_RECORD)
    form = RecordForm(definition, options, data=request.POST if request.method == "POST" else None) if can_add else None
    if request.method == "POST":
        checked_post(request, form.fields)
        if form.is_valid():
            change_record(workspace, table, {"action": "add", "values": form.values()})
            return redirect("collection", slug=slug, table=table)
    rows = []
    for row in records(workspace, table):
        fields = []
        for field in definition["fields"]:
            value = row["values"][field["id"]]
            if field["type"] == "relation":
                value = "None" if value is None else dict(options[field["target"]]).get(str(value), "Record #" + str(value))
            fields.append({"label": field["label"], "value": value})
        rows.append({"id": row["id"], "fields": fields})
    return render(request, "staging_auth/collection.html", {
        "workspace": workspace, "table": definition, "rows": rows, "form": form,
        "can_edit": allowed(principal, slug, Action.EDIT_RECORD),
        "can_delete": allowed(principal, slug, Action.DELETE_RECORD),
    })


@require_http_methods(["GET", "POST"])
@protected_html
def edit_page(request, slug, table, item_id, workspace, principal):
    require_access(principal, slug, Action.EDIT_RECORD)
    definition, options = table_data(workspace, table)
    row = item_for(workspace, table, item_id)
    form = RecordForm(definition, options, data=request.POST if request.method == "POST" else None, values=row["values"])
    if request.method == "POST":
        checked_post(request, form.fields)
        if form.is_valid():
            change_record(workspace, table, {"action": "edit", "id": item_id, "values": form.values()})
            return redirect("collection", slug=slug, table=table)
    return render(request, "staging_auth/edit.html", {"workspace": workspace, "table": definition, "item_id": item_id, "form": form})


@require_http_methods(["GET", "POST"])
@protected_html
def delete_page(request, slug, table, item_id, workspace, principal):
    require_access(principal, slug, Action.DELETE_RECORD)
    definition = table_definition(validate_schema(workspace.schema), table)
    item_for(workspace, table, item_id)
    if request.method == "POST":
        checked_post(request, ())
        change_record(workspace, table, {"action": "delete", "id": item_id})
        return redirect("collection", slug=slug, table=table)
    return render(request, "staging_auth/delete.html", {"workspace": workspace, "table": definition, "item_id": item_id})


@require_http_methods(["GET", "POST"])
@protected_html
def members_page(request, slug, workspace, principal):
    require_access(principal, slug, Action.MANAGE_MEMBERS)
    form = MemberForm(request.POST if request.method == "POST" else None)
    if request.method == "POST":
        checked_post(request, ("user_id", "role"), ("active",))
        if form.is_valid():
            try:
                set_member(workspace, request.user, form.cleaned_data)
            except ValueError:
                form.add_error(None, "Membership change rejected. Use an existing active account and retain an active owner.")
            else:
                return redirect("workspace", slug=slug)
    members = Membership.objects.filter(workspace=workspace).order_by("user_id")
    return render(request, "staging_auth/members.html", {"workspace": workspace, "members": members, "form": form})
