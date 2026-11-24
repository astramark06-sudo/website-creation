from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("staging_auth", "0002_workspace_description")]
    operations = [
        migrations.CreateModel(
            name="LoginBudget",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("window_start", models.PositiveBigIntegerField()),
                ("attempts", models.PositiveIntegerField()),
            ],
            options={"constraints": [
                models.CheckConstraint(condition=models.Q(id=1), name="staging_single_login_budget"),
                models.CheckConstraint(condition=models.Q(attempts__lte=10), name="staging_login_budget_bound"),
            ]},
        ),
    ]
