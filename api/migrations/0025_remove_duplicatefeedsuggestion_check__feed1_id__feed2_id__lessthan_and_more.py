# Generated by Django 5.0.1 on 2024-02-06 20:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("api", "0024_alternatefeedurl_idx__alter___feed_url__upper_and_more"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="duplicatefeedsuggestion",
            name="check__feed1_id__feed2_id__lessthan",
        ),
        migrations.RemoveConstraint(
            model_name="duplicatefeedsuggestion",
            name="unique__feed1__feed2",
        ),
        migrations.RemoveConstraint(
            model_name="subscribedfeedusermapping",
            name="unique__user__feed",
        ),
        migrations.RenameIndex(
            model_name="alternatefeedurl",
            new_name="alter...__idx__feed_url__upper",
            old_name="idx__alter...__feed_url__upper",
        ),
        migrations.RenameIndex(
            model_name="feed",
            new_name="feed__idx__feed_url__upper",
            old_name="idx__feed__feed_url__upper",
        ),
        migrations.AddConstraint(
            model_name="duplicatefeedsuggestion",
            constraint=models.CheckConstraint(
                check=models.Q(("feed1_id__lt", models.F("feed2_id")), _negated=True),
                name="duplicatefeedsuggestion__check__feed1_id__feed2_id__lessthan",
            ),
        ),
        migrations.AddConstraint(
            model_name="duplicatefeedsuggestion",
            constraint=models.UniqueConstraint(
                fields=("feed1", "feed2"),
                name="duplicatefeedsuggestion__unique__feed1__feed2",
            ),
        ),
        migrations.AddConstraint(
            model_name="subscribedfeedusermapping",
            constraint=models.UniqueConstraint(
                fields=("user", "feed"),
                name="subscribedfeedusermapping__unique__user__feed",
            ),
        ),
    ]