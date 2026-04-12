from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import Http404, HttpResponse
from django.contrib.sitemaps.views import sitemap
from core.sitemaps import SITEMAPS

# ── Hidden Admin URL ──────────────────────────────────────────
# /admin/ এ গেলে 404 দেখাবে — real admin URL টা secret
# .env তে ADMIN_URL=your-secret-path দাও
ADMIN_URL = getattr(settings, 'ADMIN_URL', 'secret-admin-2024')


def robots_txt(request):
    """
    Serve /robots.txt dynamically.
    Allows all bots on product/category pages; disallows admin & checkout.
    """
    site = f"{request.scheme}://{request.get_host()}"
    content = f"""User-agent: *
Disallow: /{ADMIN_URL}/
Disallow: /checkout/
Disallow: /cart/
Disallow: /payment/
Disallow: /manage/
Disallow: /dashboard/
Allow: /

Sitemap: {site}/sitemap.xml
"""
    return HttpResponse(content, content_type='text/plain')


urlpatterns = [
    path(f'{ADMIN_URL}/', admin.site.urls),
    path('admin/', lambda r: (_ for _ in ()).throw(Http404())),  # fake 404

    # ── SEO ──────────────────────────────────────────────────
    path('sitemap.xml', sitemap, {'sitemaps': SITEMAPS},
         name='django.contrib.sitemaps.views.sitemap'),
    path('robots.txt', robots_txt, name='robots_txt'),

    path('', include('core.urls')),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])