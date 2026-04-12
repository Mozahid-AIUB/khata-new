# 🎮 Practical Khata — Master Project Guide
> **Last Updated:** Session 5 — Phase 1 Bug Fix Complete
> **Server:** ✅ Running at 127.0.0.1:8000
> **Status:** 🟡 In Progress

---

## 📊 Progress Tracker

| Task | Status | Notes |
|------|--------|-------|
| Django Setup | ✅ Done | khata-new |
| Templates | ✅ Done | 14 HTML files (product_detail added) |
| Static CSS | ✅ Done | 856 line optimized |
| Static JS | ✅ Done | animations.js, cart.js |
| settings.py | ✅ Done | ADMIN_URL, security headers |
| urls.py | ✅ Done | Hidden admin, fake 404 |
| models.py v2 | ✅ Done | 10 models total |
| views.py v2 | ✅ Done | Pagination, stock, security |
| admin.py v2 | ✅ Done | All models, thumbnails, badges |
| context_processors | ✅ Done | cart_count + site_settings |
| base.html v2 | ✅ Done | AI chat, SEO, Flash Sale, dynamic WA |
| AI Chat Widget | ✅ Done | Floating bubble, quick replies, typing |
| Flash Sale Banner | ✅ Done | Dynamic countdown from DB |
| SEO Meta Tags | ✅ Done | Dynamic from SiteSettings |
| Dynamic Footer | ✅ Done | WA number, bKash, Nagad from DB |
| Active Nav Links | ✅ Done | Highlights current page |
| **admin_orders.html** | ✅ **FIXED** | stats.pending_count, stats.today_count, stats.total_revenue |
| **dashboard.html** | ✅ **FIXED** | stats display working perfectly |
| **product_detail.html** | ✅ **CREATED** | Full page with reviews, related products, AJAX cart |
| products.html | ⚠️ Todo | Needs pagination UI |
| home.html | ⚠️ Todo | Flash sale section needed |
| add_product.html | ⚠️ Empty | needs form |
| sitemap.xml | ❌ Todo | |
| robots.txt | ❌ Todo | |
| Email notification | ❌ Todo | Phase 2 |
| Railway Deploy | ❌ Todo | Phase 4 |

---

## ✅ Session 5.2 — product_detail.html তৈরি সম্পন্ন 🎉

### 📄 **product_detail.html Features:**
| Feature | Details |
|---------|---------|
| Product Grid | Sticky image + scrollable info |
| Image Gallery | Main image + thumbnails (if extra_images exist) |
| Dynamic Pricing | Sale price with discount percentage |
| Stock Status | In stock / Low stock / Out of stock badges |
| Reviews System | Customer reviews + rating stars |
| Review Form | Submit review with name + rating + comment |
| Related Products | Shows 4 similar products from same category |
| AJAX Add to Cart | No page reload, instant feedback |
| Breadcrumb Nav | Home > Products > Category > Product |
| Delivery Info | FREE delivery, timing, payment methods |
| WhatsApp Button | Direct order link with product details |
| Responsive Design | Mobile-optimized grid & buttons |

### 🎨 **Design Elements:**
```
✅ Consistent with home.html design system
✅ Dark theme with neon accents
✅ Smooth animations & transitions
✅ Glass-morphism cards
✅ Gradient price display
✅ Star ratings with glow effect
✅ Sticky image section on desktop
✅ Professional typography
```

### 🔧 **Technical Features:**
```javascript
- changeImage(src, thumb) // Thumbnail switching
- addToCartDetail(productId) // AJAX cart addition
- Image lazy loading
- Form validation
- CSRF token handling
```

---

## ✅ Session 5 — Phase 1 Bug Fix Complete

### 🐛 Bugs Fixed:
| File | Issue | Solution |
|------|-------|----------|
| admin_orders.html | `{{ pending_count }}` → ❌ | ✅ `{{ stats.pending_count }}` |
| admin_orders.html | `{{ today_orders }}` → ❌ | ✅ `{{ stats.today_count }}` |
| admin_orders.html | `{{ total_revenue }}` → ❌ | ✅ `{{ stats.total_revenue }}` |
| admin_orders.html | `{{ order.final_amount }}` → ❌ | ✅ `{{ order.total_amount }}` |
| dashboard.html | ✅ Already perfect | No changes needed |

### 📝 Changes Made:
```diff
- {{ pending_count }}
+ {{ stats.pending_count }}

- {{ today_orders }}
+ {{ stats.today_count }}

- {{ total_revenue }}
+ {{ stats.total_revenue }}

- {{ order.final_amount|floatformat:0 }}
+ {{ order.total_amount|floatformat:0 }}
```

---

## ✅ Session 4 — What Was Done

### base.html v2 — Full Upgrade
| Feature | Details |
|---------|---------|
| Dynamic SEO | meta title/desc/og from SiteSettings model |
| Flash Sale Banner | Live countdown timer from FlashSale DB |
| AI Chat Widget | Floating bubble, typing indicator, quick replies |
| Dynamic WhatsApp | Number from SiteSettings (not hardcoded) |
| Dynamic Footer | Name, tagline, WA, bKash, Nagad from DB |
| Active Nav | Highlights current page link |
| Vercel script removed | Was causing 404 error |
| CSRF in AI chat | Proper token injection |

### AI Chat Features
- Floating bubble (bottom-right, left of WhatsApp button)
- Typing indicator (3 bouncing dots)
- Quick reply buttons (Delivery, Price, Payment, Tracking)
- Unread badge (shows after 3 seconds)
- Smooth open/close animation
- Logs to SupportMessage model
- Mobile responsive

---

## 🗂️ Project Structure (Current)

```
khata-new/
├── config/
│   ├── settings.py     ✅ ADMIN_URL, security, site_settings context
│   ├── urls.py         ✅ Hidden admin
│   └── wsgi.py
├── core/
│   ├── migrations/     ✅ up to date
│   ├── admin.py        ✅ v2 all models
│   ├── context_processors.py  ✅ cart + site_settings + flash_sale
│   ├── models.py       ✅ v2 — 10 models
│   ├── urls.py         ✅ all routes
│   └── views.py        ✅ v2 — secure, paginated
├── templates/
│   ├── base.html       ✅ v2 — AI chat, SEO, Flash Sale
│   ├── home.html       ⚠️ needs Flash Sale section
│   ├── products.html   ⚠️ needs pagination UI
│   ├── cart.html       ✅ good
│   ├── checkout.html   ✅ good
│   ├── dashboard.html  ✅ FIXED — stats working
│   ├── login.html      ✅ good
│   ├── register.html   ✅ good
│   ├── order_tracking.html ✅ good
│   ├── admin_orders.html   ✅ FIXED — all stats working
│   ├── admin_reviews.html  ✅ good
│   ├── manage_coupons.html ✅ good
│   ├── manageProduct.html  ✅ good
│   ├── add_product.html    ⚠️ empty — needs content
│   └── product_detail.html ❌ missing — needs creation
├── static/
│   ├── css/style.css   ✅ 856 line
│   └── js/             ✅ animations + cart
├── media/
├── .env                ✅ ADMIN_URL set
└── db.sqlite3
```

---

## 🔐 Security

```
/admin/              → 404 (fake)
/secret-admin-2024/  → Real admin (change in .env)

User roles:
- Superuser  → everything
- Staff      → admin panel + manage views (@staff_required)
- Auth user  → dashboard (@login_required)
- Guest      → shop only
```

---

## ✅ Phase 1 Complete! 🎉
## ✅ Phase 2 (Part 1) Complete! 🎉

**Dashboard**, **Admin Orders**, এবং **product_detail.html** — সব ঠিক আছে!

---

## 🚀 Next Steps (In Order)

### 🟢 **Phase 2 (Part 2): Remaining Template**
1. **add_product.html** — fill in form (Admin এর জন্য)

### 🟡 **Phase 3: UI Polish**
2. **products.html** — add pagination UI
3. **home.html** — add Flash Sale section

### 🔵 **Phase 4: SEO & Deploy**
4. **sitemap.xml + robots.txt** — SEO
5. **Railway Deploy** — production

---

## 💬 এখন কী করবে?

বলো:
- **"Phase 2 শুরু করি"** → product_detail.html তৈরি করবো
- **"Phase 3"** → pagination আর flash sale section
- **"অন্য কিছু"** → তোমার ইচ্ছা

---

## 📌 Important Notes:

### Stats Variables (views.py থেকে):
```python
# dashboard view (line 342-347)
stats = {
    'total_orders': ...,
    'total_spent': ...,
    'pending': ...,
    'delivered': ...,
}

# admin_orders view (line 465-471)
stats = {
    'total_revenue': ...,
    'pending_count': ...,
    'today_count': ...,
    'total_count': ...,
    'delivered_count': ...,
}
```

### Order Model Fields:
- `order.total_amount` ✅ (exists)
- `order.grand_total` ✅ (calculated in checkout)
- `order.final_amount()` ❌ (removed, don't use)

# 📚 Practical Khata — Project Guide
> **Last Updated:** Session 8
> **Status:** 🟢 Core Complete — Deploy Ready

---

## 📊 Progress

| Task | Status |
|------|--------|
| Django + models | ✅ |
| All views | ✅ |
| base.html (AI chat, SEO, Flash Sale) | ✅ |
| AI Chat (typewriter, Bangla) | ✅ |
| product_detail.html | ✅ |
| dashboard, admin_orders, reviews | ✅ |
| manage products `/manage/` | ✅ |
| **add_product.html** | ✅ **Done this session** |
| **products.html + pagination** | ✅ **Done this session** |
| home.html Flash Sale section | ⚠️ |
| sitemap.xml + robots.txt | ❌ |
| Railway Deploy | ❌ |

---

## 🆕 Session 8 — What's New

### add_product.html ✅
- Live slug preview from product name
- Drag & drop image upload with preview
- Real-time character counter for description
- Stock warning (low/zero)
- Toggle switch for featured
- Loading state on submit
- Sale price field

### products.html ✅
- Advanced filter bar (All / SSC / HSC / Category)
- Sort dropdown (newest, price asc/desc, popular)
- Search bar with URL state
- Hover overlay with quick cart + view buttons
- Sale badge + low stock + out of stock badges
- Smart pagination with ellipsis
- Toast notification on cart add
- AJAX add to cart (no page reload)
- Empty state with staff shortcut

---

## 🏗️ File Locations

```
core/templates/
├── base.html          ✅ (chatbot, SEO, navbar)
├── home.html          ⚠️ (needs flash sale)
├── products.html      ✅ NEW — replace this
├── product_detail.html ✅
├── add_product.html   ✅ NEW — replace this
├── manageProduct.html ✅
├── cart.html          ✅
├── checkout.html      ✅
├── dashboard.html     ✅
├── admin_orders.html  ✅
├── admin_reviews.html ✅
├── manage_coupons.html ✅
└── (login, register, order_tracking, etc.)

⚠️ RULE: NEVER put files in templates/ (root)
         Always use core/templates/
```

---

## 🔐 Access URLs

```
/                        → Home
/products/               → All products (new pagination)
/manage/                 → Product management (staff)
/manage/add/             → Add product (staff) — NEW form
/manage/orders/          → Orders (staff)
/login/                  → Login (NOT /accounts/login/)
/AdminMozahid2026/       → Django Admin
```

---

## 🤖 AI Chat

```python
# Enable/disable via shell:
from core.models import SiteSettings
s = SiteSettings.get()
s.chat_enabled = True
s.save()

# Typewriter speed (base.html):
const speed = 25  # ms per char — lower = faster
```

---

## 🚀 Next Steps

### Priority 1 — Quick wins
1. `home.html` Flash Sale section

### Priority 2 — SEO
2. `sitemap.xml`
3. `robots.txt`

### Priority 3 — Deploy 🚀
4. Railway deploy
   - `requirements.txt` update
   - `Procfile` create
   - PostgreSQL setup
   - Static files (whitenoise)

### Future — After deploy
5. React frontend (proper setup with Django REST API)
6. Email notifications for orders
7. Analytics dashboard