# Generated by Django 5.0.3 on 2024-06-01 17:41

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0034_alter_feed_home_url_alter_feedentry_author_name"),
    ]

    operations = [
        migrations.AlterField(
            model_name="feed",
            name="home_url",
            field=models.URLField(
                help_text="Cannot be edited with UI due to ambiguity between empty string and NULL",
                max_length=2048,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="feedentry",
            name="author_name",
            field=models.CharField(
                help_text="Cannot be edited with UI due to ambiguity between empty string and NULL",
                max_length=1024,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="feedentry",
            name="id",
            field=models.CharField(
                help_text="Cannot be edited with UI due to ambiguity between empty string and NULL",
                max_length=2048,
                null=True,
            ),
        ),
    ]
