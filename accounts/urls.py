from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    # path("register/", views.register_view, name="register"),
    path("login/", views.login_view, name="login"),
    path('auth/', views.auth_view, name='login_register'),
    path("logout/", views.logout_view, name="logout"),
]


