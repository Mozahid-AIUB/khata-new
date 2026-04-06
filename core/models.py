from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Avg


# ─────────────────────────────────────────────
#  SITE SETTINGS (Dynamic config from admin)
# ─────────────────────────────────────────────

class SiteSettings(models.Model):
    """
    Global site settings — editable from Django admin.
    Only ONE row should exist (singleton pattern).
    """
    site_name        = models.CharField(max_length=100, default='Practical Khata')
    tagline          = models.CharField(max_length=200, default='SSC & HSC Practical Khata')
    whatsapp_number  = models.CharField(max_length=20, default='8801707591255')
    delivery_charge  = models.DecimalField(max_digits=6, decimal_places=2, default=110)
    free_delivery_above = models.DecimalField(max_digits=8, decimal_places=2, default=0,
                          help_text='0 means no free delivery threshold')
    bkash_number     = models.CharField(max_length=20, blank=True, default='01707591255')
    nagad_number     = models.CharField(max_length=20, blank=True, default='01707591255')

    # AI Chat widget
    chat_enabled     = models.BooleanField(default=True, help_text='Show AI chat widget')
    chat_welcome_msg = models.CharField(max_length=300,
                       default='আসসালামু আলাইকুম! 👋 কীভাবে সাহায্য করতে পারি?')

    # SEO
    meta_description = models.TextField(blank=True,
                       default='Buy SSC & HSC Practical Khata online in Bangladesh.')
    meta_keywords    = models.CharField(max_length=300, blank=True,
                       default='practical khata, SSC, HSC, Bangladesh')
    og_image         = models.ImageField(upload_to='site/', blank=True, null=True)

    class Meta:
        verbose_name = 'Site Settings'
        verbose_name_plural = 'Site Settings'

    def __str__(self):
        return self.site_name

    @classmethod
    def get(cls):
        """Always returns the single settings instance."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


# ─────────────────────────────────────────────
#  CATEGORY
# ─────────────────────────────────────────────

class Category(models.Model):
    name        = models.CharField(max_length=100)
    slug        = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    icon        = models.CharField(max_length=10, blank=True, default='📚',
                  help_text='Emoji icon for category')
    order       = models.PositiveIntegerField(default=0, help_text='Display order')

    class Meta:
        verbose_name_plural = 'Categories'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


# ─────────────────────────────────────────────
#  PRODUCT
# ─────────────────────────────────────────────

class Product(models.Model):
    LEVEL_CHOICES = [('SSC', 'SSC'), ('HSC', 'HSC'), ('BOTH', 'SSC & HSC')]

    # Core
    name        = models.CharField(max_length=200)
    slug        = models.SlugField(unique=True)
    category    = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    level       = models.CharField(max_length=4, choices=LEVEL_CHOICES)
    description = models.TextField()
    price       = models.DecimalField(max_digits=10, decimal_places=2)
    stock       = models.IntegerField(default=0)
    image       = models.ImageField(upload_to='products/')
    featured    = models.BooleanField(default=False)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    # Flash Sale
    sale_price   = models.DecimalField(max_digits=10, decimal_places=2,
                   null=True, blank=True, help_text='Sale price (leave empty for no sale)')
    sale_starts_at = models.DateTimeField(null=True, blank=True)
    sale_ends_at   = models.DateTimeField(null=True, blank=True)

    # SEO
    meta_title       = models.CharField(max_length=70, blank=True,
                       help_text='SEO title (max 70 chars). Leave empty to use product name.')
    meta_description = models.CharField(max_length=160, blank=True,
                       help_text='SEO description (max 160 chars).')

    # Analytics
    view_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-featured', '-created_at']

    def __str__(self):
        return f"{self.level} - {self.name}"

    # ── Properties ──

    @property
    def is_on_sale(self):
        """True if product currently has an active flash sale."""
        if not self.sale_price:
            return False
        now = timezone.now()
        if self.sale_starts_at and now < self.sale_starts_at:
            return False
        if self.sale_ends_at and now > self.sale_ends_at:
            return False
        return True

    @property
    def current_price(self):
        """Return sale_price if active, else regular price."""
        return self.sale_price if self.is_on_sale else self.price

    @property
    def discount_percent(self):
        """Percentage saved during sale."""
        if self.is_on_sale and self.sale_price:
            saved = float(self.price) - float(self.sale_price)
            return round(saved / float(self.price) * 100)
        return 0

    @property
    def is_in_stock(self):
        return self.stock > 0

    @property
    def is_low_stock(self):
        return 0 < self.stock <= 5

    @property
    def get_meta_title(self):
        return self.meta_title or f"{self.name} — {self.level} Practical Khata"

    @property
    def get_meta_description(self):
        return self.meta_description or self.description[:160]

    def average_rating(self):
        result = self.reviews.filter(approved=True).aggregate(avg=Avg('rating'))
        return round(result['avg'] or 0, 1)

    def increment_views(self):
        Product.objects.filter(pk=self.pk).update(view_count=models.F('view_count') + 1)


# ─────────────────────────────────────────────
#  PRODUCT IMAGES (Multiple)
# ─────────────────────────────────────────────

class ProductImage(models.Model):
    """Extra images for a product (gallery)."""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='extra_images')
    image   = models.ImageField(upload_to='products/gallery/')
    alt     = models.CharField(max_length=200, blank=True)
    order   = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.product.name} — image {self.order}"


# ─────────────────────────────────────────────
#  COUPON
# ─────────────────────────────────────────────

class Coupon(models.Model):
    DISCOUNT_TYPES = [('percent', 'Percent %'), ('flat', 'Flat ৳')]

    code           = models.CharField(max_length=20, unique=True)
    discount_type  = models.CharField(max_length=10, choices=DISCOUNT_TYPES, default='percent')
    discount_value = models.DecimalField(max_digits=6, decimal_places=2)
    min_order      = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    max_uses       = models.IntegerField(default=100)
    used_count     = models.IntegerField(default=0)
    active         = models.BooleanField(default=True)
    expires_at     = models.DateTimeField(null=True, blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        symbol = '%' if self.discount_type == 'percent' else '৳'
        return f"{self.code} ({self.discount_value}{symbol})"

    def is_valid(self):
        if not self.active:
            return False, "কুপন inactive।"
        if self.used_count >= self.max_uses:
            return False, "কুপন শেষ হয়ে গেছে।"
        if self.expires_at and timezone.now() > self.expires_at:
            return False, "কুপনের মেয়াদ শেষ।"
        return True, "valid"

    @property
    def is_expired(self):
        return self.expires_at and timezone.now() > self.expires_at


# ─────────────────────────────────────────────
#  ORDER
# ─────────────────────────────────────────────

class Order(models.Model):
    STATUS_CHOICES = [
        ('pending',    'Pending'),
        ('confirmed',  'Confirmed'),
        ('processing', 'Processing'),
        ('dispatched', 'Dispatched'),
        ('delivered',  'Delivered'),
        ('cancelled',  'Cancelled'),
    ]

    PAYMENT_METHODS = [
        ('bkash',  'bKash'),
        ('nagad',  'Nagad'),
        ('cash',   'Cash on Delivery'),
        ('other',  'Other'),
    ]

    user           = models.ForeignKey(User, on_delete=models.SET_NULL,
                     null=True, blank=True, related_name='orders')
    customer_name  = models.CharField(max_length=100)
    phone          = models.CharField(max_length=15)
    address        = models.TextField()
    total_amount   = models.DecimalField(max_digits=10, decimal_places=2)
    discount       = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    delivery_charge = models.DecimalField(max_digits=6, decimal_places=2, default=110)
    coupon         = models.ForeignKey(Coupon, on_delete=models.SET_NULL, null=True, blank=True)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHODS,
                     default='bkash', blank=True)
    payment_ref    = models.CharField(max_length=100, blank=True,
                     help_text='bKash/Nagad transaction ID')
    status         = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    tracking_note  = models.TextField(blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Order #{self.id} — {self.customer_name}"

    @property
    def grand_total(self):
        return float(self.total_amount)

    @property
    def subtotal(self):
        return float(self.total_amount) - float(self.delivery_charge) + float(self.discount)

    @property
    def is_cancellable(self):
        return self.status in ['pending', 'confirmed']


# ─────────────────────────────────────────────
#  ORDER ITEM
# ─────────────────────────────────────────────

class OrderItem(models.Model):
    order    = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product  = models.ForeignKey(Product, on_delete=models.SET_NULL,
               null=True, blank=True)
    name     = models.CharField(max_length=200, blank=True,
               help_text='Snapshot of product name at order time')
    quantity = models.IntegerField(default=1)
    price    = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity}× {self.name or (self.product.name if self.product else 'Deleted')}"

    @property
    def subtotal(self):
        return float(self.price) * self.quantity

    def save(self, *args, **kwargs):
        # Snapshot product name so it persists if product is deleted
        if self.product and not self.name:
            self.name = self.product.name
        super().save(*args, **kwargs)


# ─────────────────────────────────────────────
#  REVIEW
# ─────────────────────────────────────────────

class Review(models.Model):
    product    = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user       = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    name       = models.CharField(max_length=80)
    rating     = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    comment    = models.TextField()
    approved   = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        # One review per user per product
        constraints = [
            models.UniqueConstraint(
                fields=['product', 'user'],
                condition=models.Q(user__isnull=False),
                name='unique_review_per_user'
            )
        ]

    def __str__(self):
        return f"{self.name} — {self.product.name} ({self.rating}★)"

    @property
    def star_range(self):
        return range(self.rating)


# ─────────────────────────────────────────────
#  SUPPORT CHAT (WhatsApp + AI widget)
# ─────────────────────────────────────────────

class SupportMessage(models.Model):
    """
    Stores AI chat messages for analytics.
    Helps improve the bot over time.
    """
    SOURCE_CHOICES = [
        ('ai',       'AI Response'),
        ('fallback', 'Fallback Response'),
        ('whatsapp', 'WhatsApp Redirect'),
    ]

    session_key = models.CharField(max_length=100, blank=True)
    user        = models.ForeignKey(User, on_delete=models.SET_NULL,
                  null=True, blank=True)
    question    = models.TextField()
    answer      = models.TextField()
    source      = models.CharField(max_length=20, choices=SOURCE_CHOICES, default='fallback')
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Support Message'

    def __str__(self):
        return f"{self.session_key[:8]} — {self.question[:50]}"


# ─────────────────────────────────────────────
#  FLASH SALE BANNER
# ─────────────────────────────────────────────

class FlashSale(models.Model):
    """Sitewide flash sale banner with countdown."""
    title      = models.CharField(max_length=200)
    subtitle   = models.CharField(max_length=300, blank=True)
    ends_at    = models.DateTimeField()
    is_active  = models.BooleanField(default=True)
    cta_text   = models.CharField(max_length=50, default='এখনই অর্ডার করুন 🚀')
    cta_url    = models.CharField(max_length=200, default='/products/')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    @property
    def is_live(self):
        return self.is_active and timezone.now() < self.ends_at

    @property
    def seconds_remaining(self):
        delta = self.ends_at - timezone.now()
        return max(0, int(delta.total_seconds()))