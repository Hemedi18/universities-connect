from django.urls import path
from . import views

app_name = "chat"

urlpatterns = [
    path("inbox/", views.inbox, name="inbox"),
    path("start/<int:user_id>/", views.start_chat, name="start_chat"),
    path("room/<int:conversation_id>/", views.chat_room, name="chat_room"),
    path(
        "room/<int:conversation_id>/messages/", views.get_messages, name="get_messages"
    ),
    path(
        "room/<int:conversation_id>/typing/",
        views.update_typing_status,
        name="update_typing",
    ),
    path(
        "room/<int:conversation_id>/check_typing/",
        views.check_typing_status,
        name="check_typing",
    ),
    path("deal/<int:deal_id>/sold/", views.deal_mark_sold, name="deal_mark_sold"),
    path(
        "deal/<int:deal_id>/not-sold/",
        views.deal_mark_not_sold,
        name="deal_mark_not_sold",
    ),
    path(
        "deal/<int:deal_id>/stock/",
        views.deal_update_stock,
        name="deal_update_stock",
    ),
    path(
        "deal/<int:deal_id>/rate/",
        views.deal_submit_rating,
        name="deal_submit_rating",
    ),
    path("total_unread/", views.get_total_unread, name="get_total_unread"),
    path("api/unread/", views.get_total_unread, name="api_unread"),
    path("<int:user_id>/", views.start_chat, name="chat_with_user"),
]
