import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_order_order_id_payment_ssl'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # ── UserProfile ──────────────────────────────────────
        migrations.CreateModel(
            name='UserProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('xp', models.PositiveIntegerField(default=0)),
                ('referral_code', models.CharField(max_length=12, unique=True, blank=True)),
                ('total_orders', models.PositiveIntegerField(default=0)),
                ('total_spent', models.DecimalField(max_digits=10, decimal_places=2, default=0)),
                ('scratch_cards', models.PositiveIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='profile',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('referred_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='referrals',
                    to='core.userprofile',
                )),
            ],
        ),

        # ── XPLog ────────────────────────────────────────────
        migrations.CreateModel(
            name='XPLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('amount', models.IntegerField()),
                ('reason', models.CharField(max_length=200)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('profile', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='xp_logs',
                    to='core.userprofile',
                )),
            ],
            options={'ordering': ['-created_at']},
        ),

        # ── Badge ────────────────────────────────────────────
        migrations.CreateModel(
            name='Badge',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('badge_slug', models.CharField(max_length=30)),
                ('earned_at', models.DateTimeField(auto_now_add=True)),
                ('profile', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='badges',
                    to='core.userprofile',
                )),
            ],
            options={'ordering': ['-earned_at'],
                     'unique_together': {('profile', 'badge_slug')}},
        ),

        # ── ScratchCard ──────────────────────────────────────
        migrations.CreateModel(
            name='ScratchCard',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('status', models.CharField(
                    choices=[('pending','Pending'),('scratched','Scratched'),('expired','Expired')],
                    default='pending', max_length=10,
                )),
                ('reward_type', models.CharField(
                    choices=[('discount_pct','Discount %'),('discount_flat','Discount Flat'),
                             ('free_delivery','Free Delivery'),('xp_bonus','XP Bonus')],
                    default='discount_pct', max_length=20,
                )),
                ('reward_value', models.PositiveIntegerField(default=10)),
                ('coupon_code', models.CharField(max_length=20, blank=True)),
                ('expires_at', models.DateTimeField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('scratched_at', models.DateTimeField(null=True, blank=True)),
                ('profile', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='scratch_card_set',
                    to='core.userprofile',
                )),
                ('order', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='scratch_cards',
                    to='core.order',
                )),
            ],
        ),
    ]
