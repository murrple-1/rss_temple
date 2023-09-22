# Generated by Django 4.2.5 on 2023-09-22 19:00

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0012_alter_token_options"),
    ]

    operations = [
        migrations.AddField(
            model_name="feedentry",
            name="has_top_image_been_processed",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="feedentry",
            name="top_image_src",
            field=models.TextField(default=""),
        ),
        migrations.AddIndex(
            model_name="feedentry",
            index=models.Index(
                fields=["has_top_image_been_processed"],
                name="api_feedent_has_top_022e54_idx",
            ),
        ),
    ]
