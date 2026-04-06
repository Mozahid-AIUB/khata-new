# 🎮 Practical Khata — Master Project Guide
> **Last Updated:** Session 4 — base.html, AI Chat, Flash Sale, SEO
> **Server:** ✅ Running at 127.0.0.1:8000
> **Status:** 🟡 In Progress

---

## 📊 Progress Tracker

| Task | Status | Notes |
|------|--------|-------|
| Django Setup | ✅ Done | khata-new |
| Templates | ✅ Done | 13 HTML files |
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
| admin_orders.html | ⚠️ Minor | stats variable names updated needed |
| products.html | ⚠️ Todo | Needs pagination UI |
| home.html | ⚠️ Todo | Flash sale section needed |
| product_detail.html | ❌ Missing | Not created yet |
| sitemap.xml | ❌ Todo | |
| robots.txt | ❌ Todo | |
| Email notification | ❌ Todo | Phase 2 |
| Railway Deploy | ❌ Todo | Phase 4 |

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
│   ├── dashboard.html  ✅ good (needs stats display)
│   ├── login.html      ✅ good
│   ├── register.html   ✅ good
│   ├── order_tracking.html ✅ good
│   ├── admin_orders.html   ⚠️ stats var name fix needed
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

## ❌ Known Issues / Bugs

| Issue | File | Fix |
|-------|------|-----|
| admin_orders stats var | admin_orders.html | stats.pending_count not pending_count |
| add_product.html empty | templates/ | needs form |
| product_detail.html missing | templates/ | needs creation |
| products.html no pagination | products.html | needs page navigation |
| dashboard stats not shown | dashboard.html | stats.total_orders etc |
| order.final_amount() removed | dashboard/tracking | use order.grand_total |

---

## 🚀 Next Steps (In Order)

1. **Fix bugs** — admin_orders stats, dashboard stats
2. **product_detail.html** — create from scratch
3. **add_product.html** — fill in form
4. **products.html** — add pagination UI
5. **home.html** — add Flash Sale section
6. **sitemap.xml + robots.txt** — SEO
7. **Railway Deploy** — production

---

## 💬 New Conversation এ বলো
> "এই README দেখো। Session 4 শেষ।
> এখন [next step] করতে চাই।"