from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="Workspace",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("slug", models.SlugField(max_length=32, unique=True)),
                ("title", models.CharField(max_length=120)),
                ("schema", models.JSONField()),
            ],
        ),
        migrations.CreateModel(
            name="Membership",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("role", models.CharField(choices=[("viewer", "viewer"), ("editor", "editor"), ("owner", "owner")], max_length=12)),
                ("active", models.BooleanField(default=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ("workspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="staging_auth.workspace")),
            ],
            options={"constraints": [models.UniqueConstraint(fields=("workspace", "user"), name="staging_one_membership")]},
        ),
        migrations.CreateModel(
            name="Record",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("table_id", models.CharField(max_length=32)),
                ("data", models.JSONField()),
                ("workspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="staging_auth.workspace")),
            ],
            options={"indexes": [models.Index(fields=["workspace", "table_id", "id"], name="staging_record_scope")]},
        ),
        migrations.CreateModel(
            name="MembershipEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("actor_id", models.PositiveBigIntegerField()),
                ("target_id", models.PositiveBigIntegerField()),
                ("role", models.CharField(max_length=12)),
                ("active", models.BooleanField()),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("workspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="staging_auth.workspace")),
            ],
        ),
    ]
