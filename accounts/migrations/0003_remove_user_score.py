# Generated by Django 5.2 on 2025-05-15 14:03

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_user_coin'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='user',
            name='score',
        ),
    ]
