from django.urls import path
from . import views

app_name = "company"

urlpatterns = [
    path("register/", views.register_company, name="register"),
    path("dashboard/", views.company_dashboard, name="dashboard"),
    path("edit/", views.edit_company_profile, name="edit_profile"),
    path("<int:company_id>/", views.view_company_profile, name="profile"),
    path("follow/<int:company_id>/", views.toggle_follow_company, name="toggle_follow"),
    path("<int:company_id>/review/", views.add_review, name="add_review"),
    path("review/edit/<int:review_id>/", views.edit_review, name="edit_review"),
    path("review/delete/<int:review_id>/", views.delete_review, name="delete_review"),
    path("<int:company_id>/report/", views.report_company, name="report"),
    path("ajax/load-districts/", views.load_districts, name="ajax_load_districts"),
]
