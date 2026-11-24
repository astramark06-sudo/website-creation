"""Provision a workspace for an existing test user; no credentials in arguments."""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, IntegrityError

from scripts.creator_access import Role
from scripts.creator_relational import identifier, read_schema, require_text
from staging_auth.models import Workspace, Membership


class Command(BaseCommand):
    help = "Create a new local staging workspace and its first owner"

    def add_arguments(self, parser):
        parser.add_argument("--slug", required=True)
        parser.add_argument("--title", required=True)
        parser.add_argument("--schema", required=True)
        parser.add_argument("--owner", required=True, help="Existing local test-account username")

    def handle(self, *args, **options):
        try:
            slug = identifier(options["slug"])
            title = require_text(options["title"], "Workspace title", 120)
            schema = read_schema(options["schema"])
            with transaction.atomic():
                owner = get_user_model().objects.get(username=options["owner"], is_active=True)
                workspace = Workspace.objects.create(slug=slug, title=title, schema=schema)
                Membership.objects.create(workspace=workspace, user=owner, role=Role.OWNER.value)
        except (ValueError, OSError, IntegrityError, get_user_model().DoesNotExist) as exc:
            raise CommandError("Unable to provision workspace; check schema, slug and existing active owner") from exc
        self.stdout.write("Local test workspace created.")
