from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Avg, Count
from django.utils import timezone
from .models import (
    Category, Product, ProductImage,
    Coupon, Order, OrderItem,
    Review, SiteSettings, FlashSale, SupportMessage
)


# ─────────────────────────────────────────────
#  SITE SETTINGS
# ─────────────────────────────────────────────

@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ('🌐 Site Info', {
            'fields': ('site_name', 'tagline', 'meta_description', 'meta_keywords', 'og_image')
        }),
        ('📱 Contact', {
            'fields': ('whatsapp_number', 'bkash_number', 'nagad_number')
        }),
        ('🚚 Delivery', {
            'fields': ('delivery_charge', 'free_delivery_above')
        }),
        ('🤖 AI Chat', {
            'fields': ('chat_enabled', 'chat_welcome_msg')
        }),
    )

    def has_add_permission(self, request):
        # Only one settings instance allowed
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


# ─────────────────────────────────────────────
#  CATEGORY
# ─────────────────────────────────────────────

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display  = ['icon', 'name', 'slug', 'product_count', 'order']
    list_editable = ['order']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name']

    def product_count(self, obj):
        count = obj.products.count()
        return format_html('<b style="color:#5b7fff">{}</b>', count)
    product_count.short_description = 'Products'


# ─────────────────────────────────────────────
#  PRODUCT
# ─────────────────────────────────────────────

class ProductImageInline(admin.TabularInline):
    model  = ProductImage
    extra  = 3
    fields = ['image', 'alt', 'order']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display    = ['thumbnail', 'name', 'level', 'category', 'price_display',
                       'stock_display', 'featured', 'is_on_sale_display', 'view_count', 'created_at']
    list_filter     = ['level', 'category', 'featured']
    search_fields   = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    list_editable   = ['featured']
    readonly_fields = ['view_count', 'created_at', 'updated_at', 'current_price_display']
    inlines         = [ProductImageInline]

    fieldsets = (
        ('📦 Basic Info', {
            'fields': ('name', 'slug', 'level', 'category', 'description', 'image')
        }),
        ('💰 Pricing & Stock', {
            'fields': ('price', 'stock', 'featured', 'current_price_display')
        }),
        ('🔥 Flash Sale', {
            'fields': ('sale_price', 'sale_starts_at', 'sale_ends_at'),
            'classes': ('collapse',),
        }),
        ('🔍 SEO', {
            'fields': ('meta_title', 'meta_description'),
            'classes': ('collapse',),
        }),
        ('📊 Analytics', {
            'fields': ('view_count', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def thumbnail(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="width:50px;height:50px;object-fit:cover;border-radius:8px;">', obj.image.url)
        return '—'
    thumbnail.short_description = ''

    def price_display(self, obj):
        if obj.is_on_sale:
            return format_html(
                '<span style="text-decoration:line-through;color:#888">৳{}</span> '
                '<b style="color:#00ff87">৳{}</b>',
                obj.price, obj.sale_price
            )
        return format_html('<b>৳{}</b>', obj.price)
    price_display.short_description = 'Price'

    def stock_display(self, obj):
        if obj.stock == 0:
            return format_html('<span style="color:#ff006e;font-weight:700">Out of Stock</span>')
        elif obj.stock <= 5:
            return format_html('<span style="color:#f59e0b;font-weight:700">⚠️ {}</span>', obj.stock)
        return format_html('<span style="color:#00ff87;font-weight:700">{}</span>', obj.stock)
    stock_display.short_description = 'Stock'

    def is_on_sale_display(self, obj):
        if obj.is_on_sale:
            return format_html('<span style="color:#00ff87">🔥 {}% OFF</span>', obj.discount_percent)
        return '—'
    is_on_sale_display.short_description = 'Sale'

    def current_price_display(self, obj):
        return f"৳{obj.current_price}"
    current_price_display.short_description = 'Current Price'


# ─────────────────────────────────────────────
#  COUPON
# ─────────────────────────────────────────────

@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display  = ['code', 'discount_type', 'discount_value', 'min_order',
                     'used_count', 'max_uses', 'active', 'expires_at', 'status_display']
    list_filter   = ['discount_type', 'active']
    search_fields = ['code']
    list_editable = ['active']
    readonly_fields = ['used_count', 'created_at']

    def status_display(self, obj):
        valid, msg = obj.is_valid()
        if valid:
            return format_html('<span style="color:#00ff87;font-weight:700">✅ Valid</span>')
        return format_html('<span style="color:#ff006e;font-weight:700">❌ {}</span>', msg)
    status_display.short_description = 'Status'


# ─────────────────────────────────────────────
#  ORDER
# ─────────────────────────────────────────────

class OrderItemInline(admin.TabularInline):
    model         = OrderItem
    extra         = 0
    readonly_fields = ['name', 'product', 'quantity', 'price', 'subtotal']
    can_delete    = False

    def subtotal(self, obj):
        return f"৳{obj.subtotal:.0f}"
    subtotal.short_description = 'Subtotal'


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display    = ['id', 'customer_name', 'phone', 'total_display',
                       'payment_method', 'status_badge', 'created_at']
    list_filter     = ['status', 'payment_method', 'created_at']
    search_fields   = ['customer_name', 'phone', 'id']
    readonly_fields = ['created_at', 'updated_at', 'grand_total']
  
    inlines         = [OrderItemInline]
    date_hierarchy  = 'created_at'

    fieldsets = (
        ('👤 Customer', {
            'fields': ('user', 'customer_name', 'phone', 'address')
        }),
        ('💰 Payment', {
            'fields': ('total_amount', 'discount', 'delivery_charge',
                       'coupon', 'payment_method', 'payment_ref')
        }),
        ('📦 Status', {
            'fields': ('status', 'tracking_note')
        }),
        ('📅 Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def total_display(self, obj):
        return format_html('<b style="color:#00ff87">৳{:.0f}</b>', obj.total_amount)
    total_display.short_description = 'Total'

    def status_badge(self, obj):
        colors = {
            'pending':    '#f59e0b',
            'confirmed':  '#5b7fff',
            'processing': '#a78bfa',
            'dispatched': '#00e5b0',
            'delivered':  '#00ff87',
            'cancelled':  '#ff006e',
        }
        color = colors.get(obj.status, '#888')
        return format_html(
            '<span style="background:{};color:white;padding:3px 10px;border-radius:20px;font-size:0.75rem;font-weight:700">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'


# ─────────────────────────────────────────────
#  REVIEW
# ─────────────────────────────────────────────

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display  = ['name', 'product', 'stars_display', 'approved', 'created_at']
    list_filter   = ['approved', 'rating']
    search_fields = ['name', 'comment', 'product__name']
    list_editable = ['approved']
    readonly_fields = ['created_at']
    actions       = ['approve_selected', 'unapprove_selected']

    def stars_display(self, obj):
        stars = '⭐' * obj.rating
        return format_html('<span title="{}/5">{}</span>', obj.rating, stars)
    stars_display.short_description = 'Rating'

    def approve_selected(self, request, queryset):
        queryset.update(approved=True)
        self.message_user(request, f'{queryset.count()} reviews approved.')
    approve_selected.short_description = '✅ Approve selected reviews'

    def unapprove_selected(self, request, queryset):
        queryset.update(approved=False)
        self.message_user(request, f'{queryset.count()} reviews unapproved.')
    unapprove_selected.short_description = '❌ Unapprove selected reviews'


# ─────────────────────────────────────────────
#  FLASH SALE
# ─────────────────────────────────────────────

@admin.register(FlashSale)
class FlashSaleAdmin(admin.ModelAdmin):
    list_display  = ['title', 'ends_at', 'is_active', 'live_status', 'created_at']
    list_editable = ['is_active']
    readonly_fields = ['created_at', 'seconds_remaining']

    def live_status(self, obj):
        if obj.is_live:
            remaining = obj.seconds_remaining
            hours = remaining // 3600
            mins  = (remaining % 3600) // 60
            return format_html(
                '<span style="color:#00ff87;font-weight:700">🔴 LIVE — {}h {}m left</span>',
                hours, mins
            )
        return format_html('<span style="color:#888">Ended</span>')
    live_status.short_description = 'Status'


# ─────────────────────────────────────────────
#  SUPPORT MESSAGES (AI Chat Logs)
# ─────────────────────────────────────────────

@admin.register(SupportMessage)
class SupportMessageAdmin(admin.ModelAdmin):
    list_display  = ['short_question', 'short_answer', 'source', 'user', 'created_at']
    list_filter   = ['source', 'created_at']
    search_fields = ['question', 'answer']
    readonly_fields = ['session_key', 'user', 'question', 'answer', 'source', 'created_at']

    def short_question(self, obj):
        return obj.question[:60] + '...' if len(obj.question) > 60 else obj.question
    short_question.short_description = 'Question'

    def short_answer(self, obj):
        return obj.answer[:60] + '...' if len(obj.answer) > 60 else obj.answer
    short_answer.short_description = 'Answer'

    def has_add_permission(self, request):
        return False


# ─────────────────────────────────────────────
#  ADMIN SITE CUSTOMIZATION
# ─────────────────────────────────────────────

admin.site.site_header  = '🎮 Practical Khata Admin'
admin.site.site_title   = 'Practical Khata'
admin.site.index_title  = 'Dashboard'