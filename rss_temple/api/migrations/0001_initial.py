# Generated by Django 2.1.3 on 2018-11-08 01:13

from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='FavoriteFeedEntryUserMapping',
            fields=[
                ('uuid', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
            ],
        ),
        migrations.CreateModel(
            name='Feed',
            fields=[
                ('uuid', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('feed_url', models.TextField(unique=True)),
                ('title', models.TextField(null=True)),
                ('home_url', models.TextField(null=True)),
                ('published_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(null=True)),
                ('db_created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('db_updated_at', models.DateTimeField(null=True)),
            ],
        ),
        migrations.CreateModel(
            name='FeedEntry',
            fields=[
                ('uuid', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('id', models.TextField(null=True)),
                ('created_at', models.DateTimeField(null=True)),
                ('published_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(null=True)),
                ('title', models.TextField(null=True)),
                ('url', models.TextField(null=True)),
                ('content', models.TextField(null=True)),
                ('author_name', models.TextField(null=True)),
                ('hash', models.IntegerField()),
                ('db_created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('db_updated_at', models.DateTimeField(null=True)),
                ('feed', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='api.Feed')),
            ],
        ),
        migrations.CreateModel(
            name='FeedEntryTagMapping',
            fields=[
                ('uuid', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('feed_entry', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='api.FeedEntry')),
            ],
        ),
        migrations.CreateModel(
            name='FeedTagMapping',
            fields=[
                ('uuid', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('feed', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='api.Feed')),
            ],
        ),
        migrations.CreateModel(
            name='Login',
            fields=[
                ('uuid', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
            ],
        ),
        migrations.CreateModel(
            name='ReadFeedEntryUserMapping',
            fields=[
                ('uuid', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('read_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('feed_entry', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='api.FeedEntry')),
            ],
        ),
        migrations.CreateModel(
            name='Session',
            fields=[
                ('uuid', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('expires_at', models.DateTimeField(null=True)),
            ],
        ),
        migrations.CreateModel(
            name='SubscribedFeedUserMapping',
            fields=[
                ('uuid', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('feed', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='api.Feed')),
            ],
        ),
        migrations.CreateModel(
            name='Tag',
            fields=[
                ('uuid', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('label_text', models.TextField(unique=True)),
            ],
        ),
        migrations.CreateModel(
            name='User',
            fields=[
                ('uuid', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('email', models.CharField(max_length=64, unique=True)),
            ],
        ),
        migrations.CreateModel(
            name='UserCategory',
            fields=[
                ('uuid', models.UUIDField(default=uuid.uuid4, primary_key=True, serialize=False)),
                ('text', models.TextField(unique=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='api.User')),
            ],
        ),
        migrations.CreateModel(
            name='FacebookLogin',
            fields=[
                ('login_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='api.Login')),
                ('profile_id', models.CharField(max_length=96)),
            ],
            bases=('api.login',),
        ),
        migrations.CreateModel(
            name='GoogleLogin',
            fields=[
                ('login_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='api.Login')),
                ('g_user_id', models.CharField(max_length=96)),
            ],
            bases=('api.login',),
        ),
        migrations.CreateModel(
            name='MyLogin',
            fields=[
                ('login_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='api.Login')),
                ('pw_hash', models.CharField(max_length=96)),
            ],
            bases=('api.login',),
        ),
        migrations.AddField(
            model_name='subscribedfeedusermapping',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='api.User'),
        ),
        migrations.AddField(
            model_name='subscribedfeedusermapping',
            name='user_category',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='api.UserCategory'),
        ),
        migrations.AddField(
            model_name='session',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='api.User'),
        ),
        migrations.AddField(
            model_name='readfeedentryusermapping',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='api.User'),
        ),
        migrations.AddField(
            model_name='login',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='api.User'),
        ),
        migrations.AddField(
            model_name='feedtagmapping',
            name='tag',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='api.Tag'),
        ),
        migrations.AddField(
            model_name='feedentrytagmapping',
            name='tag',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='api.Tag'),
        ),
        migrations.AddField(
            model_name='favoritefeedentryusermapping',
            name='feed_entry',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='api.FeedEntry'),
        ),
        migrations.AddField(
            model_name='favoritefeedentryusermapping',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='api.User'),
        ),
        migrations.AlterUniqueTogether(
            name='subscribedfeedusermapping',
            unique_together={('feed', 'user')},
        ),
        migrations.AlterUniqueTogether(
            name='readfeedentryusermapping',
            unique_together={('feed_entry', 'user')},
        ),
        migrations.AlterUniqueTogether(
            name='feedtagmapping',
            unique_together={('feed', 'tag')},
        ),
        migrations.AlterUniqueTogether(
            name='feedentrytagmapping',
            unique_together={('feed_entry', 'tag')},
        ),
        migrations.AddIndex(
            model_name='feedentry',
            index=models.Index(fields=['id'], name='api_feedent_id_6f9c14_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='favoritefeedentryusermapping',
            unique_together={('feed_entry', 'user')},
        ),
    ]
