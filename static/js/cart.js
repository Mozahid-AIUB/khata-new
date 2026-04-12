// ═══════════════════════════════════════════════════════
//  🛒 CART.JS — v3 | Drawer + localStorage + Bug Fixes
//  ✅ No code duplication — all helpers defined ONCE
//  ✅ Hardcoded +110 bug fixed → uses server grand_total
//  ✅ Cart drawer: slide-in, AJAX-populated, localStorage
// ═══════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', function () {

    // ══════════════════════════════════════
    //  🔧 HELPERS (defined once, used everywhere)
    // ══════════════════════════════════════

    function getCookie(name) {
        const v = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
        return v ? v.pop() : '';
    }

    function showToast(msg, type) {
        const colors = {
            success: 'rgba(0,229,176,0.92)',
            error:   'rgba(244,114,182,0.92)',
            info:    'rgba(91,127,255,0.92)'
        };
        const t = document.createElement('div');
        t.textContent = msg;
        t.style.cssText = `
            position:fixed; top:80px; right:20px;
            background:${colors[type] || colors.info};
            color:#fff; padding:10px 18px; border-radius:10px;
            font-size:0.85rem; font-weight:600;
            box-shadow:0 4px 20px rgba(0,0,0,0.3);
            z-index:99999; opacity:0;
            transition:opacity 0.3s ease, right 0.3s ease;
        `;
        document.body.appendChild(t);
        setTimeout(() => { t.style.opacity = 1; t.style.right = '24px'; }, 50);
        setTimeout(() => {
            t.style.opacity = 0;
            setTimeout(() => t.remove(), 350);
        }, 2500);
    }

    function updateCartBadge(count) {
        // Update nav badge
        let badge = document.querySelector('.cart-nav-badge');
        const link = document.querySelector('.nav-link[href*="cart"]');
        if (link) {
            if (!badge) {
                badge = document.createElement('span');
                badge.className = 'cart-nav-badge';
                badge.style.cssText = `
                    background:linear-gradient(135deg,#f472b6,#ec4899);
                    color:white; font-size:0.65rem; font-weight:700;
                    padding:1px 6px; border-radius:10px; line-height:1.6;
                    margin-left:2px;
                `;
                link.appendChild(badge);
            }
            badge.textContent = count;
            badge.style.display = count > 0 ? 'inline' : 'none';
        }
        // Update drawer badge
        const drawerBadge = document.querySelector('.cart-drawer-badge');
        if (drawerBadge) {
            drawerBadge.textContent = count;
            drawerBadge.style.display = count > 0 ? 'flex' : 'none';
        }
        // localStorage backup for instant display on next page load
        try { localStorage.setItem('cartCount', count); } catch(e) {}
    }

    function flyToCart(btn) {
        const cartLink = document.querySelector('.nav-link[href*="cart"]');
        if (!cartLink) return;
        const bRect = btn.getBoundingClientRect();
        const cRect = cartLink.getBoundingClientRect();
        const dot = document.createElement('div');
        dot.style.cssText = `
            position:fixed;
            left:${bRect.left + bRect.width/2 - 6}px;
            top:${bRect.top + bRect.height/2 - 6}px;
            width:12px; height:12px; border-radius:50%;
            background:linear-gradient(135deg,#5b7fff,#00e5b0);
            z-index:99999; pointer-events:none;
            transition:all 0.7s cubic-bezier(0.25,0.46,0.45,0.94);
        `;
        document.body.appendChild(dot);
        requestAnimationFrame(() => {
            dot.style.left = `${cRect.left + cRect.width/2 - 6}px`;
            dot.style.top  = `${cRect.top  + cRect.height/2 - 6}px`;
            dot.style.opacity = '0';
            dot.style.transform = 'scale(0.2)';
        });
        setTimeout(() => dot.remove(), 750);
    }

    // ── localStorage: restore badge instantly before server responds ──
    try {
        const savedCount = parseInt(localStorage.getItem('cartCount') || '0');
        if (savedCount > 0) updateCartBadge(savedCount);
    } catch(e) {}


    // ══════════════════════════════════════
    //  🛒 CART DRAWER
    // ══════════════════════════════════════

    const drawer       = document.getElementById('cartDrawer');
    const drawerOverlay = document.getElementById('cartDrawerOverlay');
    const drawerBody   = document.getElementById('cartDrawerBody');
    const drawerTotal  = document.getElementById('cartDrawerTotal');
    const drawerCount  = document.getElementById('cartDrawerCount');

    function openDrawer() {
        if (!drawer) return;
        drawer.classList.add('open');
        drawerOverlay?.classList.add('open');
        document.body.style.overflow = 'hidden';
        refreshDrawer();
    }

    function closeDrawer() {
        if (!drawer) return;
        drawer.classList.remove('open');
        drawerOverlay?.classList.remove('open');
        document.body.style.overflow = '';
    }

    // ── Intercept cart nav link → open drawer instead of navigating ──
    document.querySelectorAll('.nav-link[href*="/cart/"], .nav-link[href$="/cart"]').forEach(link => {
        link.addEventListener('click', function(e) {
            // Only intercept on pages that are NOT the cart page
            if (!document.querySelector('.cart-page-full')) {
                e.preventDefault();
                openDrawer();
            }
        });
    });

    // ── Drawer overlay / close button ──
    drawerOverlay?.addEventListener('click', closeDrawer);
    document.getElementById('cartDrawerClose')?.addEventListener('click', closeDrawer);

    // ── Escape key closes drawer ──
    document.addEventListener('keydown', e => {
        if (e.key === 'Escape') closeDrawer();
    });

    // ── Refresh drawer contents via AJAX ──
    async function refreshDrawer() {
        if (!drawerBody) return;
        drawerBody.innerHTML = `
            <div class="drawer-loading">
                <div class="drawer-spinner"></div>
                <span>লোড হচ্ছে...</span>
            </div>`;
        try {
            const res  = await fetch('/cart/', { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
            const data = await res.json();

            if (!data.success) { drawerBody.innerHTML = '<p class="drawer-empty">কার্ট খালি</p>'; return; }

            const items = data.items || [];
            updateCartBadge(data.cart_count || 0);
            if (drawerTotal)  drawerTotal.textContent  = '৳' + Math.round(data.grand_total || 0);
            if (drawerCount)  drawerCount.textContent  = items.length + 'টি পণ্য';

            if (items.length === 0) {
                drawerBody.innerHTML = `
                    <div class="drawer-empty">
                        <div style="font-size:3rem;margin-bottom:12px;">🛒</div>
                        <p>কার্ট এখন খালি</p>
                        <a href="/products/" class="btn btn-sm btn-primary mt-2" onclick="closeDrawer && closeDrawer()">খাতা দেখুন →</a>
                    </div>`;
                return;
            }

            drawerBody.innerHTML = items.map(item => `
                <div class="drawer-item" data-product-id="${item.product_id}">
                    <div class="drawer-item-img">
                        ${item.image
                            ? `<img src="${item.image}" alt="${item.name}" loading="lazy">`
                            : `<div class="drawer-item-img-placeholder">📚</div>`}
                    </div>
                    <div class="drawer-item-info">
                        <div class="drawer-item-name">${item.name}</div>
                        <div class="drawer-item-price">
                            ৳${Math.round(item.price)}
                            ${item.is_on_sale ? `<span class="drawer-sale-tag">Sale</span>` : ''}
                        </div>
                        <div class="drawer-item-controls">
                            <button class="drawer-qty-btn drawer-qty-minus" data-pid="${item.product_id}">−</button>
                            <span class="drawer-qty-num">${item.quantity}</span>
                            <button class="drawer-qty-btn drawer-qty-plus" data-pid="${item.product_id}">+</button>
                        </div>
                    </div>
                    <a href="/remove-from-cart/${item.product_id}/"
                       class="drawer-remove-btn remove-item-btn"
                       title="Remove">×</a>
                </div>
            `).join('');

            // Bind qty buttons inside drawer
            bindDrawerQty();

        } catch(err) {
            drawerBody.innerHTML = '<p class="drawer-empty">লোড হয়নি। রিফ্রেশ করুন।</p>';
        }
    }

    function bindDrawerQty() {
        drawerBody?.querySelectorAll('.drawer-qty-minus, .drawer-qty-plus').forEach(btn => {
            btn.addEventListener('click', async function() {
                const pid  = this.dataset.pid;
                const row  = this.closest('.drawer-item');
                const qEl  = row.querySelector('.drawer-qty-num');
                const isIncrease = this.classList.contains('drawer-qty-plus');
                let qty = parseInt(qEl.textContent) + (isIncrease ? 1 : -1);
                if (qty < 1) qty = 1;

                try {
                    const res  = await fetch(`/update-cart/${pid}/`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': getCookie('csrftoken'),
                        },
                        body: JSON.stringify({ quantity: qty })
                    });
                    const data = await res.json();
                    if (data.success) {
                        qEl.textContent = qty;
                        if (drawerTotal) drawerTotal.textContent = '৳' + Math.round(data.grand_total || 0);
                        updateCartBadge(data.cart_count);
                        // Also sync cart page if open
                        syncCartPageTotal(data);
                    }
                } catch(e) { showToast('Update failed', 'error'); }
            });
        });

        // Bind remove buttons inside drawer (reuses same endpoint as page)
        drawerBody?.querySelectorAll('.drawer-remove-btn').forEach(btn => {
            btn.addEventListener('click', async function(e) {
                e.preventDefault();
                const href = this.getAttribute('href');
                const row  = this.closest('.drawer-item');
                try {
                    const res  = await fetch(href, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
                    const data = await res.json();
                    if (data.success) {
                        row.style.transition = 'all 0.3s ease';
                        row.style.opacity = '0';
                        row.style.transform = 'translateX(30px)';
                        setTimeout(() => {
                            row.remove();
                            updateCartBadge(data.cart_count);
                            if (drawerTotal) drawerTotal.textContent = '৳' + Math.round(data.grand_total || 0);
                            if (data.cart_count === 0) refreshDrawer();
                            syncCartPageTotal(data);
                        }, 320);
                        showToast('Removed', 'info');
                    }
                } catch(e) { showToast('Error', 'error'); }
            });
        });
    }

    // ── Sync cart page totals if user is ON /cart/ ──
    function syncCartPageTotal(data) {
        const totalEl = document.querySelector('.summary-total-amt');
        if (totalEl && data.grand_total !== undefined) {
            totalEl.textContent = '৳' + Math.round(data.grand_total);
        }
    }


    // ══════════════════════════════════════
    //  ➕ ADD TO CART (product pages)
    // ══════════════════════════════════════

    document.querySelectorAll('.add-to-cart-btn').forEach(btn => {
        btn.addEventListener('click', async function(e) {
            e.preventDefault();
            const productId = this.dataset.productId;
            const orig = this.innerHTML;
            this.disabled = true;

            try {
                const res  = await fetch(`/add-to-cart/${productId}/`, {
                    headers: { 'X-Requested-With': 'XMLHttpRequest' }
                });
                const data = await res.json();

                if (data.success) {
                    this.innerHTML = '<i class="fas fa-check"></i>';
                    this.style.background = 'linear-gradient(135deg,#00e5b0,#00d084)';
                    updateCartBadge(data.cart_count);
                    showToast('কার্টে যোগ হয়েছে ✓', 'success');
                    flyToCart(this);

                    // If drawer exists, refresh it
                    if (drawer) refreshDrawer();

                    setTimeout(() => {
                        this.innerHTML = orig;
                        this.style.background = '';
                        this.disabled = false;
                    }, 1800);
                }
            } catch(err) {
                this.disabled = false;
                showToast('Failed. Try again.', 'error');
            }
        });
    });


    // ══════════════════════════════════════
    //  🔢 QTY BUTTONS (cart page)
    // ══════════════════════════════════════

    document.querySelectorAll('.qty-decrease, .qty-increase').forEach(btn => {
        btn.addEventListener('click', async function() {
            const row        = this.closest('[data-product-id]');
            const pid        = row.dataset.productId;
            const qtyEl      = row.querySelector('.qty-num');
            const isIncrease = this.classList.contains('qty-increase');
            let   qty        = parseInt(qtyEl.textContent) + (isIncrease ? 1 : -1);
            if (qty < 1) qty = 1;

            try {
                const res  = await fetch(`/update-cart/${pid}/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCookie('csrftoken'),
                    },
                    body: JSON.stringify({ quantity: qty })
                });
                const data = await res.json();

                if (data.success) {
                    qtyEl.textContent = qty;

                    const subtotalEl = row.querySelector('.ci-subtotal');
                    if (subtotalEl && data.item_subtotal !== undefined) {
                        subtotalEl.textContent = '৳' + parseFloat(data.item_subtotal).toFixed(0);
                    }

                    // ✅ FIXED: use data.grand_total (not hardcoded +110)
                    syncCartPageTotal(data);
                    updateCartBadge(data.cart_count);

                    qtyEl.style.transform = 'scale(1.3)';
                    setTimeout(() => qtyEl.style.transform = '', 200);
                }
            } catch(err) { showToast('Update failed', 'error'); }
        });
    });


    // ══════════════════════════════════════
    //  ❌ REMOVE FROM CART (cart page)
    // ══════════════════════════════════════

    document.querySelectorAll('.remove-item-btn').forEach(btn => {
        // Skip drawer remove buttons (already handled in bindDrawerQty)
        if (btn.closest('#cartDrawer')) return;

        btn.addEventListener('click', async function(e) {
            e.preventDefault();
            const href = this.getAttribute('href');
            const row  = this.closest('[data-product-id]') || this.closest('.cart-item-row');

            try {
                const res  = await fetch(href, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
                const data = await res.json();

                if (data.success) {
                    row.style.animation = 'slideOutRight 0.35s ease forwards';
                    setTimeout(() => {
                        row.remove();
                        updateCartBadge(data.cart_count);
                        // ✅ FIXED: use data.grand_total
                        syncCartPageTotal(data);
                        if (data.cart_count === 0) location.reload();
                    }, 380);
                    showToast('Removed', 'info');
                }
            } catch(err) { showToast('Error removing item', 'error'); }
        });
    });


    // ── Animations ──
    const s = document.createElement('style');
    s.textContent = `
        @keyframes slideOutRight {
            to { transform: translateX(60px); opacity: 0; }
        }
        .qty-num { transition: transform 0.2s ease; }
    `;
    document.head.appendChild(s);

    console.log('🛒 Cart.js v3 loaded — drawer ready');
});
