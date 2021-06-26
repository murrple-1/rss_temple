from django.db import migrations


def _forward_func_add_feed_entry_search_vector(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return

    with schema_editor.connection.cursor() as c:
        c.execute('''
            ALTER TABLE api_feed ADD COLUMN title_search_vector tsvector GENERATED ALWAYS AS (
                to_tsvector('english', title)
            ) STORED''')
        c.execute('''
            CREATE INDEX api_feed_title_search_vector_idx ON api_feed USING GIN (title_search_vector)''')
        c.execute('''
            ALTER TABLE api_feedentry ADD COLUMN title_search_vector tsvector GENERATED ALWAYS AS (
                to_tsvector('english', title)
            ) STORED''')
        c.execute('''
            CREATE INDEX api_feedentry_title_search_vector_idx ON api_feedentry USING GIN (title_search_vector)''')


def _reverse_func_add_feed_entry_search_vector(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return

    with schema_editor.connection.cursor() as c:
        c.execute('''
            DROP INDEX IF EXISTS api_feed_title_search_vector_idx''')
        c.execute('''
            ALTER TABLE api_feed DROP COLUMN IF EXISTS title_search_vector''')
        c.execute('''
            DROP INDEX IF EXISTS api_feedentry_title_search_vector_idx''')
        c.execute('''
            ALTER TABLE api_feedentry DROP COLUMN IF EXISTS title_search_vector''')


class Migration(migrations.Migration):
    dependencies = [
        ('api', '0013_postgres_search_vector'),
    ]

    operations = [
        migrations.RunPython(_forward_func_add_feed_entry_search_vector, _reverse_func_add_feed_entry_search_vector),
    ]
