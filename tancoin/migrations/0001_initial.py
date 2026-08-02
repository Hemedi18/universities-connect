# Generated manually for tancoin app

from decimal import Decimal

from django.db import migrations, models


def seed_default_rate(apps, schema_editor):
    ExchangeRate = apps.get_model("tancoin", "ExchangeRate")
    if not ExchangeRate.objects.exists():
        ExchangeRate.objects.create(
            fiat_currency_code="TZS",
            fiat_per_one_tan=Decimal("500"),
            notes="Default seed — change in Admin to match your market.",
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ExchangeRate",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "fiat_currency_code",
                    models.CharField(
                        default="TZS",
                        help_text="ISO-style code shown next to fiat estimates (e.g. TZS, USD).",
                        max_length=10,
                    ),
                ),
                (
                    "fiat_per_one_tan",
                    models.DecimalField(
                        decimal_places=6,
                        help_text="Example: if 1 TAN = 500 TZS, enter 500.",
                        max_digits=24,
                    ),
                ),
                ("notes", models.CharField(blank=True, max_length=255)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Exchange rate",
                "verbose_name_plural": "Exchange rates",
                "ordering": ["-updated_at"],
            },
        ),
        migrations.RunPython(seed_default_rate, noop_reverse),
    ]
