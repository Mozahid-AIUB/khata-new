from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Avg, Sum


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

    def save(self, *args, **kwargs):
        """Auto-compress product image on upload using Pillow."""
        # Get old image path before save (so we don't recompress on every field update)
        old_image_name = None
        if self.pk:
            try:
                old_image_name = Product.objects.get(pk=self.pk).image.name
            except Product.DoesNotExist:
                pass

        super().save(*args, **kwargs)

        # Only compress if this is a new image (not re-saving same file)
        if self.image and self.image.name != old_image_name:
            self._compress_image(self.image)

    @staticmethod
    def _compress_image(image_field, max_size=(800, 800), quality=82):
        """
        Compress & resize image in-place.
        - Converts RGBA/P → RGB (JPEG compat)
        - Resizes to max 800×800 (keeps aspect ratio)
        - Saves as JPEG at quality=82 (~70% smaller)
        """
        try:
            from PIL import Image as PilImage
            import io, os
            from django.core.files.base import ContentFile

            img_path = image_field.path
            if not os.path.exists(img_path):
                return

            img = PilImage.open(img_path)
            # Convert palette/RGBA to RGB for JPEG
            if img.mode in ('RGBA', 'P', 'LA'):
                bg = PilImage.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                bg.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = bg
            elif img.mode != 'RGB':
                img = img.convert('RGB')

            # Resize (thumbnail keeps aspect ratio, never upscales)
            img.thumbnail(max_size, PilImage.LANCZOS)

            # Save back as JPEG
            out = io.BytesIO()
            img.save(out, format='JPEG', quality=quality, optimize=True)
            out.seek(0)

            # Replace file (keep same name but .jpg extension)
            base = os.path.splitext(os.path.basename(img_path))[0]
            new_name = f"{base}.jpg"

            # Write compressed bytes directly to storage path
            with open(img_path, 'wb') as f:
                f.write(out.read())

        except Exception:
            pass  # Never crash on image compression failure


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
        ('bkash',   'bKash'),
        ('nagad',   'Nagad'),
        ('cash',    'Cash on Delivery'),
        ('sslcommerz', 'Card / Online (SSLCommerz)'),
        ('other',   'Other'),
    ]

    PAYMENT_STATUS = [
        ('unpaid',    'Unpaid'),
        ('paid',      'Paid'),
        ('failed',    'Failed'),
        ('cancelled', 'Cancelled'),
        ('refunded',  'Refunded'),
    ]

    # ── Human-readable order ID (e.g. PK-20260001) ──
    order_id       = models.CharField(max_length=30, unique=True, blank=True,
                     help_text='Auto-generated: PK-YYYYXXXX')

    user           = models.ForeignKey(User, on_delete=models.SET_NULL,
                     null=True, blank=True, related_name='orders')
    customer_name  = models.CharField(max_length=100)
    phone          = models.CharField(max_length=15)
    address        = models.TextField()
    total_amount   = models.DecimalField(max_digits=10, decimal_places=2)
    discount       = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    delivery_charge = models.DecimalField(max_digits=6, decimal_places=2, default=110)
    coupon         = models.ForeignKey(Coupon, on_delete=models.SET_NULL, null=True, blank=True)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS,
                     default='bkash', blank=True)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS,
                     default='unpaid')
    payment_ref    = models.CharField(max_length=200, blank=True,
                     help_text='bKash/Nagad TrxID or SSLCommerz val_id')
    ssl_transaction_id = models.CharField(max_length=100, blank=True,
                     help_text='SSLCommerz bank_tran_id')
    status         = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    tracking_note  = models.TextField(blank=True)
    estimated_delivery_date = models.DateField(
        null=True, blank=True,
        help_text='Expected delivery date (set manually by admin or auto on confirmation)'
    )
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        # Auto-set estimated_delivery_date on first save (3 business days from now)
        if not self.pk and not self.estimated_delivery_date:
            from datetime import date, timedelta
            d = date.today()
            days_added = 0
            while days_added < 3:
                d += timedelta(days=1)
                if d.weekday() < 5:  # Mon–Fri only
                    days_added += 1
            self.estimated_delivery_date = d

        # Auto-generate readable order_id on first save
        if not self.order_id:
            super().save(*args, **kwargs)
            year = self.created_at.strftime('%Y')
            self.order_id = f"PK-{year}{self.id:04d}"
            Order.objects.filter(pk=self.pk).update(order_id=self.order_id)
        else:
            super().save(*args, **kwargs)

    def __str__(self):
        return f"Order {self.order_id or self.id} — {self.customer_name}"

    @property
    def grand_total(self):
        return float(self.total_amount)

    @property
    def total_price(self):
        """Alias used in templates/chatbot."""
        return float(self.total_amount)

    @property
    def final_amount(self):
        """Alias for total_amount (used in admin order templates)."""
        return float(self.total_amount)

    @property
    def subtotal(self):
        return float(self.total_amount) - float(self.delivery_charge) + float(self.discount)

    @property
    def is_cancellable(self):
        return self.status in ['pending', 'confirmed']

    @property
    def is_paid(self):
        return self.payment_status == 'paid'


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


# ═══════════════════════════════════════════════
#  🎮 GAMIFICATION SYSTEM
# ═══════════════════════════════════════════════

class UserProfile(models.Model):
    """
    Extended user profile — XP, level, referral code, total stats.
    Auto-created via post_save signal on User creation.
    """
    LEVEL_THRESHOLDS = [
        (0,    'Newcomer',   '🌱'),
        (100,  'Explorer',   '⚡'),
        (300,  'Scholar',    '📚'),
        (600,  'Achiever',   '🏆'),
        (1000, 'Champion',   '🔥'),
        (2000, 'Legend',     '👑'),
    ]

    user          = models.OneToOneField(User, on_delete=models.CASCADE,
                    related_name='profile')
    xp            = models.PositiveIntegerField(default=0, help_text='Experience points')
    referral_code = models.CharField(max_length=12, unique=True, blank=True,
                    help_text='User\'s unique referral code')
    referred_by   = models.ForeignKey('self', on_delete=models.SET_NULL,
                    null=True, blank=True, related_name='referrals')
    total_orders  = models.PositiveIntegerField(default=0)
    total_spent   = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    scratch_cards = models.PositiveIntegerField(default=0,
                    help_text='Unscratched cards available')
    created_at    = models.DateTimeField(auto_now_add=True)
    updated_at    = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.referral_code:
            import random, string
            while True:
                code = 'PK' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                if not UserProfile.objects.filter(referral_code=code).exists():
                    self.referral_code = code
                    break
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} — {self.xp} XP"

    @property
    def level_info(self):
        """Returns (level_name, level_icon, xp_for_next, progress_pct)."""
        current_thresh = (0, 'Newcomer', '🌱')
        next_thresh    = None
        for i, (xp_req, name, icon) in enumerate(self.LEVEL_THRESHOLDS):
            if self.xp >= xp_req:
                current_thresh = (xp_req, name, icon)
                if i + 1 < len(self.LEVEL_THRESHOLDS):
                    next_thresh = self.LEVEL_THRESHOLDS[i + 1]
        if next_thresh:
            xp_in_level    = self.xp - current_thresh[0]
            xp_needed      = next_thresh[0] - current_thresh[0]
            progress_pct   = min(100, int(xp_in_level / xp_needed * 100))
            xp_to_next     = next_thresh[0] - self.xp
        else:
            progress_pct   = 100
            xp_to_next     = 0
        return {
            'name':         current_thresh[1],
            'icon':         current_thresh[2],
            'progress_pct': progress_pct,
            'xp_to_next':   xp_to_next,
            'next_level':   next_thresh[1] if next_thresh else None,
        }

    def add_xp(self, amount, reason=''):
        """Add XP and create an XP log entry."""
        self.xp += amount
        self.save(update_fields=['xp', 'updated_at'])
        XPLog.objects.create(profile=self, amount=amount, reason=reason)
        # Check badges after each XP gain
        self._award_badges()

    def _award_badges(self):
        """Auto-award badges based on current stats."""
        BADGE_RULES = [
            ('first_order',   lambda p: p.total_orders >= 1),
            ('five_orders',   lambda p: p.total_orders >= 5),
            ('ten_orders',    lambda p: p.total_orders >= 10),
            ('big_spender',   lambda p: float(p.total_spent) >= 2000),
            ('referrer',      lambda p: p.referrals.count() >= 1),
            ('super_referrer',lambda p: p.referrals.count() >= 5),
            ('explorer',      lambda p: p.xp >= 100),
            ('champion',      lambda p: p.xp >= 1000),
        ]
        for slug, check in BADGE_RULES:
            if check(self):
                Badge.objects.get_or_create(profile=self, badge_slug=slug)


class XPLog(models.Model):
    """Log every XP transaction."""
    profile    = models.ForeignKey(UserProfile, on_delete=models.CASCADE,
                 related_name='xp_logs')
    amount     = models.IntegerField()
    reason     = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"+{self.amount} XP — {self.reason}"


class Badge(models.Model):
    """Earned badges per user."""
    BADGE_CATALOG = {
        'first_order':    ('🛒', 'First Order',    'প্রথম অর্ডার করেছো!'),
        'five_orders':    ('📦', '5 Orders',        '৫টি অর্ডার সম্পন্ন'),
        'ten_orders':     ('🏅', '10 Orders',       '১০টি অর্ডার সম্পন্ন'),
        'big_spender':    ('💎', 'Big Spender',     '৳২০০০+ খরচ করেছো'),
        'referrer':       ('🤝', 'Referrer',        'বন্ধুকে রেফার করেছো'),
        'super_referrer': ('🌟', 'Super Referrer',  '৫+ বন্ধুকে রেফার করেছো'),
        'explorer':       ('⚡', 'Explorer',        '১০০ XP অর্জন করেছো'),
        'champion':       ('🔥', 'Champion',        '১০০০ XP অর্জন করেছো'),
    }

    profile    = models.ForeignKey(UserProfile, on_delete=models.CASCADE,
                 related_name='badges')
    badge_slug = models.CharField(max_length=30)
    earned_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('profile', 'badge_slug')
        ordering = ['-earned_at']

    def __str__(self):
        return f"{self.profile.user.username} — {self.badge_slug}"

    @property
    def info(self):
        return self.BADGE_CATALOG.get(self.badge_slug, ('🏷️', self.badge_slug, ''))


class ScratchCard(models.Model):
    """One-time scratch card rewards after an order."""
    STATUS_CHOICES = [
        ('pending',   'Pending'),
        ('scratched', 'Scratched'),
        ('expired',   'Expired'),
    ]
    REWARD_TYPES = [
        ('discount_pct',  'Discount %'),
        ('discount_flat', 'Discount Flat'),
        ('free_delivery', 'Free Delivery'),
        ('xp_bonus',      'XP Bonus'),
    ]

    profile      = models.ForeignKey(UserProfile, on_delete=models.CASCADE,
                   related_name='scratch_card_set')
    order        = models.ForeignKey('Order', on_delete=models.CASCADE,
                   related_name='scratch_cards', null=True, blank=True)
    status       = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    reward_type  = models.CharField(max_length=20, choices=REWARD_TYPES, default='discount_pct')
    reward_value = models.PositiveIntegerField(default=10,
                   help_text='Value: 10 = 10% or ৳10 or 50XP')
    coupon_code  = models.CharField(max_length=20, blank=True,
                   help_text='Auto-generated coupon code after scratch')
    expires_at   = models.DateTimeField()
    created_at   = models.DateTimeField(auto_now_add=True)
    scratched_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"ScratchCard #{self.id} — {self.profile.user.username} ({self.status})"

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    def scratch(self):
        """Mark as scratched and create coupon if applicable."""
        if self.status != 'pending' or self.is_expired:
            return None
        self.status = 'scratched'
        self.scratched_at = timezone.now()
        # Auto-create a coupon code
        if self.reward_type in ('discount_pct', 'discount_flat'):
            import random, string
            code = 'SCRATCH' + ''.join(random.choices(string.digits, k=4))
            dtype = 'percent' if self.reward_type == 'discount_pct' else 'flat'
            Coupon.objects.create(
                code=code,
                discount_type=dtype,
                discount_value=self.reward_value,
                min_order=0,
                max_uses=1,
                expires_at=timezone.now() + timezone.timedelta(days=7),
            )
            self.coupon_code = code
        self.save()
        return self.coupon_code