# Generated by Django 3.2.3 on 2021-06-09 04:30

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0010_user_attributes"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="feedentry",
            unique_together=set(),
        ),
        migrations.AddConstraint(
            model_name="feedentry",
            constraint=models.UniqueConstraint(
                condition=models.Q(("updated_at__isnull", True)),
                fields=("feed", "url"),
                name="unique__feed__url__when__updated_at__null",
            ),
        ),
        migrations.AddConstraint(
            model_name="feedentry",
            constraint=models.UniqueConstraint(
                fields=("feed", "url", "updated_at"),
                name="unique__feed__url__when__updated_at__not_null",
            ),
        ),
    ]
