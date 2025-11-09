from django.urls import path
from . import views

urlpatterns = [
    # Offer URLs
    path('', views.offer_list, name='offer_list'),
    path('add/', views.add_offer, name='add_offer'),
    path('edit/<int:offer_id>/', views.edit_offer, name='edit_offer'),
    path('delete/<int:offer_id>/', views.delete_offer, name='delete_offer'),
]