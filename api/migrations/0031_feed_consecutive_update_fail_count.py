# Generated by Django 5.0.3 on 2024-03-23 20:25

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0030_remove_feed_consecutive_update_fail_count"),
    ]

    operations = [
        migrations.AddField(
            model_name="feed",
            name="consecutive_update_fail_count",
            field=models.PositiveSmallIntegerField(default=0),
        ),
    ]
