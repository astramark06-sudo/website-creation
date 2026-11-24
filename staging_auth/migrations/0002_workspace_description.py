from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("staging_auth", "0001_initial")]
    operations = [
        migrations.AddField(model_name="workspace", name="description",
                            field=models.TextField(blank=True, default="", max_length=1000)),
    ]
