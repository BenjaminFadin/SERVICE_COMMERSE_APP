from django.urls import path
from . import views

app_name = "services"

urlpatterns = [
    path("home/", views.home, name="home"),
    
    
]

