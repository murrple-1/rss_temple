# Generated by Django 3.1.7 on 2021-03-31 04:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0003_auto_20210114_0439'),
    ]

    operations = [
        migrations.AlterField(
            model_name='feedentry',
            name='content',
            field=models.TextField(),
        ),
        migrations.AlterField(
            model_name='feedentry',
            name='title',
            field=models.TextField(),
        ),
        migrations.AlterField(
            model_name='feedentry',
            name='url',
            field=models.TextField(),
        ),
    ]
