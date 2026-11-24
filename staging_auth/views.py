"""Django session and CSRF protected endpoints for the local staging profile."""
import json
from functools import wraps

from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_http_methods
from django.core.exceptions import RequestDataTooBig

from scripts.creator_access import Action
from scripts.creator_relational import unique_object, reject_constant, validate_schema
from .models import Membership
from .services import (NotAuthenticated, NotMember, authorized_workspace, records,
                       change_record, set_member, workspace_list)


def json_body(request):
    if request.content_type != "application/json":
        raise ValueError("Expected JSON")
    body = request.body
    if not 0 < len(body) <= 16384:
        raise ValueError("Invalid body length")
    data = json.loads(body.decode("utf-8"), object_pairs_hook=unique_object, parse_constant=reject_constant)
    if not isinstance(data, dict):
        raise ValueError("Expected JSON object")
    return data


def atomic_endpoint(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        try:
            with transaction.atomic():
                if not request.user.is_authenticated:
                    raise NotAuthenticated()
                return view(request, *args, **kwargs)
        except NotAuthenticated:
            return JsonResponse({"error": "Sign in required"}, status=401)
        except NotMember:
            return JsonResponse({"error": "Not found"}, status=404)
        except PermissionError:
            return JsonResponse({"error": "Operation not permitted"}, status=403)
        except (ValueError, TypeError, KeyError, RequestDataTooBig, RecursionError):
            return JsonResponse({"error": "Invalid request or workspace data"}, status=400)
    return wrapped


@require_GET
def home(request):
    return render(request, "staging_auth/home.html", {"workspaces": workspace_list(request.user)})


@require_GET
@atomic_endpoint
def schema_view(request, slug):
    workspace = authorized_workspace(request.user, slug, Action.READ_RECORDS)
    return JsonResponse({"title": workspace.title, "schema": validate_schema(workspace.schema)})


@require_http_methods(["GET", "POST"])
@atomic_endpoint
def record_view(request, slug, table):
    if request.method == "GET":
        workspace = authorized_workspace(request.user, slug, Action.READ_RECORDS)
        return JsonResponse({"records": records(workspace, table)})
    payload = json_body(request)
    action = payload.get("action")
    rules = {"add": (Action.CREATE_RECORD, {"action", "values"}),
             "edit": (Action.EDIT_RECORD, {"action", "id", "values"}),
             "delete": (Action.DELETE_RECORD, {"action", "id"})}
    if not isinstance(action, str) or action not in rules or set(payload) != rules[action][1]:
        raise ValueError("Invalid mutation")
    workspace = authorized_workspace(request.user, slug, rules[action][0])
    return JsonResponse(change_record(workspace, table, payload))


@require_GET
@atomic_endpoint
def export_view(request, slug):
    workspace = authorized_workspace(request.user, slug, Action.EXPORT_DATA)
    schema = validate_schema(workspace.schema)
    response = JsonResponse({"schema": schema, "tables": {
        table["id"]: records(workspace, table["id"]) for table in schema["tables"]
    }})
    response["Content-Disposition"] = 'attachment; filename="workspace-records.json"'
    return response


@require_http_methods(["GET", "POST"])
@atomic_endpoint
def members_view(request, slug):
    workspace = authorized_workspace(request.user, slug, Action.MANAGE_MEMBERS)
    if request.method == "GET":
        return JsonResponse({"members": list(Membership.objects.filter(workspace=workspace).order_by("user_id").values(
            "user_id", "role", "active"))})
    return JsonResponse(set_member(workspace, request.user, json_body(request)))
