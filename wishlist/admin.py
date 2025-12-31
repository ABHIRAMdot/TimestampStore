from django.contrib import admin
from .models import Wishlist, WishlistItem

# Register your models here.


class WishlistItemInline(admin.TabularInline):
    model = WishlistItem
    extra = 0
    readonly_fields = ("created_at",)
    fields = ("product", "variant", "created_at")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ("user", "get_item_count", "created_at", "updated_at")
    list_filter = ("created_at", "updated_at")
    search_fields = ("user__email", "user__first_name", "user__last_name")
    readonly_fields = ("created_at", "updated_at")
    inlines = [WishlistItemInline]

    def get_item_count(self, obj):
        return obj.get_item_count()

    get_item_count.short_description = "Items Count"

    def has_add_permission(self, request):
        return False


@admin.register(WishlistItem)
class WishlistItemAdmin(admin.ModelAdmin):
    list_display = ("wishlist", "product", "variant", "is_in_stock", "created_at")
    list_filter = ("created_at", "product__category")
    search_fields = (
        "wishlist__user__email",
        "product__product_name",
        "variant__colour",
    )
    readonly_fields = ("created_at",)

    def is_in_stock(self, obj):
        return obj.is_in_stock()

    is_in_stock.boolean = True
    is_in_stock.short_description = "In Stock"
