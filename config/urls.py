from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import Http404

# ── Hidden Admin URL ──────────────────────────────────────────
# /admin/ এ গেলে 404 দেখাবে — real admin URL টা secret
# .env তে ADMIN_URL=your-secret-path দাও
ADMIN_URL = getattr(settings, 'ADMIN_URL', 'secret-admin-2024')

urlpatterns = [
    path(f'{ADMIN_URL}/', admin.site.urls),
    path('admin/', lambda r: (_ for _ in ()).throw(Http404())),  # fake 404
    path('', include('core.urls')),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])