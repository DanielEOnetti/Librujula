from django.urls import path
from . import views

urlpatterns = [
    # Cuando alguien entre a 'recomendar/', ejecuta la función recomendar_libros
    path('recomendar/', views.recomendar_libros),
]