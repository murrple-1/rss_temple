# Generated by Django 5.0.2 on 2024-03-23 20:00

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0029_feed_consecutive_update_fail_count"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="feed",
            name="consecutive_update_fail_count",
        ),
    ]
