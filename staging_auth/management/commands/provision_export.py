"""Provision the fixed exported workspace for an existing local test account."""
import json
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction

from scripts.creator_access import Role
from scripts.creator_relational import require_text, validate_schema, unique_object, reject_constant
from staging_auth.models import Workspace, Membership


def read_config(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(65537)
    if len(raw) > 65536:
        raise ValueError("Export configuration exceeds limit")
    config = json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object, parse_constant=reject_constant)
    if (not isinstance(config, dict) or set(config) != {"version", "profile", "title", "description", "schema"}
            or type(config["version"]) is not int or config["version"] != 1
            or config["profile"] != "authenticated-local-staging"):
        raise ValueError("Invalid export configuration")
    return (require_text(config["title"], "Workspace title", 120),
            require_text(config["description"], "Description", 1000),
            validate_schema(config["schema"]))


class Command(BaseCommand):
    help = "Create the exported local workspace and its first owner"

    def add_arguments(self, parser):
        parser.add_argument("--owner", required=True, help="Existing local test-account username")

    def handle(self, *args, **options):
        try:
            title, description, schema = read_config(Path(settings.BASE_DIR) / "workspace-config.json")
            with transaction.atomic():
                owner = get_user_model().objects.get(username=options["owner"], is_active=True)
                workspace = Workspace.objects.create(slug="workspace", title=title, description=description, schema=schema)
                Membership.objects.create(workspace=workspace, user=owner, role=Role.OWNER.value)
        except (ValueError, OSError, IntegrityError, get_user_model().DoesNotExist, RecursionError) as exc:
            raise CommandError("Unable to provision exported workspace; check configuration and existing active account") from exc
        self.stdout.write("Exported local test workspace created.")
