from django.db import migrations


def _forward_func_deduplication_feed_entries(apps, schema_editor):
    FeedEntry = apps.get_model('api', 'FeedEntry')

    unique_set = set()
    delete_list = []

    for feed_entry in FeedEntry.objects.all():
        unique_desc = (feed_entry.feed_id, feed_entry.url,
                       feed_entry.updated_at)

        if unique_desc in unique_set:
            delete_list.append(feed_entry)
        else:
            unique_set.add(unique_desc)

    for feed_entry in delete_list:
        feed_entry.delete()


class Migration(migrations.Migration):
    dependencies = [
        ('api', '0005_auto_20210331_1716'),
    ]

    operations = [
        migrations.RunPython(_forward_func_deduplication_feed_entries),
    ]
