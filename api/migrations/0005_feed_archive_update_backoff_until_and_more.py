# Generated by Django 4.2.3 on 2023-07-29 19:03

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0004_feedentry_api_feedent_publish_bdf95e_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="feed",
            name="archive_update_backoff_until",
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AddField(
            model_name="feedentry",
            name="is_archived",
            field=models.BooleanField(default=False),
        ),
        migrations.AddIndex(
            model_name="feedentry",
            index=models.Index(
                fields=["is_archived"], name="api_feedent_is_arch_6c1cc5_idx"
            ),
        ),
    ]
