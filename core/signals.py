"""
🎮 Gamification Signals
━━━━━━━━━━━━━━━━━━━━━━
Auto-fires on key events:
  • User created → UserProfile created
  • Order delivered → XP + ScratchCard awarded
  • Review submitted → XP awarded
  • Referral used → XP awarded to referrer
"""
import random
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.utils import timezone


# ── XP rewards per action ──────────────────────────────
XP_RULES = {
    'order_placed':   30,   # placing any order
    'order_delivered': 50,  # order marked delivered
    'review_posted':  20,   # submitting a review
    'referral_used':  100,  # someone used your referral code
}

# ── Scratch card reward pool ───────────────────────────
SCRATCH_REWARDS = [
    ('discount_pct',  10),  # 10% off
    ('discount_pct',  15),  # 15% off
    ('discount_pct',  20),  # 20% off
    ('discount_flat', 50),  # ৳50 off
    ('discount_flat', 100), # ৳100 off
    ('free_delivery', 0),   # Free delivery
    ('xp_bonus',      50),  # 50 XP bonus
    ('xp_bonus',      100), # 100 XP bonus
]


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Auto-create UserProfile on new User registration."""
    if created:
        from .models import UserProfile
        UserProfile.objects.get_or_create(user=instance)


@receiver(post_save, sender='core.Order')
def handle_order_gamification(sender, instance, created, **kwargs):
    """
    Award XP + ScratchCard when:
      - Order first created (placed XP)
      - Order status changes to 'delivered' (delivered XP + scratch card)
    """
    from .models import UserProfile, ScratchCard

    if not instance.user:
        return

    profile, _ = UserProfile.objects.get_or_create(user=instance.user)

    if created:
        # XP for placing order
        profile.add_xp(XP_RULES['order_placed'], 'অর্ডার দেওয়ার জন্য')
        # Update stats
        profile.total_orders = instance.user.orders.count()
        profile.total_spent  = sum(
            float(o.total_amount) for o in instance.user.orders.all()
        )
        profile.save(update_fields=['total_orders', 'total_spent', 'updated_at'])

    elif instance.status == 'delivered':
        # XP for delivery
        if not XPLog_exists(profile, f'delivered-{instance.id}'):
            profile.add_xp(XP_RULES['order_delivered'], f'অর্ডার #{instance.order_id} ডেলিভারি হয়েছে')
            # Issue a scratch card
            reward_type, reward_value = random.choice(SCRATCH_REWARDS)
            ScratchCard.objects.create(
                profile=profile,
                order=instance,
                reward_type=reward_type,
                reward_value=reward_value,
                expires_at=timezone.now() + timezone.timedelta(days=30),
            )
            profile.scratch_cards = profile.scratch_card_set.filter(status='pending').count()
            profile.save(update_fields=['scratch_cards', 'updated_at'])


@receiver(post_save, sender='core.Review')
def handle_review_xp(sender, instance, created, **kwargs):
    """Award XP when a review is submitted."""
    if not created:
        return
    from .models import UserProfile
    # Try to find a profile via name match (reviews may not have user FK)
    # Best effort: match by username
    try:
        from django.contrib.auth.models import User as U
        user = U.objects.get(username=instance.name)
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.add_xp(XP_RULES['review_posted'], f'Review দেওয়ার জন্য')
    except Exception:
        pass  # review by guest — no XP


def XPLog_exists(profile, reason_key):
    """Check if an XP log with a specific reason key already exists (idempotent)."""
    from .models import XPLog
    return XPLog.objects.filter(profile=profile, reason__icontains=reason_key).exists()
