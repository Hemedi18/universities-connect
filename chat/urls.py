from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    path('inbox/', views.inbox, name='inbox'),
    path('start/<int:user_id>/', views.start_chat, name='start_chat'),
    path('room/<int:conversation_id>/', views.chat_room, name='chat_room'),
    path('room/<int:conversation_id>/messages/', views.get_messages, name='get_messages'),
    path('room/<int:conversation_id>/typing/', views.update_typing_status, name='update_typing'),
    path('room/<int:conversation_id>/check_typing/', views.check_typing_status, name='check_typing'),
    path('total_unread/', views.get_total_unread, name='get_total_unread'),
    path('<int:user_id>/', views.start_chat, name='chat_with_user'),
]