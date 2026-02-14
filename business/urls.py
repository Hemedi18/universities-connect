from django.urls import path
from . import views 
from company import views as company_views

app_name = 'business'

urlpatterns = [
    path('', views.home_redirect, name='home'),
    path('item/<int:item_id>/', views.item_detail_redirect, name='item_detail'),
    path('about/', views.about_redirect, name='about'),
    path('contact/', views.contact_redirect, name='contact'),
    path('documentation/', views.documentation_redirect, name='documentation'),
    path('cart/', views.view_cart_redirect, name='view_cart'),
    path('cart/add/<int:item_id>/', views.add_to_cart_redirect, name='add_to_cart'),
    path('cart/remove/<int:item_id>/', views.remove_from_cart_redirect, name='remove_from_cart'),
    path('company/<int:company_id>/', views.view_company_profile_redirect, name='view_company_profile'),
    path('company/edit/', company_views.edit_company_profile, name='edit_company_profile'),
    path('company/dashboard/', views.company_dashboard, name='company_dashboard'),
    path('sell/', views.post_item, name='post_item'),
    path('manage/', views.manage_items, name='manage_items'),
    path('edit/<int:item_id>/', views.edit_item, name='edit_item'),
    path('delete/<int:item_id>/', views.delete_item, name='delete_item'),
    path('dashboard/', views.personal_dashboard, name='personal_dashboard'), # For individual sellers
    path('notifications/', views.notifications_view, name='user_notifications'),
    path('notifications/read/all/', views.mark_all_notifications_read, name='mark_all_notifications_read'),
    path('notifications/read/<int:notification_id>/', views.mark_notification_read, name='mark_notification_read'),
    path('item/pin/<int:item_id>/', views.toggle_pin_item, name='toggle_pin_item'),
]