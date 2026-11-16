"""Django Admin：商品中心应急维护入口，前台业务不依赖。"""

from django.contrib import admin

from apps.catalog.models import Category, Product, ProductImage, Sku, StockLog


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0


class SkuInline(admin.TabularInline):
    model = Sku
    extra = 0
    fields = ("sku_code", "spec_text", "sale_price", "stock", "locked_stock", "status")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "level", "sort_weight", "is_deleted")
    list_filter = ("level", "is_deleted")
    search_fields = ("name", "public_id")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "status", "price_min", "price_max", "sales_count")
    list_filter = ("status", "category")
    search_fields = ("name", "public_id")
    inlines = [ProductImageInline, SkuInline]
    readonly_fields = ("public_id", "created_at", "updated_at")


@admin.register(StockLog)
class StockLogAdmin(admin.ModelAdmin):
    list_display = ("sku", "change", "stock_before", "stock_after", "operator", "created_at")
    search_fields = ("sku__sku_code", "sku__product__name")
    list_filter = ("created_at",)
    readonly_fields = (
        "sku",
        "operator",
        "change",
        "stock_before",
        "stock_after",
        "reason",
        "created_at",
    )
