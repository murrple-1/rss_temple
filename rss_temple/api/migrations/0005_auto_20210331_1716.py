# Generated by Django 3.1.7 on 2021-03-31 17:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0004_auto_20210331_0442'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='feedentry',
            index=models.Index(fields=['url'], name='api_feedent_url_a60cf6_idx'),
        ),
    ]