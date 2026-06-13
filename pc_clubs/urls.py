from django.urls import path
from . import views

app_name = 'pc_clubs'

urlpatterns = [
    path('', views.pc_club_list, name='list'),
    path('category/<slug:category_slug>/', views.pc_club_list, name='list_by_category'),
    path('<int:pk>/', views.pc_club_detail, name='detail'),
    path('<int:pk>/book/', views.pc_club_book, name='book'),
    path('booking/<int:booking_id>/status/', views.pc_booking_change_status, name='booking_change_status'),
]
