"""
Run this script from project root:
python fix_dashboard.py
"""
import os

content = '''{% extends 'base.html' %}
{% block title %}My Dashboard{% endblock %}
{% block content %}
<section class="py-5">
<div class="container" style="max-width:800px;">

    <!-- Profile Header -->
    <div class="dash-header">
        <div class="dash-avatar">{{ request.user.username|slice:":2"|upper }}</div>
        <div>
            <h2 class="dash-name">{{ request.user.username }}</h2>
            <p class="dash-email">{{ request.user.email|default:"No email" }}</p>
        </div>
        <a href="{% url 'logout' %}" class="dash-logout">Logout</a>
    </div>

    <!-- Stats Row -->
    <div class="dash-stats-row">
        <div class="dash-stat">
            <div class="dash-stat-num">{{ stats.total_orders }}</div>
            <div class="dash-stat-label">মোট Orders</div>
        </div>
        <div class="dash-stat">
            <div class="dash-stat-num" style="color:#00e5b0;">৳{{ stats.total_spent|floatformat:0 }}</div>
            <div class="dash-stat-label">মোট খরচ</div>
        </div>
        <div class="dash-stat">
            <div class="dash-stat-num" style="color:#f59e0b;">{{ stats.pending }}</div>
            <div class="dash-stat-label">Pending</div>
        </div>
        <div class="dash-stat">
            <div class="dash-stat-num" style="color:#00ff87;">{{ stats.delivered }}</div>
            <div class="dash-stat-label">Delivered</div>
        </div>
    </div>

    <h3 class="dash-section-title">📦 আমার Orders</h3>

    {% if orders %}
    {% for order in orders %}
    <div class="dash-order-card">
        <div class="dao-top">
            <div>
                <span class="dao-id">Order #{{ order.id }}</span>
                <span class="dao-date">{{ order.created_at|date:"d M Y" }}</span>
            </div>
            <span class="dao-status status-{{ order.status }}">{{ order.get_status_display }}</span>
        </div>
        <div class="dao-items">
            {% for item in order.items.all %}
            <span class="dao-item-tag">{{ item.name|default:item.product.name }} x{{ item.quantity }}</span>
            {% endfor %}
        </div>
        <div class="dao-footer">
            <span class="dao-total">৳{{ order.grand_total|floatformat:0 }}</span>
            <a href="{% url 'order_tracking' order.id %}" class="dao-track-btn">Track করো</a>
        </div>
    </div>
    {% endfor %}
    {% else %}
    <div class="dash-empty">
        <div style="font-size:3rem;margin-bottom:12px;">📭</div>
        <p>এখনো কোনো order করোনি।</p>
        <a href="{% url 'products' %}" class="btn btn-primary px-4 mt-2">Products দেখো</a>
    </div>
    {% endif %}

</div>
</section>

<style>
.dash-header{display:flex;align-items:center;gap:16px;margin-bottom:20px;padding:20px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);border-radius:14px;}
.dash-avatar{width:52px;height:52px;border-radius:50%;background:linear-gradient(135deg,#5b7fff,#7c3aed);display:flex;align-items:center;justify-content:center;font-size:1.1rem;font-weight:800;color:white;flex-shrink:0;}
.dash-name{font-size:1.1rem!important;font-weight:700!important;color:#e8ecf4;margin:0 0 2px;}
.dash-email{font-size:0.82rem!important;color:#6b7a99;margin:0;}
.dash-logout{margin-left:auto;font-size:0.8rem;color:#f472b6;border:1px solid rgba(244,114,182,0.3);border-radius:8px;padding:5px 12px;text-decoration:none;}
.dash-logout:hover{background:rgba(244,114,182,0.1);color:#f472b6;}
.dash-stats-row{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:28px;}
.dash-stat{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);border-radius:12px;padding:16px;text-align:center;transition:border-color 0.2s;}
.dash-stat:hover{border-color:rgba(91,127,255,0.3);}
.dash-stat-num{font-size:1.4rem;font-weight:900;color:#e8ecf4;}
.dash-stat-label{font-size:0.75rem;color:#6b7a99;margin-top:4px;}
.dash-section-title{font-size:1rem!important;font-weight:700!important;color:#e8ecf4;margin-bottom:16px;}
.dash-order-card{background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);border-radius:12px;padding:16px;margin-bottom:12px;transition:border-color 0.2s;}
.dash-order-card:hover{border-color:rgba(91,127,255,0.3);}
.dao-top{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;}
.dao-id{font-weight:700;font-size:0.9rem!important;color:#e8ecf4;margin-right:10px;}
.dao-date{font-size:0.78rem!important;color:#6b7a99;}
.dao-status{font-size:0.72rem!important;font-weight:700;padding:3px 10px;border-radius:20px;}
.status-pending{background:rgba(245,158,11,0.15);color:#f59e0b;}
.status-confirmed{background:rgba(91,127,255,0.15);color:#8ba4ff;}
.status-processing{background:rgba(167,139,250,0.15);color:#a78bfa;}
.status-dispatched{background:rgba(0,229,176,0.15);color:#00e5b0;}
.status-delivered{background:rgba(0,255,135,0.15);color:#00ff87;}
.status-cancelled{background:rgba(244,114,182,0.15);color:#f472b6;}
.dao-items{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px;}
.dao-item-tag{font-size:0.75rem!important;background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.08);border-radius:6px;padding:3px 10px;color:#9aa5c4;}
.dao-footer{display:flex;align-items:center;justify-content:space-between;}
.dao-total{font-weight:800;font-size:1rem!important;color:#00e5b0;}
.dao-track-btn{font-size:0.8rem;color:#8ba4ff;border:1px solid rgba(91,127,255,0.3);border-radius:8px;padding:5px 14px;text-decoration:none;}
.dao-track-btn:hover{background:rgba(91,127,255,0.15);color:#c0d0ff;}
.dash-empty{text-align:center;padding:48px 20px;color:#6b7a99;}
@media(max-width:576px){.dash-stats-row{grid-template-columns:repeat(2,1fr);}}
</style>
{% endblock %}
'''

# Write to both locations
paths = [
    'templates/dashboard.html',
    'core/templates/dashboard.html',
]

for path in paths:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✅ Written: {path} ({len(content.splitlines())} lines)")

print("\nDone! Now run: python manage.py runserver")
