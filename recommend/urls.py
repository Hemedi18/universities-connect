from django.urls import path

from . import views

app_name = "recommend"

urlpatterns = [
    path("api/events", views.api_events, name="api_events"),
    path("api/recommendations", views.api_recommendations, name="api_recommendations"),
]
