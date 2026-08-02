from django.db import migrations


def forwards(apps, schema_editor):
    Item = apps.get_model("business", "Item")
    ItemMedia = apps.get_model("business", "ItemMedia")
    for item in Item.objects.all():
        if ItemMedia.objects.filter(item_id=item.id).exists():
            continue
        order = 0
        for field, mtype in (
            ("image", "image"),
            ("image2", "image"),
            ("image3", "image"),
            ("video", "video"),
        ):
            f = getattr(item, field, None)
            if not f:
                continue
            name = getattr(f, "name", "") or ""
            if not name:
                continue
            ItemMedia.objects.create(
                item_id=item.id,
                file=name,
                media_type=mtype,
                sort_order=order,
            )
            order += 1


def backwards(apps, schema_editor):
    ItemMedia = apps.get_model("business", "ItemMedia")
    ItemMedia.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("business", "0025_item_media_max6"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
