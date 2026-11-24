"""Persistent memberships and workspace-scoped schema-aware records."""
from django.conf import settings
from django.db import models

from scripts.creator_access import Role


class Workspace(models.Model):
    slug = models.SlugField(max_length=32, unique=True)
    title = models.CharField(max_length=120)
    schema = models.JSONField()


class Membership(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=12, choices=[(role.value, role.value) for role in Role])
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["workspace", "user"], name="staging_one_membership"),
        ]


class Record(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE)
    table_id = models.CharField(max_length=32)
    data = models.JSONField()

    class Meta:
        indexes = [models.Index(fields=["workspace", "table_id", "id"], name="staging_record_scope")]


class MembershipEvent(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE)
    actor_id = models.PositiveBigIntegerField()
    target_id = models.PositiveBigIntegerField()
    role = models.CharField(max_length=12)
    active = models.BooleanField()
    created = models.DateTimeField(auto_now_add=True)
