# pylint: skip-file
# Generated by Django 3.2.10 on 2022-02-10 13:43

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('django_dialog_engine', '0011_dialogscript_labels'),
    ]

    operations = [
        migrations.AddField(
            model_name='dialogscript',
            name='embeddable',
            field=models.BooleanField(default=False),
        ),
    ]
