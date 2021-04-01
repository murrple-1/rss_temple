# Generated by Django 3.1.7 on 2021-04-01 05:02

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0005_auto_20210331_1716'),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name='feedentry',
            name='api_feedent_hash_5fbffa_idx',
        ),
        migrations.AlterUniqueTogether(
            name='feedentry',
            unique_together={('feed', 'url', 'updated_at')},
        ),
        migrations.RemoveField(
            model_name='feedentry',
            name='hash',
        ),
    ]
