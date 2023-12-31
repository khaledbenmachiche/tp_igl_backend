# Generated by Django 5.0 on 2023-12-24 21:03

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Articles', '0003_remove_uploadedarticle_created_at_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='uploadedarticle',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='uploadedarticle',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
    ]