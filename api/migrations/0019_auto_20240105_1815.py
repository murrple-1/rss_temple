# Generated by Django 5.0 on 2024-01-05 18:15

import uuid

from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def _forward_func_update_classifier_labels(
    apps: StateApps, schema_editor: BaseDatabaseSchemaEditor
):
    FeedEntry = apps.get_model("api", "FeedEntry")
    entry_uuids_to_delete: list[uuid.UUID] = []
    entries_seen: set[tuple[str, uuid.UUID]] = set()
    for uuid_, id_, feed_id in FeedEntry.objects.filter(id__isnull=False).values_list(
        "uuid", "id", "feed_id"
    ):
        t: tuple[str, uuid.UUID] = (id_, feed_id)
        if t in entries_seen:
            entry_uuids_to_delete.append(uuid_)
        else:
            entries_seen.add(t)

    FeedEntry.objects.filter(uuid__in=entry_uuids_to_delete).delete()


class Migration(migrations.Migration):
    dependencies = [
        (
            "api",
            "0018_auto_20231106_0059",
        ),
    ]

    operations = [
        migrations.RunPython(
            _forward_func_update_classifier_labels,
            migrations.RunPython.noop,
        ),
    ]
