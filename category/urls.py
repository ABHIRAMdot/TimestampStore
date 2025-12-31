from django.urls import path
from . import views  # make sure this import is correct

urlpatterns = [
    path("", views.category_list, name="category_list"),
    path("add/", views.add_category, name="add_category"),
    path("edit/<int:category_id>/", views.edit_category, name="edit_category"),
    path(
        "toggle-status/<int:category_id>/",
        views.toggle_category_status,
        name="toggle_category_status",
    ),
]
