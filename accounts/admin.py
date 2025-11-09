from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Account

# Register your models here.

class AccountAdmin(UserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'is_admin')
    search_fields = ('email', 'first_name')
    readonly_fields = ('date_joined', 'last_login')
    ordering = ('email',)


    filter_horizontal = ()
    list_filter    = ()
    fieldsets = ()

admin.site.register(Account, AccountAdmin)