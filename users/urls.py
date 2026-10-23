from django.urls import path
from . import views

app_name = "users"
urlpatterns = [
    path("", views.home, name="home"),
    path("edit/", views.edit_profile, name="edit_profile"),
    path("register/", views.register_user, name="register"),
    path("verify-otp/", views.verify_registration_otp, name="verify_otp"),
    path("resend-otp/", views.resend_registration_otp, name="resend_otp"),
    path("login/", views.login_user, name="login"),
    path("logout/", views.logout_user, name="logout"),
]
