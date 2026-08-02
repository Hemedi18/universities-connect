from django.core.management.base import BaseCommand

from recommend.features import rebuild_all_features
from recommend.schedule import mark_rebuild_complete


class Command(BaseCommand):
    help = "Rebuild recommend feature store (item/user features + item similarities)."

    def handle(self, *args, **options):
        self.stdout.write("Rebuilding recommendation features...")
        stats = rebuild_all_features()
        mark_rebuild_complete()
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. items={stats['items']} users={stats['users']} "
                f"similarities={stats['similarities']}"
            )
        )
