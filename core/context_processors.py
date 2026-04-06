from .models import SiteSettings, FlashSale
from django.utils import timezone


def cart_count(request):
    cart = request.session.get('cart', {})
    total_items = sum(item.get('quantity', 0) for item in cart.values())
    return {'cart_count': total_items}


def site_settings(request):
    """Injects SiteSettings and active FlashSale into every template."""
    settings = SiteSettings.get()
    flash_sale = FlashSale.objects.filter(
        is_active=True,
        ends_at__gt=timezone.now()
    ).first()

    return {
        'site_settings': settings,
        'flash_sale': flash_sale,
        'whatsapp_number': settings.whatsapp_number,
        'delivery_charge': settings.delivery_charge,
        'chat_enabled': settings.chat_enabled,
        'chat_welcome_msg': settings.chat_welcome_msg,
    }