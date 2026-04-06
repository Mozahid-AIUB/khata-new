from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.cache import cache_page
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Count, Avg
from django.utils import timezone
from django.conf import settings
from .models import Product, Category, Order, OrderItem, Coupon, Review
import os, re, json, unicodedata, datetime

# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def staff_required(view_func):
    """Staff only decorator — non-staff gets redirected to login."""
    decorated = user_passes_test(
        lambda u: u.is_active and u.is_staff,
        login_url='/login/?next=/'
    )(view_func)
    return login_required(decorated)


def get_site_domain(request):
    """Return current site domain dynamically."""
    return f"{request.scheme}://{request.get_host()}"


# ─────────────────────────────────────────────
#  HOME & PRODUCTS
# ─────────────────────────────────────────────

def home(request):
    featured = Product.objects.filter(featured=True, stock__gt=0).select_related('category')[:6]
    categories = Category.objects.annotate(product_count=Count('products')).filter(product_count__gt=0)
    flash_sale = Product.objects.filter(
        sale_price__isnull=False,
        sale_ends_at__gt=timezone.now(),
        stock__gt=0
    ).select_related('category')[:4] if hasattr(Product, 'sale_price') else []

    return render(request, 'home.html', {
        'featured_products': featured,
        'categories': categories,
        'flash_sale_products': flash_sale,
    })


def product_list(request, category_slug=None):
    products = Product.objects.filter(stock__gt=0).select_related('category').order_by('-created_at')
    categories = Category.objects.annotate(product_count=Count('product'))
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
        'products': products_page,
        'categories': categories,
        'current_category': current_category,
        'level_filter': level,
        'sort': sort,
        'total_count': paginator.count,
    })


def product_detail(request, slug):
    product = get_object_or_404(Product.objects.select_related('category'), slug=slug)
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
    else:
        cart[pid] = {
            'name': product.name,
            'price': float(product.price),
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
    cart = request.session.get('cart', {})
    pid = str(product_id)
    cart.pop(pid, None)
    request.session['cart'] = cart

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        total = sum(float(i['price']) * i['quantity'] for i in cart.values())
        return JsonResponse({
            'success': True,
            'cart_count': sum(i['quantity'] for i in cart.values()),
            'total': total,
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
        elif product:
            cart[pid] = {
                'name': product.name,
                'price': float(product.price),
                'quantity': quantity,
                'image': product.image.url if product.image else None,
                'slug': product.slug,
                'level': product.level,
            }

    request.session['cart'] = cart
    item_subtotal = float(cart[pid]['price']) * cart[pid]['quantity'] if pid in cart else 0
    total = sum(float(i['price']) * i['quantity'] for i in cart.values())

    return JsonResponse({
        'success': True,
        'cart_count': sum(i['quantity'] for i in cart.values()),
        'item_subtotal': item_subtotal,
        'total': total,
    })


def cart_view(request):
    cart = request.session.get('cart', {})
    total = 0
    for item in cart.values():
        item['price'] = float(item['price'])
        item['subtotal'] = item['price'] * item['quantity']
        total += item['subtotal']

    coupon_discount = float(request.session.get('coupon_discount', 0))
    coupon_code = request.session.get('coupon_code', '')
    final_total = max(0, total - coupon_discount)

    return render(request, 'cart.html', {
        'cart': cart,
        'total': total,
        'coupon_discount': coupon_discount,
        'coupon_code': coupon_code,
        'final_total': final_total,
        'delivery_charge': 110,
        'grand_total': final_total + 110,
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

def checkout(request):
    cart = request.session.get('cart', {})
    if not cart:
        messages.warning(request, 'কার্ট খালি!')
        return redirect('products')

    total = sum(float(i['price']) * i['quantity'] for i in cart.values())
    coupon_discount = float(request.session.get('coupon_discount', 0))
    coupon_code = request.session.get('coupon_code', '')
    final_total = max(0, total - coupon_discount)
    delivery = 110
    grand_total = final_total + delivery

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        phone = request.POST.get('phone', '').strip()
        address = request.POST.get('address', '').strip()

        if not all([name, phone, address]):
            messages.error(request, 'সব field পূরণ করুন।')
            return render(request, 'checkout.html', {
                'cart': cart, 'total': total,
                'coupon_discount': coupon_discount,
                'final_total': final_total,
                'delivery': delivery,
                'grand_total': grand_total,
            })

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
            address=address,
            total_amount=grand_total,
            discount=coupon_discount,
            coupon=coupon_obj,
        )

        # Create order items + reduce stock
        for pid, item in cart.items():
            product = Product.objects.filter(id=pid).first()
            if product:
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=item['quantity'],
                    price=item['price'],
                )
                # Reduce stock
                product.stock = max(0, product.stock - item['quantity'])
                product.save(update_fields=['stock'])

        # Clear session
        request.session['cart'] = {}
        request.session['coupon_code'] = ''
        request.session['coupon_discount'] = 0

        # Build WhatsApp message
        domain = get_site_domain(request)
        items_text = '%0A'.join([
            f"• {i['name']} ×{i['quantity']} = ৳{int(float(i['price']) * i['quantity'])}"
            for i in cart.values()
        ])
        wa_msg = (
            f"আসসালামু আলাইকুম!%0A"
            f"🛒 নতুন অর্ডার #{order.id}%0A"
            f"━━━━━━━━━━━━━━%0A"
            f"👤 নাম: {name}%0A"
            f"📱 ফোন: {phone}%0A"
            f"📍 ঠিকানা: {address}%0A%0A"
            f"📦 পণ্য:%0A{items_text}%0A%0A"
            f"━━━━━━━━━━━━━━%0A"
            f"Subtotal: ৳{int(total)}%0A"
            f"Discount: ৳{int(coupon_discount)}%0A"
            f"Delivery: ৳{delivery}%0A"
            f"💰 মোট: ৳{int(grand_total)}%0A%0A"
            f"🔗 Tracking: {domain}/order/{order.id}/tracking/"
        )
        return redirect(f"https://wa.me/8801707591255?text={wa_msg}")

    for item in cart.values():
        item['price'] = float(item['price'])
        item['subtotal'] = item['price'] * item['quantity']

    return render(request, 'checkout.html', {
        'cart': cart,
        'total': total,
        'coupon_discount': coupon_discount,
        'coupon_code': coupon_code,
        'final_total': final_total,
        'delivery': delivery,
        'grand_total': grand_total,
    })


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
        'total_spent': orders.aggregate(s=Sum('total_amount'))['s'] or 0,
        'pending': orders.filter(status='pending').count(),
        'delivered': orders.filter(status='delivered').count(),
    }

    return render(request, 'dashboard.html', {
        'orders': orders,
        'stats': stats,
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
#  AI CHAT
# ─────────────────────────────────────────────

@require_POST
def ai_chat(request):
    try:
        payload  = json.loads(request.body.decode('utf-8'))
        question = payload.get('question', '').strip()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'error': 'invalid_payload'}, status=400)

    if not question:
        return JsonResponse({'answer': 'প্রশ্ন করুন।'})

    if len(question) > 500:
        return JsonResponse({'answer': 'প্রশ্ন বেশি লম্বা। সংক্ষেপে লিখুন।'})

    # Try HuggingFace
    hf_key = getattr(settings, 'HUGGINGFACE_API_KEY', '') or os.getenv('HUGGINGFACE_API_KEY', '')
    if hf_key:
        try:
            import requests as req
            resp = req.post(
                "https://router.huggingface.co/hf-inference/models/google/flan-t5-small",
                headers={"Authorization": f"Bearer {hf_key}"},
                json={"inputs": question, "parameters": {"max_new_tokens": 200},
                      "options": {"wait_for_model": True}},
                timeout=15,
            )
            if resp.status_code == 200:
                result = resp.json()
                answer = ''
                if isinstance(result, list) and result:
                    answer = result[0].get('generated_text', '').strip()
                elif isinstance(result, dict):
                    answer = result.get('generated_text', '').strip()
                if answer:
                    return JsonResponse({'answer': answer})
        except Exception:
            pass  # Fallback to rule-based

    # Rule-based fallback
    ql = question.lower()
    if any(w in ql for w in ['ডেলিভারি', 'delivery', 'পৌঁছাবে', 'কতদিন']):
        answer = '🚚 ডেলিভারি চার্জ ৳১১০। অর্ডারের ২-৩ কার্যদিবসে পৌঁছাবে।'
    elif any(w in ql for w in ['দাম', 'price', 'কত', 'মূল্য']):
        answer = '💰 খাতার দাম ৳২৯০ থেকে শুরু। Products page এ সব দাম দেখতে পাবে।'
    elif any(w in ql for w in ['coupon', 'কুপন', 'discount', 'ছাড়']):
        answer = '🎟️ Cart page এ কুপন কোড enter করলে ছাড় পাবে!'
    elif any(w in ql for w in ['track', 'অর্ডার', 'order', 'কোথায়', 'status']):
        answer = '📦 Checkout এর পরে Order Tracking link পাবে। সেখানে live status দেখতে পারবে।'
    elif any(w in ql for w in ['payment', 'পেমেন্ট', 'বিকাশ', 'bkash', 'nagad', 'নগদ']):
        answer = '📱 bKash/Nagad: 01707591255। Send Money → Screenshot WhatsApp এ পাঠাও।'
    elif any(w in ql for w in ['return', 'ফেরত', 'problem', 'সমস্যা', 'ক্ষতিগ্রস্ত']):
        answer = '🔄 কোনো সমস্যা হলে WhatsApp এ জানান। আমরা দ্রুত সমাধান করব!'
    elif any(w in ql for w in ['hello', 'hi', 'হ্যালো', 'আসসালামু', 'salam']):
        answer = 'আসসালামু আলাইকুম! 👋 Practical Khata তে স্বাগতম। কীভাবে সাহায্য করতে পারি?'
    elif any(w in ql for w in ['ssc', 'hsc', 'class', 'শ্রেণী']):
        answer = '📚 আমাদের কাছে SSC ও HSC উভয় স্তরের Practical Khata পাওয়া যায়।'
    elif any(w in ql for w in ['quality', 'মান', 'হাতের লেখা', 'handwriting']):
        answer = '✍️ সব খাতা Professional হাতের লেখায় তৈরি। Perfect Figure ও Diagram সহ।'
    else:
        answer = '😊 ডেলিভারি, অর্ডার, দাম, কুপন — সব বিষয়ে সাহায্য করতে পারি। কী জানতে চান?'

    return JsonResponse({'answer': answer})