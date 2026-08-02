from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Count, Max
from django.utils import timezone

from recommend.models import InteractionEvent, ItemFeature, ItemSimilarity, UserFeature
from recommend.schedule import (
    features_are_stale,
    last_rebuild_at,
    rebuild_interval_seconds,
)


class Command(BaseCommand):
    help = "Print recommendation pipeline stats (events, features, freshness)."

    def handle(self, *args, **options):
        now = timezone.now()
        total_events = InteractionEvent.objects.count()
        by_type = {
            row["event_type"]: row["c"]
            for row in InteractionEvent.objects.values("event_type").annotate(
                c=Count("id")
            )
        }
        latest_event = InteractionEvent.objects.aggregate(m=Max("timestamp"))["m"]
        item_feats = ItemFeature.objects.count()
        user_feats = UserFeature.objects.count()
        sims = ItemSimilarity.objects.count()
        latest_item_feat = ItemFeature.objects.aggregate(m=Max("updated_at"))["m"]
        last_rebuild = last_rebuild_at()
        interval = rebuild_interval_seconds()
        stale = features_are_stale()
        auto = getattr(settings, "RECOMMEND_REBUILD_ON_REQUEST", True)

        self.stdout.write(f"Now: {now.isoformat()}")
        self.stdout.write(f"Events: {total_events}  by_type={by_type}")
        self.stdout.write(f"Latest event: {latest_event}")
        self.stdout.write(f"ItemFeature rows: {item_feats}  latest={latest_item_feat}")
        self.stdout.write(f"UserFeature rows: {user_feats}")
        self.stdout.write(f"ItemSimilarity rows: {sims}")
        self.stdout.write(f"Last rebuild: {last_rebuild}")
        self.stdout.write(
            f"Auto-rebuild: {auto}  interval={interval}s  stale={stale}"
        )
        self.stdout.write(
            "Manual rebuild: python manage.py rebuild_recommend_features"
        )
