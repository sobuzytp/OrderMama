from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("subscriptions", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="plan",
            name="code",
            field=models.SlugField(max_length=20, unique=True),
        ),
        migrations.AddField(
            model_name="plan",
            name="grace_days",
            field=models.PositiveIntegerField(default=3),
        ),
    ]
