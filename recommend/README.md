"""
Recommendation runbook
======================

1. Ensure `recommend` is in INSTALLED_APPS, then:

       python manage.py migrate
       python manage.py rebuild_recommend_features

2. Verify APIs:

       GET  /api/recommendations?count=10
       POST /api/events   (JSON array of interaction events)

3. Stats:

       python manage.py recommend_stats

4. Auto-rebuild (default):
   When someone hits Hot picks / `/api/recommendations`, if features are older
   than `RECOMMEND_REBUILD_INTERVAL_SECONDS` (default 6 hours), a background
   thread rebuilds item/user features + similarities.

   Settings in `u_connect/settings.py`:

       RECOMMEND_REBUILD_ON_REQUEST = True
       RECOMMEND_REBUILD_INTERVAL_SECONDS = 6 * 60 * 60

   Set interval to `0` or `RECOMMEND_REBUILD_ON_REQUEST = False` to disable.
   Manual `rebuild_recommend_features` still works anytime.
"""
