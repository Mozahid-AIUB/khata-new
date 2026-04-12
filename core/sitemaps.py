"""
core/sitemaps.py — Auto-generated XML sitemap for Practical Khata
Registered in config/urls.py via django.contrib.sitemaps.views.sitemap
"""
from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from .models import Product, Category


class StaticSitemap(Sitemap):
    """Static pages — home, products listing, register, login."""
    changefreq = 'weekly'
    priority    = 0.8

    def items(self):
        return ['home', 'products', 'register', 'login']

    def location(self, item):
        return reverse(item)

    def lastmod(self, item):
        return None


class ProductSitemap(Sitemap):
    """One URL per product — highest priority for SEO."""
    changefreq = 'daily'
    priority    = 1.0

    def items(self):
        return Product.objects.filter(stock__gt=0).order_by('-updated_at')

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return reverse('product_detail', kwargs={'slug': obj.slug})


class CategorySitemap(Sitemap):
    """One URL per category."""
    changefreq = 'weekly'
    priority    = 0.7

    def items(self):
        return Category.objects.all()

    def location(self, obj):
        return reverse('products_by_category', kwargs={'slug': obj.slug})


# Dict passed to sitemap view
SITEMAPS = {
    'static':     StaticSitemap,
    'products':   ProductSitemap,
    'categories': CategorySitemap,
}
