from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [("payments", "0001_initial")]

    operations = [
        migrations.AddField(model_name="payment", name="method", field=models.CharField(blank=True, choices=[("bkash", "bKash"), ("nagad", "Nagad"), ("rocket", "Rocket")], max_length=12)),
        migrations.AddField(model_name="payment", name="sender_number", field=models.CharField(blank=True, max_length=20)),
        migrations.AddField(model_name="payment", name="trx_id", field=models.CharField(blank=True, max_length=100, null=True, unique=True)),
        migrations.AddField(model_name="payment", name="rejection_reason", field=models.CharField(blank=True, max_length=500)),
        migrations.AddField(model_name="payment", name="reviewed_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AlterField(model_name="payment", name="status", field=models.CharField(choices=[("pending", "অপেক্ষমাণ"), ("submitted", "জমা দেওয়া হয়েছে"), ("approved", "অনুমোদিত"), ("rejected", "প্রত্যাখ্যাত"), ("paid", "সফল"), ("failed", "ব্যর্থ"), ("cancelled", "বাতিল")], default="pending", max_length=12)),
        migrations.AddConstraint(model_name="payment", constraint=models.UniqueConstraint(condition=Q(status="submitted"), fields=("restaurant",), name="one_submitted_payment_per_restaurant")),
    ]
