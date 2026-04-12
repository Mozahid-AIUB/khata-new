from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Count, Avg
from django.utils import timezone
from django.conf import settings
from .models import Product, Category, Order, OrderItem, Coupon, Review, UserProfile, Badge, XPLog, ScratchCard
import os, re, json, unicodedata, datetime, time
from collections import defaultdict
from threading import Lock

# ─────────────────────────────────────────────
#  RATE LIMITER (in-memory, thread-safe)
# ─────────────────────────────────────────────
#  Usage: @rate_limit(max_calls=5, window_sec=60)
#  Falls back gracefully — never crashes on limiter error.

_rl_store: dict = defaultdict(list)   # key → [timestamp, ...]
_rl_lock = Lock()


def rate_limit(max_calls: int = None, window_sec: int = None):
    """
    Decorator factory: limits calls per IP per window.
    Config pulled from settings if not passed directly.
    On limit breach: returns 429 JSON for AJAX, or shows error + redirect for form POST.
    """
    def decorator(view_func):
        def wrapped(request, *args, **kwargs):
            try:
                _max   = max_calls  or getattr(settings, 'RATE_LIMIT_CHECKOUT', 5)
                _win   = window_sec or getattr(settings, 'RATE_LIMIT_WINDOW_SEC', 60)
                ip     = (
                    request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
                    or request.META.get('REMOTE_ADDR', 'unknown')
                )
                key    = f"{view_func.__name__}:{ip}"
                now    = time.time()

                with _rl_lock:
                    # Purge old timestamps outside window
                    _rl_store[key] = [t for t in _rl_store[key] if now - t < _win]
                    count = len(_rl_store[key])

                    if count >= _max:
                        wait = int(_win - (now - _rl_store[key][0])) + 1
                        # AJAX request → JSON
                        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or \
                           request.content_type == 'application/json':
                            return JsonResponse(
                                {'error': f'অনেক বেশি request। {wait} সেকেন্ড পরে চেষ্টা করুন।'},
                                status=429
                            )
                        # Form POST → error message + redirect
                        messages.error(
                            request,
                            f'⚠️ অনেক বেশি চেষ্টা করা হয়েছে। {wait} সেকেন্ড পরে আবার চেষ্টা করুন।'
                        )
                        return redirect(request.META.get('HTTP_REFERER', '/'))

                    _rl_store[key].append(now)

            except Exception:
                pass  # Never block a request because of limiter bug

            return view_func(request, *args, **kwargs)
        wrapped.__name__ = view_func.__name__
        wrapped.__doc__  = view_func.__doc__
        return wrapped
    return decorator


# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def staff_required(view_func):
    """Staff only decorator — non-staff gets redirected to login."""
    decorated = user_passes_test(
        lambda u: u.is_active and u.is_staff,
        login_url='/login/'
    )(view_func)
    return login_required(decorated)


def get_site_domain(request):
    """Return current site domain dynamically."""
    return f"{request.scheme}://{request.get_host()}"


# ─────────────────────────────────────────────
#  HOME & PRODUCTS
# ─────────────────────────────────────────────

@cache_page(60 * 5)   # 4.8 — Cache home page for 5 min
@vary_on_cookie       # Separate cache entry per session cookie → safe for logged-in users
def home(request):
    from .models import FlashSale
    now = timezone.now()

    featured = Product.objects.filter(featured=True, stock__gt=0).select_related('category')[:6]
    categories = Category.objects.annotate(product_count=Count('products')).filter(product_count__gt=0)

    flash_sale_products = Product.objects.filter(
        sale_price__isnull=False,
        sale_ends_at__gt=now,
        stock__gt=0
    ).select_related('category')[:4]

    # Active FlashSale banner (from admin)
    active_flash = FlashSale.objects.filter(is_active=True, ends_at__gt=now).first()

    # Server timestamp in ms for JS countdown sync (avoids client clock drift)
    server_now_ms = int(now.timestamp() * 1000)

    return render(request, 'home.html', {
        'featured_products': featured,
        'categories': categories,
        'flash_sale_products': flash_sale_products,
        'active_flash': active_flash,
        'server_now_ms': server_now_ms,
        # Pass ends_at as ms timestamp so JS can use it accurately
        'flash_ends_ms': int(active_flash.ends_at.timestamp() * 1000) if active_flash else None,
    })


@cache_page(60 * 3)   # Cache product list for 3 min
@vary_on_cookie       # Separate cache per session → cart badge correct
def product_list(request, category_slug=None):
    products = Product.objects.filter(stock__gt=0).select_related('category').order_by('-created_at')
    categories = Category.objects.annotate(product_count=Count('products'))
    current_category = None

    # Category filter
    if category_slug:
        current_category = get_object_or_404(Category, slug=category_slug)
        products = products.filter(category=current_category)

    # Level filter (SSC/HSC)
    level = request.GET.get('level', '')
    if level in ['SSC', 'HSC']:
        products = products.filter(level=level)

    # Sort
    sort = request.GET.get('sort', '-created_at')
    sort_options = {
        'price_asc': 'price',
        'price_desc': '-price',
        'newest': '-created_at',
        'popular': '-id',
    }
    products = products.order_by(sort_options.get(sort, '-created_at'))

    # Pagination
    paginator = Paginator(products, 12)
    page = request.GET.get('page', 1)
    products_page = paginator.get_page(page)

    return render(request, 'products.html', {
        'products':         products_page,
        'categories':       categories,
        'current_category': current_category,
        'level_filter':     level,
        'sort':             sort,
        'total_count':      paginator.count,
        # Sort options for sidebar/topbar rendering
        'sort_opts': [
            ('newest',     'Newest',      '🆕'),
            ('price_asc',  'Price ↑',     '⬆️'),
            ('price_desc', 'Price ↓',     '⬇️'),
            ('popular',    'Popular',     '🔥'),
        ],
    })


def product_detail(request, slug):
    product = get_object_or_404(Product.objects.select_related('category'), slug=slug)
    # Track page view (atomic F() update — no race condition)
    product.increment_views()
    related = Product.objects.filter(
        category=product.category, stock__gt=0
    ).exclude(id=product.id).order_by('-featured')[:4]
    reviews = product.reviews.filter(approved=True).order_by('-created_at')
    avg_rating = reviews.aggregate(avg=Avg('rating'))['avg'] or 0
    in_cart = str(product.id) in request.session.get('cart', {})

    return render(request, 'product_detail.html', {
        'product': product,
        'related_products': related,
        'reviews': reviews,
        'avg_rating': round(avg_rating, 1),
        'review_count': reviews.count(),
        'in_cart': in_cart,
    })


def search_products(request):
    query = request.GET.get('q', '').strip()
    products = Product.objects.filter(stock__gt=0)
    if query:
        products = products.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(category__name__icontains=query)
        ).distinct()
    paginator = Paginator(products, 12)
    products_page = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'products.html', {
        'products': products_page,
        'search_query': query,
        'total_count': paginator.count,
    })


# ─────────────────────────────────────────────
#  CART
# ─────────────────────────────────────────────

def add_to_cart(request, product_id):
    product = get_object_or_404(Product, id=product_id)

    # Stock check
    if product.stock <= 0:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'out_of_stock'})
        messages.error(request, f'"{product.name}" এখন stock এ নেই।')
        return redirect(request.META.get('HTTP_REFERER', 'home'))

    cart = request.session.get('cart', {})
    pid = str(product_id)

    # Check cart quantity vs stock
    current_qty = cart[pid]['quantity'] if pid in cart else 0
    if current_qty >= product.stock:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'max_stock_reached'})
        messages.warning(request, f'সর্বোচ্চ {product.stock}টা যোগ করা যাবে।')
        return redirect(request.META.get('HTTP_REFERER', 'home'))

    if pid in cart:
        cart[pid]['quantity'] += 1
        # Price re-check: update to current_price in case sale changed
        cart[pid]['price'] = float(product.current_price)
        cart[pid]['original_price'] = float(product.price)
        cart[pid]['is_on_sale'] = product.is_on_sale
    else:
        cart[pid] = {
            'name': product.name,
            'price': float(product.current_price),       # ✅ sale price if active
            'original_price': float(product.price),      # original for strikethrough
            'is_on_sale': product.is_on_sale,
            'quantity': 1,
            'image': product.image.url if product.image else None,
            'slug': product.slug,
            'level': product.level,
        }

    request.session['cart'] = cart
    cart_count = sum(i['quantity'] for i in cart.values())

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'cart_count': cart_count})
    messages.success(request, f'✅ "{product.name}" কার্টে যোগ হয়েছে!')
    return redirect(request.META.get('HTTP_REFERER', 'home'))


def remove_from_cart(request, product_id):
    from .models import SiteSettings
    cart = request.session.get('cart', {})
    pid = str(product_id)
    cart.pop(pid, None)
    request.session['cart'] = cart

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        site = SiteSettings.get()
        coupon_discount = float(request.session.get('coupon_discount', 0))
        total = sum(float(i['price']) * i['quantity'] for i in cart.values())
        final_total = max(0, total - coupon_discount)
        delivery = float(site.delivery_charge)
        return JsonResponse({
            'success': True,
            'cart_count': sum(i['quantity'] for i in cart.values()),
            'total': total,
            'grand_total': final_total + delivery,
        })
    return redirect('cart')


@require_POST
def update_cart(request, product_id):
    try:
        payload = json.loads(request.body.decode('utf-8'))
        quantity = int(payload.get('quantity', 0))
    except (ValueError, json.JSONDecodeError):
        return JsonResponse({'success': False, 'error': 'invalid_payload'}, status=400)

    cart = request.session.get('cart', {})
    pid = str(product_id)

    if quantity <= 0:
        cart.pop(pid, None)
    else:
        # Validate against stock
        product = Product.objects.filter(id=product_id).first()
        if product and quantity > product.stock:
            return JsonResponse({'success': False, 'error': 'exceeds_stock', 'max': product.stock})

        if pid in cart:
            cart[pid]['quantity'] = quantity
            cart[pid]['price'] = float(product.current_price)
            cart[pid]['original_price'] = float(product.price)
            cart[pid]['is_on_sale'] = product.is_on_sale
        elif product:
            cart[pid] = {
                'name': product.name,
                'price': float(product.current_price),
                'original_price': float(product.price),
                'is_on_sale': product.is_on_sale,
                'quantity': quantity,
                'image': product.image.url if product.image else None,
                'slug': product.slug,
                'level': product.level,
            }

    request.session['cart'] = cart
    item_subtotal = float(cart[pid]['price']) * cart[pid]['quantity'] if pid in cart else 0
    from .models import SiteSettings
    site = SiteSettings.get()
    coupon_discount = float(request.session.get('coupon_discount', 0))
    total = sum(float(i['price']) * i['quantity'] for i in cart.values())
    final_total = max(0, total - coupon_discount)
    delivery = float(site.delivery_charge)

    return JsonResponse({
        'success': True,
        'cart_count': sum(i['quantity'] for i in cart.values()),
        'item_subtotal': item_subtotal,
        'total': total,
        'grand_total': final_total + delivery,
    })


def cart_view(request):
    from .models import SiteSettings
    site = SiteSettings.get()

    cart = request.session.get('cart', {})
    total = 0
    savings = 0  # total sale savings

    for item in cart.values():
        item['price'] = float(item['price'])
        item['original_price'] = float(item.get('original_price', item['price']))
        item['is_on_sale'] = item.get('is_on_sale', False)
        item['subtotal'] = item['price'] * item['quantity']
        item['original_subtotal'] = item['original_price'] * item['quantity']
        if item['is_on_sale']:
            savings += item['original_subtotal'] - item['subtotal']
        total += item['subtotal']

    coupon_discount = float(request.session.get('coupon_discount', 0))
    coupon_code = request.session.get('coupon_code', '')
    final_total = max(0, total - coupon_discount)
    delivery_charge = float(site.delivery_charge)
    grand_total = final_total + delivery_charge
    cart_count = sum(i['quantity'] for i in cart.values())

    # ── AJAX: return JSON for cart drawer ──
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        items_list = []
        for pid, item in cart.items():
            image_url = ''
            try:
                from .models import Product
                p = Product.objects.get(pk=int(pid))
                if p.image:
                    image_url = p.image.url
            except Exception:
                pass
            items_list.append({
                'product_id': pid,
                'name': item.get('name', ''),
                'price': item['price'],
                'original_price': item['original_price'],
                'is_on_sale': item['is_on_sale'],
                'quantity': item['quantity'],
                'subtotal': item['subtotal'],
                'image': image_url,
            })
        return JsonResponse({
            'success': True,
            'items': items_list,
            'cart_count': cart_count,
            'subtotal': total,
            'savings': savings,
            'coupon_discount': coupon_discount,
            'delivery_charge': delivery_charge,
            'grand_total': grand_total,
        })

    return render(request, 'cart.html', {
        'cart': cart,
        'subtotal': total,
        'total': total,                    # backward compat
        'savings': savings,                # sale savings to show
        'coupon_discount': coupon_discount,
        'coupon_code': coupon_code,
        'final_total': final_total,
        'delivery_charge': delivery_charge,
        'grand_total': grand_total,
    })


@require_POST
def apply_coupon(request):
    code = request.POST.get('coupon_code', '').strip().upper()
    cart = request.session.get('cart', {})
    total = sum(float(i['price']) * i['quantity'] for i in cart.values())

    try:
        coupon = Coupon.objects.get(code=code)
        valid, msg = coupon.is_valid()
        if not valid:
            messages.error(request, f'❌ {msg}')
            return redirect('cart')
        if float(coupon.min_order) > total:
            messages.error(request, f'❌ Minimum order ৳{int(coupon.min_order)} লাগবে।')
            return redirect('cart')

        discount = (
            round(total * float(coupon.discount_value) / 100, 2)
            if coupon.discount_type == 'percent'
            else float(coupon.discount_value)
        )
        discount = min(discount, total)  # discount > total হবে না

        request.session['coupon_code'] = code
        request.session['coupon_discount'] = discount
        messages.success(request, f'✅ কুপন applied! ৳{int(discount)} ছাড় পেলে।')

    except Coupon.DoesNotExist:
        messages.error(request, '❌ কুপন কোড সঠিক নয়।')
        request.session.pop('coupon_code', None)
        request.session.pop('coupon_discount', None)

    return redirect('cart')


# ─────────────────────────────────────────────
#  CHECKOUT & ORDER TRACKING
# ─────────────────────────────────────────────

BANGLADESH_DISTRICTS = [
    'ঢাকা','চট্টগ্রাম','রাজশাহী','খুলনা','বরিশাল','সিলেট','রংপুর','ময়মনসিংহ',
    'গাজীপুর','নারায়ণগঞ্জ','কুমিল্লা','ফেনী','নোয়াখালী','লক্ষ্মীপুর','চাঁদপুর',
    'ব্রাহ্মণবাড়িয়া','হবিগঞ্জ','মৌলভীবাজার','সুনামগঞ্জ','নেত্রকোনা','কিশোরগঞ্জ',
    'টাঙ্গাইল','মানিকগঞ্জ','মুন্সিগঞ্জ','নরসিংদী','ফরিদপুর','মাদারীপুর','শরীয়তপুর',
    'গোপালগঞ্জ','রাজবাড়ী','পাবনা','সিরাজগঞ্জ','নাটোর','নওগাঁ','চাঁপাইনবাবগঞ্জ',
    'জয়পুরহাট','বগুড়া','গাইবান্ধা','কুড়িগ্রাম','লালমনিরহাট','নীলফামারী','পঞ্চগড়',
    'ঠাকুরগাঁও','দিনাজপুর','জামালপুর','শেরপুর','ময়মনসিংহ','মেহেরপুর','চুয়াডাঙ্গা',
    'কুষ্টিয়া','মাগুরা','নড়াইল','যশোর','সাতক্ষীরা','বাগেরহাট','পিরোজপুর',
    'ঝালকাঠি','বরগুনা','পটুয়াখালী','ভোলা','খাগড়াছড়ি','রাঙামাটি','বান্দরবান',
    'কক্সবাজার',
]

@rate_limit(max_calls=10, window_sec=60)   # 10 checkout attempts per minute per IP
def checkout(request):
    from .models import SiteSettings
    cart = request.session.get('cart', {})
    if not cart:
        messages.warning(request, 'কার্ট খালি!')
        return redirect('products')

    site = SiteSettings.get()
    savings = 0
    total = 0

    for item in cart.values():
        item['price'] = float(item['price'])
        item['original_price'] = float(item.get('original_price', item['price']))
        item['is_on_sale'] = item.get('is_on_sale', False)
        item['subtotal'] = item['price'] * item['quantity']
        item['original_subtotal'] = item['original_price'] * item['quantity']
        if item['is_on_sale']:
            savings += item['original_subtotal'] - item['subtotal']
        total += item['subtotal']

    coupon_discount = float(request.session.get('coupon_discount', 0))
    coupon_code = request.session.get('coupon_code', '')
    final_total = max(0, total - coupon_discount)
    delivery = float(site.delivery_charge)
    grand_total = final_total + delivery

    # Shared context for GET & error re-render
    ctx = {
        'cart': cart,
        'subtotal': total,
        'total': total,
        'savings': savings,
        'coupon_discount': coupon_discount,
        'coupon_code': coupon_code,
        'final_total': final_total,
        'delivery': delivery,
        'grand_total': grand_total,
        'districts': BANGLADESH_DISTRICTS,
    }

    if request.method == 'POST':
        name           = request.POST.get('name', '').strip()
        phone          = request.POST.get('phone', '').strip()
        district       = request.POST.get('district', '').strip()
        address        = request.POST.get('address', '').strip()
        note           = request.POST.get('note', '').strip()
        payment_method = request.POST.get('payment_method', 'bkash').strip()
        payment_ref    = request.POST.get('payment_ref', '').strip()

        # Full address = district + address
        full_address = f"{address}, {district}" if district else address

        if not all([name, phone, address]):
            messages.error(request, 'সব required field পূরণ করুন।')
            return render(request, 'checkout.html', ctx)

        # Validate & use coupon
        coupon_obj = None
        if coupon_code:
            try:
                coupon_obj = Coupon.objects.get(code=coupon_code)
                valid, _ = coupon_obj.is_valid()
                if valid:
                    coupon_obj.used_count += 1
                    coupon_obj.save()
                else:
                    coupon_obj = None
                    coupon_discount = 0
            except Coupon.DoesNotExist:
                pass

        # Create order
        order = Order.objects.create(
            user=request.user if request.user.is_authenticated else None,
            customer_name=name,
            phone=phone,
            address=full_address,
            total_amount=grand_total,
            discount=coupon_discount,
            delivery_charge=delivery,
            coupon=coupon_obj,
            payment_method=payment_method,
            payment_ref=payment_ref,
            tracking_note=note,
        )

        # Create order items + reduce stock
        for pid, item in cart.items():
            product = Product.objects.filter(id=pid).first()
            if product:
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    name=item.get('name', product.name),
                    quantity=item['quantity'],
                    price=item['price'],
                )
                product.stock = max(0, product.stock - item['quantity'])
                product.save(update_fields=['stock'])

        # Clear session
        request.session['cart'] = {}
        request.session['coupon_code'] = ''
        request.session['coupon_discount'] = 0

        # Build WhatsApp confirmation message
        domain = get_site_domain(request)
        pm_labels = {'bkash':'bKash', 'nagad':'Nagad', 'cash':'Cash on Delivery', 'other':'Other'}
        items_text = '%0A'.join([
            f"• {i.get('name','Product')} ×{i['quantity']} = ৳{int(float(i['price'])*i['quantity'])}"
            for i in cart.values()
        ])
        wa_msg = (
            f"আসসালামু আলাইকুম! 👋%0A"
            f"🛒 নতুন অর্ডার %23{order.id}%0A"
            f"━━━━━━━━━━━━━━%0A"
            f"👤 নাম: {name}%0A"
            f"📱 ফোন: {phone}%0A"
            f"📍 ঠিকানা: {full_address}%0A%0A"
            f"📦 পণ্য:%0A{items_text}%0A%0A"
            f"━━━━━━━━━━━━━━%0A"
            f"Subtotal: ৳{int(total)}%0A"
            f"Discount: ৳{int(coupon_discount)}%0A"
            f"Delivery: ৳{int(delivery)}%0A"
            f"💰 মোট: ৳{int(grand_total)}%0A%0A"
            f"💳 Payment: {pm_labels.get(payment_method, payment_method)}%0A"
            + (f"TrxID: {payment_ref}%0A" if payment_ref else "")
            + f"%0A🔗 Tracking: {domain}/order/{order.id}/tracking/"
        )
        return redirect(f"https://wa.me/{site.whatsapp_number}?text={wa_msg}")

    return render(request, 'checkout.html', ctx)


def order_tracking(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    steps = ['pending', 'confirmed', 'processing', 'dispatched', 'delivered']
    step_labels = {
        'pending':    ('⏳', 'অর্ডার পেয়েছি'),
        'confirmed':  ('✅', 'Confirmed'),
        'processing': ('📝', 'তৈরি হচ্ছে'),
        'dispatched': ('🚚', 'পাঠানো হয়েছে'),
        'delivered':  ('🎉', 'পৌঁছে গেছে'),
    }
    current_idx = steps.index(order.status) if order.status in steps else 0
    progress_pct = int((current_idx / (len(steps) - 1)) * 100) if len(steps) > 1 else 0

    return render(request, 'order_tracking.html', {
        'order': order,
        'steps': steps,
        'step_labels': step_labels,
        'current_idx': current_idx,
        'progress_pct': progress_pct,
    })


def order_invoice_pdf(request, order_id):
    """
    Generate a PDF invoice for an order using ReportLab.
    Falls back to an HTML invoice page if ReportLab is not installed.
    """
    order = get_object_or_404(Order, id=order_id)

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import cm
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
        from django.http import HttpResponse
        import io

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4,
            rightMargin=2*cm, leftMargin=2*cm,
            topMargin=2*cm, bottomMargin=2*cm,
        )

        styles = getSampleStyleSheet()
        story  = []

        # ── Colour palette ──
        C_DARK   = colors.HexColor('#0a0e1a')
        C_BLUE   = colors.HexColor('#5b7fff')
        C_GREEN  = colors.HexColor('#00e5b0')
        C_GREY   = colors.HexColor('#6b7a99')
        C_WHITE  = colors.white
        C_LIGHT  = colors.HexColor('#e8ecf4')
        C_WARN   = colors.HexColor('#f59e0b')

        # ── Custom styles ──
        title_style = ParagraphStyle('Title', parent=styles['Normal'],
            fontSize=20, fontName='Helvetica-Bold',
            textColor=C_BLUE, alignment=TA_CENTER, spaceAfter=4)
        sub_style = ParagraphStyle('Sub', parent=styles['Normal'],
            fontSize=9, fontName='Helvetica',
            textColor=C_GREY, alignment=TA_CENTER, spaceAfter=2)
        section_style = ParagraphStyle('Section', parent=styles['Normal'],
            fontSize=8, fontName='Helvetica-Bold',
            textColor=C_BLUE, spaceBefore=12, spaceAfter=4)
        body_style = ParagraphStyle('Body', parent=styles['Normal'],
            fontSize=9, fontName='Helvetica', textColor=C_LIGHT)
        bold_style = ParagraphStyle('Bold', parent=styles['Normal'],
            fontSize=9, fontName='Helvetica-Bold', textColor=C_LIGHT)
        right_style = ParagraphStyle('Right', parent=styles['Normal'],
            fontSize=9, fontName='Helvetica', textColor=C_LIGHT, alignment=TA_RIGHT)
        total_style = ParagraphStyle('Total', parent=styles['Normal'],
            fontSize=12, fontName='Helvetica-Bold', textColor=C_GREEN, alignment=TA_RIGHT)

        # ── Header ──
        story.append(Paragraph('Practical Khata', title_style))
        story.append(Paragraph('SSC &amp; HSC Practical Notebooks', sub_style))
        story.append(Paragraph('📧 practicalkhata@gmail.com', sub_style))
        story.append(HRFlowable(width='100%', thickness=1, color=C_BLUE, spaceAfter=8))

        # ── Invoice Meta ──
        meta_data = [
            [Paragraph('<b>INVOICE</b>', ParagraphStyle('', fontName='Helvetica-Bold', fontSize=14, textColor=C_GREEN)),
             Paragraph(f'Invoice #: <b>{order.order_id or order.id}</b>', bold_style)],
            ['', Paragraph(f'Date: {order.created_at.strftime("%d %b %Y")}', body_style)],
        ]
        if order.estimated_delivery_date:
            meta_data.append(['', Paragraph(f'Est. Delivery: {order.estimated_delivery_date.strftime("%d %b %Y")}', body_style)])

        meta_table = Table(meta_data, colWidths=[10*cm, 7*cm])
        meta_table.setStyle(TableStyle([
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 0.3*cm))

        # ── Customer Info ──
        story.append(Paragraph('CUSTOMER DETAILS', section_style))
        cust_data = [
            [Paragraph(f'<b>Name:</b> {order.customer_name}', body_style),
             Paragraph(f'<b>Phone:</b> {order.phone}', body_style)],
            [Paragraph(f'<b>Address:</b> {order.address}', body_style), ''],
        ]
        if order.estimated_delivery_date and order.status not in ('delivered', 'cancelled'):
            cust_data.append([Paragraph(f'<b>Est. Delivery:</b> {order.estimated_delivery_date.strftime("%d %b, %Y (%A)")}', body_style), ''])
        cust_table = Table(cust_data, colWidths=[10*cm, 7*cm])
        cust_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#0d1420')),
            ('ROUNDEDCORNERS', [4]),
            ('INNERGRID', (0,0), (-1,-1), 0, colors.transparent),
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#1e2a45')),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
        ]))
        story.append(cust_table)
        story.append(Spacer(1, 0.3*cm))

        # ── Items Table ──
        story.append(Paragraph('ORDER ITEMS', section_style))
        items_header = [
            Paragraph('<b>Product</b>', bold_style),
            Paragraph('<b>Qty</b>', ParagraphStyle('', fontName='Helvetica-Bold', fontSize=9, textColor=C_LIGHT, alignment=TA_CENTER)),
            Paragraph('<b>Unit Price</b>', ParagraphStyle('', fontName='Helvetica-Bold', fontSize=9, textColor=C_LIGHT, alignment=TA_RIGHT)),
            Paragraph('<b>Total</b>', ParagraphStyle('', fontName='Helvetica-Bold', fontSize=9, textColor=C_LIGHT, alignment=TA_RIGHT)),
        ]
        items_rows = [items_header]
        for item in order.items.all():
            subtotal = float(item.price) * item.quantity
            items_rows.append([
                Paragraph(item.product.name if item.product else 'Product', body_style),
                Paragraph(str(item.quantity), ParagraphStyle('', fontName='Helvetica', fontSize=9, textColor=C_LIGHT, alignment=TA_CENTER)),
                Paragraph(f'৳{float(item.price):.0f}', ParagraphStyle('', fontName='Helvetica', fontSize=9, textColor=C_LIGHT, alignment=TA_RIGHT)),
                Paragraph(f'৳{subtotal:.0f}', ParagraphStyle('', fontName='Helvetica', fontSize=9, textColor=C_LIGHT, alignment=TA_RIGHT)),
            ])

        items_table = Table(items_rows, colWidths=[9*cm, 2*cm, 3*cm, 3*cm])
        items_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1a2540')),
            ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#0d1420')),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor('#0d1420'), colors.HexColor('#101726')]),
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#1e2a45')),
            ('LINEBELOW', (0,0), (-1,0), 1, C_BLUE),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('LEFTPADDING', (0,0), (-1,-1), 8),
            ('RIGHTPADDING', (0,-1), (-1,-1), 8),
        ]))
        story.append(items_table)
        story.append(Spacer(1, 0.3*cm))

        # ── Totals ──
        delivery = float(order.delivery_charge)
        discount = float(order.discount)
        grand    = float(order.total_amount)

        totals_data = []
        totals_data.append(['', Paragraph('Subtotal:', right_style), Paragraph(f'৳{grand - delivery + discount:.0f}', right_style)])
        totals_data.append(['', Paragraph('Delivery:', right_style), Paragraph(f'৳{delivery:.0f}', right_style)])
        if discount:
            totals_data.append(['', Paragraph('Discount:', right_style), Paragraph(f'- ৳{discount:.0f}', ParagraphStyle('', fontName='Helvetica', fontSize=9, textColor=C_WARN, alignment=TA_RIGHT))])
        totals_data.append(['', Paragraph('<b>Total:</b>', ParagraphStyle('', fontName='Helvetica-Bold', fontSize=11, textColor=C_GREEN, alignment=TA_RIGHT)), Paragraph(f'<b>৳{grand:.0f}</b>', ParagraphStyle('', fontName='Helvetica-Bold', fontSize=12, textColor=C_GREEN, alignment=TA_RIGHT))])

        totals_table = Table(totals_data, colWidths=[9*cm, 5*cm, 3*cm])
        totals_table.setStyle(TableStyle([
            ('LINEABOVE', (1, -1), (-1,-1), 1, C_BLUE),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        story.append(totals_table)

        # Payment status
        pay_status = '✅ Paid' if order.payment_status == 'paid' else '⏳ Unpaid'
        pm_labels = {'bkash': 'bKash', 'nagad': 'Nagad', 'cash': 'Cash on Delivery',
                     'sslcommerz': 'Card / Online', 'other': 'Other'}
        story.append(Spacer(1, 0.4*cm))
        story.append(Paragraph(
            f'Payment: {pm_labels.get(order.payment_method, order.payment_method)} &nbsp;|&nbsp; Status: {pay_status}',
            ParagraphStyle('', fontName='Helvetica', fontSize=8, textColor=C_GREY, alignment=TA_RIGHT)
        ))
        if order.payment_ref:
            story.append(Paragraph(f'Ref: {order.payment_ref}',
                ParagraphStyle('', fontName='Helvetica', fontSize=8, textColor=C_GREY, alignment=TA_RIGHT)))

        # Footer
        story.append(Spacer(1, 0.6*cm))
        story.append(HRFlowable(width='100%', thickness=0.5, color=colors.HexColor('#1e2a45'), spaceAfter=8))
        story.append(Paragraph(
            'ধন্যবাদ Practical Khata-র সাথে থাকার জন্য! 🙏 | practicalkhata.com',
            ParagraphStyle('', fontName='Helvetica', fontSize=8, textColor=C_GREY, alignment=TA_CENTER)
        ))

        doc.build(story)
        buffer.seek(0)
        filename = f"invoice-{order.order_id or order.id}.pdf"
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response

    except ImportError:
        # ReportLab not installed — render a printable HTML fallback
        return render(request, 'order_invoice_html.html', {'order': order})


# ─────────────────────────────────────────────
#  AUTH
# ─────────────────────────────────────────────

def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        username  = request.POST.get('username', '').strip()
        email     = request.POST.get('email', '').strip()
        password  = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')

        errors = []
        if not username or len(username) < 3:
            errors.append('Username কমপক্ষে ৩ অক্ষর হতে হবে।')
        if password != password2:
            errors.append('পাসওয়ার্ড মিলছে না।')
        if len(password) < 6:
            errors.append('পাসওয়ার্ড কমপক্ষে ৬ অক্ষর হতে হবে।')
        if User.objects.filter(username=username).exists():
            errors.append('এই username আগেই আছে।')

        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            user = User.objects.create_user(username=username, email=email, password=password)
            login(request, user)
            messages.success(request, f'স্বাগতম {username}! Account তৈরি হয়েছে। 🎉')
            return redirect('dashboard')

    return render(request, 'register.html')


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            next_url = request.GET.get('next', 'dashboard')
            return redirect(next_url)
        messages.error(request, '❌ Username বা password ভুল।')
    return render(request, 'login.html')


def logout_view(request):
    logout(request)
    messages.success(request, 'Logout সফল হয়েছে।')
    return redirect('home')


@login_required
def dashboard(request):
    orders = Order.objects.filter(
        user=request.user
    ).prefetch_related('items__product').order_by('-created_at')

    stats = {
        'total_orders': orders.count(),
        'total_spent':  orders.aggregate(s=Sum('total_amount'))['s'] or 0,
        'pending':      orders.filter(status='pending').count(),
        'delivered':    orders.filter(status='delivered').count(),
    }

    # ── Gamification data ──
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    badges      = profile.badges.all()
    xp_logs     = profile.xp_logs.all()[:8]
    pending_cards = profile.scratch_card_set.filter(status='pending')
    level_info  = profile.level_info

    # Handle referral code submission
    ref_msg = None
    if request.method == 'POST' and 'apply_referral' in request.POST:
        ref_code = request.POST.get('referral_input', '').strip().upper()
        if ref_code == profile.referral_code:
            ref_msg = ('error', 'নিজের কোড ব্যবহার করা যাবে না।')
        elif profile.referred_by:
            ref_msg = ('error', 'আপনি আগেই রেফারেল ব্যবহার করেছেন।')
        else:
            try:
                referrer_profile = UserProfile.objects.get(referral_code=ref_code)
                profile.referred_by = referrer_profile
                profile.save(update_fields=['referred_by', 'updated_at'])
                profile.add_xp(50, 'রেফারেল কোড ব্যবহার করেছো')
                referrer_profile.add_xp(100, f'{request.user.username} তোমার রেফারেল ব্যবহার করেছে')
                # Give referrer a coupon
                from .models import Coupon as CouponModel
                import random as rnd, string as st
                code = 'REF' + ''.join(rnd.choices(st.digits, k=5))
                CouponModel.objects.create(
                    code=code, discount_type='flat', discount_value=50,
                    min_order=200, max_uses=1,
                    expires_at=timezone.now() + timezone.timedelta(days=30),
                )
                ref_msg = ('success', f'✅ রেফারেল সফল! তুমি ৫০ XP পেয়েছো। রেফারারও ১০০ XP পেয়েছেন।')
            except UserProfile.DoesNotExist:
                ref_msg = ('error', '❌ রেফারেল কোড সঠিক নয়।')

    return render(request, 'dashboard.html', {
        'orders':         orders,
        'stats':          stats,
        'profile':        profile,
        'level_info':     level_info,
        'badges':         badges,
        'xp_logs':        xp_logs,
        'pending_cards':  pending_cards,
        'ref_msg':        ref_msg,
    })


@login_required
@require_POST
def scratch_card(request, card_id):
    """API endpoint — scratch a card, return reward."""
    profile = get_object_or_404(UserProfile, user=request.user)
    card    = get_object_or_404(ScratchCard, id=card_id, profile=profile, status='pending')

    coupon_code = card.scratch()

    # If XP bonus, add it now
    if card.reward_type == 'xp_bonus':
        profile.add_xp(card.reward_value, 'Scratch card XP bonus')

    # Update profile scratch count
    profile.scratch_cards = profile.scratch_card_set.filter(status='pending').count()
    profile.save(update_fields=['scratch_cards', 'updated_at'])

    reward_labels = {
        'discount_pct':  f'{card.reward_value}% ছাড়',
        'discount_flat': f'৳{card.reward_value} ছাড়',
        'free_delivery': 'Free Delivery',
        'xp_bonus':      f'+{card.reward_value} XP',
    }
    return JsonResponse({
        'success':      True,
        'reward_label': reward_labels.get(card.reward_type, 'Reward'),
        'coupon_code':  coupon_code or '',
        'reward_type':  card.reward_type,
        'reward_value': card.reward_value,
    })


# ─────────────────────────────────────────────
#  REVIEWS
# ─────────────────────────────────────────────

@require_POST
def submit_review(request, slug):
    product = get_object_or_404(Product, slug=slug)
    name    = request.POST.get('name', '').strip()
    rating  = request.POST.get('rating', '5')
    comment = request.POST.get('comment', '').strip()

    try:
        rating = int(rating)
        assert 1 <= rating <= 5
    except (ValueError, AssertionError):
        messages.error(request, 'Rating সঠিক নয়।')
        return redirect('product_detail', slug=slug)

    if not name or not comment:
        messages.error(request, 'নাম ও মন্তব্য দেওয়া আবশ্যক।')
        return redirect('product_detail', slug=slug)

    # Prevent duplicate review from same user/session
    if request.user.is_authenticated:
        if Review.objects.filter(product=product, user=request.user).exists():
            messages.warning(request, 'আপনি আগেই review করেছেন।')
            return redirect('product_detail', slug=slug)

    Review.objects.create(
        product=product,
        user=request.user if request.user.is_authenticated else None,
        name=name,
        rating=rating,
        comment=comment,
        approved=False,
    )
    messages.success(request, '✅ Review submit হয়েছে। Approve হলে দেখাবে।')
    return redirect('product_detail', slug=slug)


# ─────────────────────────────────────────────
#  ADMIN — Product Management
# ─────────────────────────────────────────────

@staff_required
def manage_products(request):
    products = Product.objects.select_related('category').order_by('-id')
    categories = Category.objects.all()

    # Filter
    level = request.GET.get('level', '')
    if level:
        products = products.filter(level=level)

    # Low stock alert
    low_stock = products.filter(stock__lte=5, stock__gt=0)
    out_of_stock = products.filter(stock=0).count()

    paginator = Paginator(products, 20)
    products_page = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'manageProduct.html', {
        'products': products_page,
        'categories': categories,
        'low_stock': low_stock,
        'out_of_stock_count': out_of_stock,
    })


@staff_required
def add_product(request):
    categories = Category.objects.all()
    if request.method == 'POST':
        name        = request.POST.get('name', '').strip()
        level       = request.POST.get('level', '').strip()
        description = request.POST.get('description', '').strip()
        price       = request.POST.get('price', '0').strip()
        stock       = request.POST.get('stock', '0').strip()
        category_id = request.POST.get('category', '').strip()
        featured    = request.POST.get('featured') == 'on'
        image       = request.FILES.get('image')

        if not all([name, level, description, price, category_id, image]):
            messages.error(request, '❌ সব ফিল্ড পূরণ করুন।')
            return render(request, 'add_product.html', {'categories': categories})

        # Auto slug
        base_slug = re.sub(
            r'[^a-z0-9]+', '-',
            unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode().lower()
        ).strip('-') or 'product'

        slug, counter = base_slug, 1
        while Product.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        category = get_object_or_404(Category, id=category_id)
        Product.objects.create(
            name=name, slug=slug, level=level, description=description,
            price=price, stock=int(stock), category=category,
            featured=featured, image=image,
        )
        messages.success(request, f'✅ "{name}" যোগ হয়েছে!')
        return redirect('manage_products')

    return render(request, 'add_product.html', {'categories': categories})


@staff_required
def delete_product(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    if request.method == 'POST':
        name = product.name
        product.delete()
        messages.success(request, f'🗑️ "{name}" মুছে ফেলা হয়েছে।')
    return redirect('manage_products')


# ─────────────────────────────────────────────
#  ADMIN — Orders
# ─────────────────────────────────────────────

@staff_required
def admin_orders(request):
    status_filter = request.GET.get('status', '')
    search = request.GET.get('search', '').strip()

    orders = Order.objects.prefetch_related('items__product').order_by('-created_at')

    if status_filter:
        orders = orders.filter(status=status_filter)
    if search:
        orders = orders.filter(
            Q(customer_name__icontains=search) |
            Q(phone__icontains=search) |
            Q(id__icontains=search)
        )

    # Stats
    all_orders = Order.objects.all()
    stats = {
        'total_revenue': all_orders.aggregate(s=Sum('total_amount'))['s'] or 0,
        'pending_count': all_orders.filter(status='pending').count(),
        'today_count':   all_orders.filter(created_at__date=timezone.now().date()).count(),
        'total_count':   all_orders.count(),
        'delivered_count': all_orders.filter(status='delivered').count(),
    }

    paginator = Paginator(orders, 20)
    orders_page = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'admin_orders.html', {
        'orders': orders_page,
        'status_filter': status_filter,
        'search': search,
        'stats': stats,
        'status_choices': Order.STATUS_CHOICES,
    })


@staff_required
@require_POST
def update_order_status(request, order_id):
    order  = get_object_or_404(Order, id=order_id)
    status = request.POST.get('status', '')
    note   = request.POST.get('tracking_note', '').strip()

    if status in dict(Order.STATUS_CHOICES):
        order.status = status
        if note:
            order.tracking_note = note
        order.save(update_fields=['status', 'tracking_note', 'updated_at'])
        messages.success(request, f'✅ Order #{order_id} → {status}')
    else:
        messages.error(request, 'Invalid status।')

    return redirect('admin_orders')


# ─────────────────────────────────────────────
#  ADMIN — Reviews
# ─────────────────────────────────────────────

@staff_required
def admin_reviews(request):
    reviews = Review.objects.select_related('product', 'user').order_by('-created_at')
    pending = reviews.filter(approved=False).count()
    return render(request, 'admin_reviews.html', {
        'reviews': reviews,
        'pending_count': pending,
    })


@staff_required
def approve_review(request, review_id):
    review = get_object_or_404(Review, id=review_id)
    review.approved = not review.approved
    review.save(update_fields=['approved'])
    status = 'approved' if review.approved else 'unapproved'
    messages.success(request, f'Review {status}।')
    return redirect('admin_reviews')


# ─────────────────────────────────────────────
#  ADMIN — Coupons
# ─────────────────────────────────────────────

@staff_required
def manage_coupons(request):
    coupons = Coupon.objects.order_by('-id')
    active_count = coupons.filter(active=True).count()
    return render(request, 'manage_coupons.html', {
        'coupons': coupons,
        'active_count': active_count,
    })


@staff_required
def add_coupon(request):
    if request.method == 'POST':
        code           = request.POST.get('code', '').strip().upper()
        discount_type  = request.POST.get('discount_type', 'percent')
        discount_value = request.POST.get('discount_value', '10')
        min_order      = request.POST.get('min_order', '0')
        max_uses       = request.POST.get('max_uses', '100')
        expires_days   = request.POST.get('expires_days', '').strip()

        if not code:
            messages.error(request, 'Coupon code দিন।')
            return redirect('manage_coupons')

        if Coupon.objects.filter(code=code).exists():
            messages.error(request, f'"{code}" code আগেই আছে।')
            return redirect('manage_coupons')

        expires_at = (
            timezone.now() + datetime.timedelta(days=int(expires_days))
            if expires_days and expires_days.isdigit()
            else None
        )

        Coupon.objects.create(
            code=code,
            discount_type=discount_type,
            discount_value=discount_value,
            min_order=min_order,
            max_uses=max_uses,
            expires_at=expires_at,
        )
        messages.success(request, f'✅ Coupon "{code}" তৈরি হয়েছে!')

    return redirect('manage_coupons')


@staff_required
def delete_coupon(request, coupon_id):
    coupon = get_object_or_404(Coupon, id=coupon_id)
    if request.method == 'POST':
        coupon.delete()
        messages.success(request, '🗑️ Coupon মুছে ফেলা হয়েছে।')
    return redirect('manage_coupons')


# ─────────────────────────────────────────────
#  SSLCOMMERZ PAYMENT GATEWAY
# ─────────────────────────────────────────────

def _ssl_api_url(path, is_sandbox):
    """Return sandbox or live SSLCommerz API URL."""
    base = 'https://sandbox.sslcommerz.com' if is_sandbox else 'https://securepay.sslcommerz.com'
    return base + path


@require_POST
@rate_limit(max_calls=5, window_sec=60)   # 5 payment initiations per minute per IP
def ssl_initiate(request):
    """
    Called when user selects SSLCommerz on checkout.
    Creates a pending Order, then redirects to SSLCommerz payment page.
    """
    import requests as req
    from .models import SiteSettings

    site = SiteSettings.get()
    cart = request.session.get('cart', {})
    if not cart:
        messages.error(request, 'কার্ট খালি!')
        return redirect('cart')

    # ── Recalculate totals (same logic as checkout view) ──
    total = sum(float(i['price']) * i['quantity'] for i in cart.values())
    coupon_discount = float(request.session.get('coupon_discount', 0))
    final_total = max(0, total - coupon_discount)
    delivery = float(site.delivery_charge)
    grand_total = final_total + delivery

    # ── Customer info from POST ──
    name    = request.POST.get('name', '').strip()
    phone   = request.POST.get('phone', '').strip()
    address = request.POST.get('address', '').strip()
    district = request.POST.get('district', '').strip()
    note    = request.POST.get('note', '').strip()
    full_address = f"{address}, {district}" if district else address

    if not all([name, phone, address]):
        messages.error(request, 'সব required field পূরণ করুন।')
        return redirect('checkout')

    # ── Coupon validation ──
    coupon_code = request.session.get('coupon_code', '')
    coupon_obj = None
    if coupon_code:
        try:
            coupon_obj = Coupon.objects.get(code=coupon_code)
            valid, _ = coupon_obj.is_valid()
            if valid:
                coupon_obj.used_count += 1
                coupon_obj.save()
            else:
                coupon_obj = None
                coupon_discount = 0
        except Coupon.DoesNotExist:
            pass

    # ── Create pending order ──
    order = Order.objects.create(
        user=request.user if request.user.is_authenticated else None,
        customer_name=name,
        phone=phone,
        address=full_address,
        total_amount=grand_total,
        discount=coupon_discount,
        delivery_charge=delivery,
        coupon=coupon_obj,
        payment_method='sslcommerz',
        payment_status='unpaid',
        tracking_note=note,
        status='pending',
    )

    # Create order items
    for pid, item in cart.items():
        product = Product.objects.filter(id=pid).first()
        if product:
            OrderItem.objects.create(
                order=order,
                product=product,
                name=item.get('name', product.name),
                quantity=item['quantity'],
                price=item['price'],
            )
            product.stock = max(0, product.stock - item['quantity'])
            product.save(update_fields=['stock'])

    domain = get_site_domain(request)
    store_id   = settings.SSLCOMMERZ_STORE_ID
    store_pass = settings.SSLCOMMERZ_STORE_PASS
    is_sandbox = settings.SSLCOMMERZ_IS_SANDBOX

    payload = {
        'store_id':        store_id,
        'store_passwd':    store_pass,
        'total_amount':    str(round(grand_total, 2)),
        'currency':        'BDT',
        'tran_id':         order.order_id,
        'success_url':     f"{domain}/payment/success/",
        'fail_url':        f"{domain}/payment/fail/",
        'cancel_url':      f"{domain}/payment/cancel/",
        'ipn_url':         f"{domain}/payment/ipn/",
        'cus_name':        name,
        'cus_email':       f"{phone}@customer.pk",
        'cus_add1':        full_address,
        'cus_city':        district or 'Dhaka',
        'cus_country':     'Bangladesh',
        'cus_phone':       phone,
        'shipping_method': 'Courier',
        'ship_name':       name,
        'ship_add1':       full_address,
        'ship_city':       district or 'Dhaka',
        'ship_country':    'Bangladesh',
        'product_name':    'Practical Khata',
        'product_category': 'Books',
        'product_profile': 'physical-goods',
        'product_amount':   str(round(grand_total, 2)),
        'value_a':          str(order.id),   # Internal PK for success handler
    }

    try:
        resp = req.post(
            _ssl_api_url('/gwprocess/v4/api.php', is_sandbox),
            data=payload,
            timeout=15,
        )
        resp_data = resp.json()

        if resp_data.get('status') == 'SUCCESS':
            # Store order id in session for fail/cancel handlers
            request.session['ssl_pending_order_id'] = order.id
            # Clear cart only AFTER successful init (not on fail/cancel)
            return redirect(resp_data['GatewayPageURL'])
        else:
            order.payment_status = 'failed'
            order.save(update_fields=['payment_status'])
            messages.error(request, f"Payment gateway error: {resp_data.get('failedreason', 'Unknown')}")
            return redirect('checkout')

    except Exception as e:
        order.payment_status = 'failed'
        order.save(update_fields=['payment_status'])
        messages.error(request, 'Payment gateway-এ সংযোগ সমস্যা। পরে আবার চেষ্টা করুন।')
        return redirect('checkout')


def ssl_success(request):
    """SSLCommerz redirects here after successful payment."""
    import requests as req

    val_id   = request.POST.get('val_id') or request.GET.get('val_id', '')
    tran_id  = request.POST.get('tran_id') or request.GET.get('tran_id', '')  # = order.order_id
    amount   = request.POST.get('amount') or request.GET.get('amount', '0')
    bank_tran_id = request.POST.get('bank_tran_id') or request.GET.get('bank_tran_id', '')
    value_a  = request.POST.get('value_a') or request.GET.get('value_a', '')  # internal PK

    # Validate payment with SSLCommerz
    store_id   = settings.SSLCOMMERZ_STORE_ID
    store_pass = settings.SSLCOMMERZ_STORE_PASS
    is_sandbox = settings.SSLCOMMERZ_IS_SANDBOX

    validated = False
    try:
        verify_url = _ssl_api_url(
            f'/validator/api/validationserverAPI.php?val_id={val_id}&store_id={store_id}&store_passwd={store_pass}&format=json',
            is_sandbox
        )
        v_resp = req.get(verify_url, timeout=10).json()
        validated = (
            v_resp.get('status') == 'VALID' and
            v_resp.get('tran_id') == tran_id
        )
    except Exception:
        validated = False

    try:
        order = Order.objects.get(order_id=tran_id)
    except Order.DoesNotExist:
        # fallback: try internal pk from value_a
        try:
            order = Order.objects.get(id=int(value_a))
        except (Order.DoesNotExist, ValueError):
            return render(request, 'payment_fail.html', {'reason': 'অর্ডার পাওয়া যায়নি।'})

    if validated:
        order.payment_status    = 'paid'
        order.payment_ref       = val_id
        order.ssl_transaction_id = bank_tran_id
        order.status            = 'confirmed'
        order.save(update_fields=['payment_status', 'payment_ref', 'ssl_transaction_id', 'status', 'updated_at'])

        # Clear session
        request.session['cart'] = {}
        request.session['coupon_code'] = ''
        request.session['coupon_discount'] = 0
        request.session.pop('ssl_pending_order_id', None)

        return render(request, 'payment_success.html', {
            'order': order,
            'amount': amount,
        })
    else:
        order.payment_status = 'failed'
        order.save(update_fields=['payment_status', 'updated_at'])
        return render(request, 'payment_fail.html', {
            'order': order,
            'reason': 'Payment validation ব্যর্থ হয়েছে।',
        })


def ssl_fail(request):
    """SSLCommerz redirects here on payment failure."""
    tran_id = request.POST.get('tran_id') or request.GET.get('tran_id', '')
    value_a = request.POST.get('value_a') or request.GET.get('value_a', '')

    order = None
    try:
        order = Order.objects.get(order_id=tran_id)
    except Order.DoesNotExist:
        try:
            order = Order.objects.get(id=int(value_a))
        except (Order.DoesNotExist, ValueError):
            pass

    if order:
        order.payment_status = 'failed'
        order.save(update_fields=['payment_status', 'updated_at'])

    return render(request, 'payment_fail.html', {
        'order': order,
        'reason': 'Payment ব্যর্থ হয়েছে। আবার চেষ্টা করুন।',
    })


def ssl_cancel(request):
    """SSLCommerz redirects here on user-cancel."""
    tran_id = request.POST.get('tran_id') or request.GET.get('tran_id', '')
    value_a = request.POST.get('value_a') or request.GET.get('value_a', '')

    order = None
    try:
        order = Order.objects.get(order_id=tran_id)
    except Order.DoesNotExist:
        try:
            order = Order.objects.get(id=int(value_a))
        except (Order.DoesNotExist, ValueError):
            pass

    if order:
        order.payment_status = 'cancelled'
        order.status = 'cancelled'
        order.save(update_fields=['payment_status', 'status', 'updated_at'])

    return render(request, 'payment_cancel.html', {'order': order})


@require_POST
def ssl_ipn(request):
    """
    SSLCommerz IPN (Instant Payment Notification) — server-to-server.
    Verifies & updates order status even if browser-redirect fails.
    """
    import requests as req

    val_id      = request.POST.get('val_id', '')
    tran_id     = request.POST.get('tran_id', '')
    bank_tran_id = request.POST.get('bank_tran_id', '')
    status      = request.POST.get('status', '')

    if status not in ('VALID', 'VALIDATED'):
        return JsonResponse({'status': 'ignored'})

    store_id   = settings.SSLCOMMERZ_STORE_ID
    store_pass = settings.SSLCOMMERZ_STORE_PASS
    is_sandbox = settings.SSLCOMMERZ_IS_SANDBOX

    try:
        verify_url = _ssl_api_url(
            f'/validator/api/validationserverAPI.php?val_id={val_id}&store_id={store_id}&store_passwd={store_pass}&format=json',
            is_sandbox
        )
        v_resp = req.get(verify_url, timeout=10).json()
        if v_resp.get('status') in ('VALID', 'VALIDATED') and v_resp.get('tran_id') == tran_id:
            order = Order.objects.get(order_id=tran_id)
            if order.payment_status != 'paid':
                order.payment_status     = 'paid'
                order.payment_ref        = val_id
                order.ssl_transaction_id = bank_tran_id
                order.status             = 'confirmed'
                order.save(update_fields=['payment_status', 'payment_ref', 'ssl_transaction_id', 'status', 'updated_at'])
            return JsonResponse({'status': 'updated'})
    except Exception:
        pass

    return JsonResponse({'status': 'error'})


# ─────────────────────────────────────────────
#  AI CHAT
# ─────────────────────────────────────────────

@require_POST
@rate_limit(max_calls=20, window_sec=60)  # 20 chat messages per minute per IP
def ai_chat(request):
    """
    Smart rule-based chatbot with:
      - Dynamic data from SiteSettings & DB (no hardcoded prices)
      - Order status lookup by order_id
      - WhatsApp handoff signal
      - OpenAI hook (if OPENAI_API_KEY set)
      - Fallback graceful
    """
    from .models import SiteSettings
    try:
        payload  = json.loads(request.body.decode('utf-8'))
        question = payload.get('question', '').strip()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'error': 'invalid_payload'}, status=400)

    if not question:
        return JsonResponse({'answer': 'প্রশ্ন করুন। 😊'})
    if len(question) > 500:
        return JsonResponse({'answer': 'একটু ছোট করে লিখুন।'})

    site = SiteSettings.get()
    ql   = question.lower().strip()

    # ── 1. ORDER STATUS LOOKUP ────────────────────────────────
    # Detects: "আমার অর্ডার #PK-20260001", "order PK20260001", "track 20260001"
    order_id_match = re.search(r'(?:pk[-\s]?)?(\d{5,12})', ql)
    if order_id_match and any(w in ql for w in [
        'order', 'অর্ডার', 'track', 'status', 'কোথায়', 'পৌঁছায়নি', 'পেয়েছি', 'ডেলিভারি'
    ]):
        raw_id = order_id_match.group(1)
        try:
            order = Order.objects.get(order_id__icontains=raw_id)
            status_map = {
                'pending':    ('⏳', 'অপেক্ষায় আছে'),
                'confirmed':  ('✅', 'কনফার্ম হয়েছে'),
                'processing': ('⚙️', 'প্রস্তুত হচ্ছে'),
                'shipped':    ('🚚', 'পাঠানো হয়েছে'),
                'delivered':  ('📦', 'ডেলিভারি হয়েছে'),
                'cancelled':  ('❌', 'বাতিল হয়েছে'),
            }
            icon, label = status_map.get(order.status, ('📋', order.status))
            answer = (
                f"{icon} <strong>অর্ডার #{order.order_id}</strong>\n"
                f"স্ট্যাটাস: <strong>{label}</strong>\n"
                f"পণ্য: {order.items.count()}টি | মোট: ৳{int(order.total_price)}\n"
                f'<a href="/order/{order.id}/tracking/" '
                f'style="color:#00e5b0;text-decoration:none;">→ বিস্তারিত দেখুন</a>'
            )
            return JsonResponse({'answer': answer, 'html': True})
        except Order.DoesNotExist:
            return JsonResponse({
                'answer': f'❌ অর্ডার নম্বর <strong>{raw_id}</strong> পাওয়া যায়নি। '
                          f'সঠিক নম্বর দিন অথবা WhatsApp এ যোগাযোগ করুন।',
                'html': True,
                'whatsapp': True,
                'wa_number': site.whatsapp_number,
            })
        except Exception:
            pass

    # ── 2. OpenAI HOOK (premium fallback) ────────────────────
    openai_key = getattr(settings, 'OPENAI_API_KEY', '') or os.getenv('OPENAI_API_KEY', '')
    if openai_key:
        try:
            import requests as req
            # Build a concise system prompt with live site data
            sys_prompt = (
                f"তুমি {site.site_name}-এর AI সহকারী। "
                f"ডেলিভারি চার্জ ৳{int(site.delivery_charge)}। "
                f"bKash: {site.bkash_number or 'N/A'}, Nagad: {site.nagad_number or 'N/A'}। "
                f"WhatsApp: {site.whatsapp_number}। "
                f"শুধু বাংলায় উত্তর দাও। সংক্ষিপ্ত ও বিনয়ী থাকো।"
            )
            resp = req.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {openai_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-3.5-turbo",
                    "messages": [
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": question},
                    ],
                    "max_tokens": 200,
                    "temperature": 0.5,
                },
                timeout=12,
            )
            if resp.status_code == 200:
                answer = resp.json()['choices'][0]['message']['content'].strip()
                if answer:
                    return JsonResponse({'answer': answer})
        except Exception:
            pass  # silently fall through to rule-based

    # ── 3. SMART RULE-BASED ENGINE ────────────────────────────
    def match(words):
        return any(w in ql for w in words)

    # Greeting
    if match(['hello', 'hi', 'হ্যালো', 'হ্যালো', 'আসসালামু', 'salam', 'কেমন', 'ভালো']):
        answer = 'আসসালামু আলাইকুম! 👋 Practical Khata-তে স্বাগতম। কীভাবে সাহায্য করতে পারি?'

    # Delivery info
    elif match(['ডেলিভারি', 'delivery', 'পৌঁছাবে', 'কতদিন', 'shipping', 'কত সময়', 'কবে পাব']):
        answer = (
            f'🚚 ডেলিভারি চার্জ <strong>৳{int(site.delivery_charge)}</strong>।\n'
            f'অর্ডারের পরে ২-৩ কার্যদিবসে পৌঁছে যাবে।\n'
            f'ঢাকার বাইরে একটু বেশি সময় লাগতে পারে।'
        )
        return JsonResponse({'answer': answer, 'html': True})

    # Payment method
    elif match(['payment', 'পেমেন্ট', 'বিকাশ', 'bkash', 'nagad', 'নগদ', 'টাকা', 'pay', 'send money']):
        bkash  = site.bkash_number  or 'N/A'
        nagad  = site.nagad_number  or 'N/A'
        answer = (
            f'💳 পেমেন্ট করার নিয়ম:\n'
            f'• bKash: <strong>{bkash}</strong> (Send Money)\n'
            f'• Nagad: <strong>{nagad}</strong> (Send Money)\n'
            f'• Cash on Delivery ও আছে!\n'
            f'পেমেন্টের পরে TrxID WhatsApp এ পাঠাও।'
        )
        return JsonResponse({'answer': answer, 'html': True})

    # Coupon / discount
    elif match(['coupon', 'কুপন', 'discount', 'ছাড়', 'অফার', 'offer', 'code']):
        answer = '🎟️ কার্ট পেজে গিয়ে কুপন কোড বক্সে লিখলেই ছাড় পাবে! কুপন কোড না থাকলে WhatsApp এ জিজ্ঞেস করো।'

    # Order tracking (general, without ID)
    elif match(['track', 'ট্র্যাক', 'অর্ডার', 'order', 'কোথায়', 'status', 'পৌঁছায়নি']):
        answer = (
            '📦 অর্ডার ট্র্যাক করতে:\n'
            '১. Checkout এর পরে যে Order ID পেয়েছ সেটা লিখো\n'
            '২. এখানে লিখো: "আমার অর্ডার #PK-XXXXX"\n'
            '৩. অথবা <a href="/dashboard/" style="color:#00e5b0;">Dashboard</a> এ গিয়ে দেখো'
        )
        return JsonResponse({'answer': answer, 'html': True})

    # Return / complaint
    elif match(['return', 'ফেরত', 'problem', 'সমস্যা', 'ক্ষতিগ্রস্ত', 'ভুল', 'wrong', 'complaint', 'exchange']):
        answer = '🔄 কোনো সমস্যা হলে অর্ডারের ৪৮ ঘন্টার মধ্যে WhatsApp এ ছবি পাঠাও। আমরা দ্রুত সমাধান করব!'
        return JsonResponse({'answer': answer, 'whatsapp': True, 'wa_number': site.whatsapp_number})

    # Product info — SSC/HSC
    elif match(['ssc', 'hsc', 'class', 'শ্রেণী', 'বিজ্ঞান', 'physics', 'chemistry', 'biology', 'math']):
        answer = '📚 আমাদের কাছে SSC ও HSC উভয় স্তরের Practical Khata আছে। Physics, Chemistry, Biology, Math সব বিষয়ে।'

    # Quality / description
    elif match(['quality', 'মান', 'হাতের লেখা', 'handwriting', 'diagram', 'figure', 'কেমন']):
        answer = '✍️ সব খাতা Professional হাতের লেখায় তৈরি — Perfect Figure, Diagram ও Table সহ। Board পরীক্ষার জন্য Perfect!'

    # Price question (no order number)
    elif match(['দাম', 'price', 'কত', 'মূল্য', 'cost', 'rate']):
        try:
            cheapest = Product.objects.filter(stock__gt=0).order_by('price').first()
            price_str = f'৳{int(cheapest.current_price)} থেকে শুরু' if cheapest else 'বিভিন্ন রেঞ্জে'
        except Exception:
            price_str = 'বিভিন্ন রেঞ্জে'
        answer = (
            f'💰 খাতার দাম <strong>{price_str}</strong>।\n'
            f'<a href="/products/" style="color:#00e5b0;">সব খাতার দাম দেখতে এখানে ক্লিক করো →</a>'
        )
        return JsonResponse({'answer': answer, 'html': True})

    # WhatsApp contact
    elif match(['whatsapp', 'contact', 'যোগাযোগ', 'কথা বলব', 'সরাসরি', 'phone', 'নম্বর', 'কল']):
        answer = f'📞 সরাসরি কথা বলতে WhatsApp করো: <strong>{site.whatsapp_number}</strong>'
        return JsonResponse({'answer': answer, 'html': True, 'whatsapp': True, 'wa_number': site.whatsapp_number})

    # Fallback
    else:
        answer = (
            '😊 আমি সাহায্য করতে পারি:\n'
            '• 🚚 ডেলিভারি ও চার্জ\n'
            '• 💳 পেমেন্ট পদ্ধতি\n'
            '• 📦 অর্ডার ট্র্যাক করা\n'
            '• 🎟️ কুপন ও অফার\n'
            'কী জানতে চাও?'
        )
        return JsonResponse({'answer': answer, 'html': True})

    return JsonResponse({'answer': answer})


# ─────────────────────────────────────────────
#  ADMIN — Dashboard 2.0
# ─────────────────────────────────────────────

@staff_required
def admin_dashboard(request):
    """
    Admin super-dashboard with:
    - Revenue chart (last 30 days, Chart.js)
    - Order status distribution donut
    - Top-selling products
    - Low stock alerts
    - Customer insights (new users, total users, top buyers)
    """
    from django.db.models import DecimalField, ExpressionWrapper, F
    from django.db.models.functions import TruncDate

    now   = timezone.now()
    today = now.date()
    last_30 = today - datetime.timedelta(days=29)

    # ── Revenue / Orders: last 30 days ──────────────────────────
    daily_qs = (
        Order.objects
        .filter(created_at__date__gte=last_30)
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(revenue=Sum('total_amount'), count=Count('id'))
        .order_by('day')
    )

    # Fill in zero-value days so chart has a complete 30-day series
    day_map = {row['day']: row for row in daily_qs}
    chart_labels, chart_revenue, chart_orders = [], [], []
    for i in range(30):
        d = last_30 + datetime.timedelta(days=i)
        row = day_map.get(d, {})
        chart_labels.append(d.strftime('%d %b'))
        chart_revenue.append(float(row.get('revenue') or 0))
        chart_orders.append(row.get('count', 0))

    # ── Status distribution ──────────────────────────────────────
    status_qs = (
        Order.objects.values('status')
        .annotate(total=Count('id'))
        .order_by('status')
    )
    status_labels = [s['status'].title() for s in status_qs]
    status_counts = [s['total'] for s in status_qs]

    # ── Top-selling products (last 30 days) ──────────────────────
    top_products = (
        OrderItem.objects
        .filter(order__created_at__date__gte=last_30)
        .values('product__name', 'product__id')
        .annotate(
            units=Sum('quantity'),
            revenue=Sum(ExpressionWrapper(
                F('quantity') * F('price'),
                output_field=DecimalField()
            ))
        )
        .order_by('-units')[:8]
    )

    # ── Overall KPIs ─────────────────────────────────────────────
    all_orders = Order.objects.all()
    kpi = {
        'total_revenue':      all_orders.aggregate(s=Sum('total_amount'))['s'] or 0,
        'today_revenue':      all_orders.filter(created_at__date=today).aggregate(s=Sum('total_amount'))['s'] or 0,
        'this_month_revenue': all_orders.filter(
            created_at__year=now.year, created_at__month=now.month
        ).aggregate(s=Sum('total_amount'))['s'] or 0,
        'total_orders':  all_orders.count(),
        'today_orders':  all_orders.filter(created_at__date=today).count(),
        'pending':       all_orders.filter(status='pending').count(),
        'delivered':     all_orders.filter(status='delivered').count(),
        'cancelled':     all_orders.filter(status='cancelled').count(),
        'paid_orders':   all_orders.filter(payment_status='paid').count(),
    }

    # ── Low-stock products ────────────────────────────────────────
    low_stock = Product.objects.filter(stock__lte=5).order_by('stock').select_related('category')[:10]

    # ── Customer insights ─────────────────────────────────────────
    total_users  = User.objects.count()
    new_users_30 = User.objects.filter(date_joined__date__gte=last_30).count()
    top_buyers = (
        Order.objects.filter(user__isnull=False)
        .values('user__username', 'user__id')
        .annotate(orders=Count('id'), spent=Sum('total_amount'))
        .order_by('-spent')[:5]
    )

    # ── Recent orders (last 10) ───────────────────────────────────
    recent_orders = all_orders.prefetch_related('items__product').order_by('-created_at')[:10]

    return render(request, 'admin_dashboard.html', {
        'kpi':            kpi,
        'chart_labels':   json.dumps(chart_labels),
        'chart_revenue':  json.dumps(chart_revenue),
        'chart_orders':   json.dumps(chart_orders),
        'status_labels':  json.dumps(status_labels),
        'status_counts':  json.dumps(status_counts),
        'top_products':   top_products,
        'low_stock':      low_stock,
        'total_users':    total_users,
        'new_users_30':   new_users_30,
        'top_buyers':     top_buyers,
        'recent_orders':  recent_orders,
        'status_choices': Order.STATUS_CHOICES,
    })


@staff_required
def export_orders_csv(request):
    """Download all (or filtered) orders as CSV with BOM for Excel/Bangla."""
    import csv
    from django.http import HttpResponse

    status_filter = request.GET.get('status', '')
    date_from     = request.GET.get('from', '')
    date_to       = request.GET.get('to', '')

    orders = Order.objects.prefetch_related('items__product').order_by('-created_at')
    if status_filter:
        orders = orders.filter(status=status_filter)
    if date_from:
        try:
            orders = orders.filter(created_at__date__gte=datetime.date.fromisoformat(date_from))
        except ValueError:
            pass
    if date_to:
        try:
            orders = orders.filter(created_at__date__lte=datetime.date.fromisoformat(date_to))
        except ValueError:
            pass

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    fname    = f"orders_{timezone.now().strftime('%Y%m%d_%H%M')}.csv"
    response['Content-Disposition'] = f'attachment; filename="{fname}"'

    # UTF-8 BOM so Excel opens Bangla chars correctly
    response.write('\ufeff')
    writer = csv.writer(response)
    writer.writerow([
        'Order ID', 'Internal ID', 'Date', 'Customer', 'Phone', 'Address',
        'Items', 'Discount', 'Delivery', 'Total',
        'Payment Method', 'Payment Status', 'Order Status',
        'SSL TxnID', 'Note',
    ])
    for order in orders:
        items_str = ' | '.join(
            f"{i.name} x{i.quantity} @{i.price}" for i in order.items.all()
        )
        writer.writerow([
            order.order_id or '',
            order.id,
            order.created_at.strftime('%Y-%m-%d %H:%M'),
            order.customer_name,
            order.phone,
            order.address,
            items_str,
            order.discount,
            order.delivery_charge,
            order.total_amount,
            order.payment_method,
            order.payment_status,
            order.status,
            order.ssl_transaction_id or '',
            order.tracking_note or '',
        ])
    return response


@staff_required
@require_POST
def update_order_status_ajax(request, order_id):
    """AJAX JSON status update — used by kanban drag-drop."""
    order  = get_object_or_404(Order, id=order_id)
    status = request.POST.get('status', '')
    note   = request.POST.get('tracking_note', '').strip()

    if status not in dict(Order.STATUS_CHOICES):
        return JsonResponse({'success': False, 'error': 'Invalid status'}, status=400)

    order.status = status
    if note:
        order.tracking_note = note
    order.save(update_fields=['status', 'tracking_note', 'updated_at'])

    return JsonResponse({
        'success':      True,
        'order_id':     order.id,
        'order_ref':    order.order_id or f'#{order.id}',
        'status':       status,
        'status_label': order.get_status_display(),
    })