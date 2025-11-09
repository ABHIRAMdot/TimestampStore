from django.urls import path
from . import views
from products.views import toggle_product_status

urlpatterns = [
    path('admin-login/', views.admin_login, name='admin_login'),
    path('admin-dashboard',views.admin_dashboard,name='admin_dashboard'),
    path('users-list',views.user_list,name='user_list'),
    path('users-list/toggle-user-status/<int:user_id>/',views.toggle_user_status,name='toggle_user_status'),
    path('admin-logout',views.admin_logout,name='admin_logout',),


    path('products/toggle-product-status/<int:product_id>/',toggle_product_status, name='toggle_product_status'),


]
