# Generated by Django 5.2 on 2025-05-18 13:12

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0006_gamehistory'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='player',
            options={'verbose_name': 'Player', 'verbose_name_plural': 'Players'},
        ),
    ]
