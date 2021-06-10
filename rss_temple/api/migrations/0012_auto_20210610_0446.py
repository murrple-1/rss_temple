# Generated by Django 3.2.3 on 2021-06-10 04:46

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0011_auto_20210609_0430'),
    ]

    operations = [
        migrations.AddField(
            model_name='feed',
            name='update_backoff_until',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AddIndex(
            model_name='feed',
            index=models.Index(fields=['update_backoff_until'], name='api_feed_update__033cc4_idx'),
        ),
    ]
