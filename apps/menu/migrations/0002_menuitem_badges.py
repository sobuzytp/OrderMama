from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("menu", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="menuitem",
            name="is_popular",
            field=models.BooleanField(default=False),
        ),
        # পুরনো আইটেমে NULL থাকবে (তারা “নতুন” ব্যাজ পাবে না), নতুনগুলোতে অটো সময় বসবে
        migrations.AddField(
            model_name="menuitem",
            name="created_at",
            field=models.DateTimeField(auto_now_add=True, null=True, blank=True),
        ),
    ]
