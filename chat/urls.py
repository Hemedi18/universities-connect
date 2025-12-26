from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    path('', views.inbox, name='inbox'),
    path('<int:conversation_id>/', views.chat_room, name='chat_room'),
    path('start/<int:user_id>/', views.start_chat, name='start_chat'),
    path('api/messages/<int:conversation_id>/', views.get_messages, name='get_messages'),
    path('typing/update/<int:conversation_id>/', views.update_typing_status, name='update_typing'),
    path('typing/check/<int:conversation_id>/', views.check_typing_status, name='check_typing'),
    path('api/unread/', views.get_total_unread, name='get_total_unread'),
]