# Generated by Django 3.1.1 on 2020-09-24 05:11

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="NotifyEmailQueueEntry",
            fields=[
                (
                    "uuid",
                    models.UUIDField(
                        default=uuid.uuid4, primary_key=True, serialize=False
                    ),
                ),
                ("subject", models.CharField(max_length=256)),
                ("plain_text", models.TextField(null=True)),
                ("html_text", models.TextField(null=True)),
            ],
        ),
        migrations.CreateModel(
            name="NotifyEmailQueueEntryRecipient",
            fields=[
                (
                    "uuid",
                    models.UUIDField(
                        default=uuid.uuid4, primary_key=True, serialize=False
                    ),
                ),
                (
                    "type",
                    models.IntegerField(choices=[(0, "To"), (1, "CC"), (2, "BCC")]),
                ),
                ("email", models.CharField(max_length=256)),
                (
                    "entry",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="api.notifyemailqueueentry",
                    ),
                ),
            ],
        ),
    ]
