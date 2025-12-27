from django.urls import path
from . import views 

app_name = 'business'

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('contact/', views.contact, name='contact'),
    path('documentation/', views.documentation, name='documentation'),
    path('sell/', views.post_item, name='post_item'),
    path('item/<int:item_id>/', views.item_detail, name='item_detail'),
    path('cart/', views.view_cart, name='view_cart'),
    path('cart/add/<int:item_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('manage/', views.manage_items, name='manage_items'),
    path('edit/<int:item_id>/', views.edit_item, name='edit_item'),
    path('delete/<int:item_id>/', views.delete_item, name='delete_item'),
    path('dashboard/', views.personal_dashboard, name='personal_dashboard'),
    path('company/dashboard/', views.company_dashboard, name='company_dashboard'),
    path('company/edit/', views.edit_company_profile, name='edit_company_profile'),
    path('company/<int:company_id>/', views.view_company_profile, name='view_company_profile'),
    path('company/follow/<int:company_id>/', views.toggle_follow_company, name='toggle_follow_company'),
    path('notifications/', views.notifications_view, name='user_notifications'),
    path('notifications/read/all/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    path('notifications/read/<int:notification_id>/', views.mark_notification_read, name='mark_notification_read'),
    path('company/<int:company_id>/review/', views.add_review, name='add_review'),
    path('review/edit/<int:review_id>/', views.edit_review, name='edit_review'),
    path('review/delete/<int:review_id>/', views.delete_review, name='delete_review'),
    path('company/<int:company_id>/report/', views.report_company, name='report_company'),
    path('item/pin/<int:item_id>/', views.toggle_pin_item, name='toggle_pin_item'),
]