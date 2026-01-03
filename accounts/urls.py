from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    # path("register/", views.register_view, name="register"),
    path("login/", views.login_view, name="login"),
    path('auth/', views.auth_view, name='login_register'),
    path("logout/", views.logout_view, name="logout"),
    path("auth/reset/", views.password_reset_request, name="password_reset_request"),
    path("auth/reset/verify/", views.password_reset_verify, name="password_reset_verify"),
    path("auth/reset/set-password/", views.password_reset_set_password, name="password_reset_set_password"),

]


