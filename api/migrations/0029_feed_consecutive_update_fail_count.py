# Generated by Django 5.0.2 on 2024-03-19 20:24

from django.db import migrations, models
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps
from django.db.models.functions import Now


def _forward_func_reset_feed_update_backoff_until(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
):
    Feed = apps.get_model("api", "Feed")

    Feed.objects.update(update_backoff_until=Now())


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0028_alter_user_attributes"),
    ]

    operations = [
        migrations.AddField(
            model_name="feed",
            name="consecutive_update_fail_count",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.RunPython(
            _forward_func_reset_feed_update_backoff_until, migrations.RunPython.noop
        ),
    ]
