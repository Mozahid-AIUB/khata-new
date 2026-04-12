from django.db import migrations, models


def generate_order_ids(apps, schema_editor):
    """Populate unique order_id for existing orders."""
    Order = apps.get_model('core', 'Order')
    for order in Order.objects.all():
        year = order.created_at.year
        order.order_id = f'PK-{year}{order.id:04d}'
        order.save(update_fields=['order_id'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_flashsale_productimage_sitesettings_supportmessage_and_more'),
    ]

    operations = [
        # Step 1: Add order_id as nullable first (no unique yet)
        migrations.AddField(
            model_name='order',
            name='order_id',
            field=models.CharField(
                blank=True, null=True, max_length=30,
                help_text='Auto-generated: PK-YYYYXXXX',
            ),
        ),
        # Step 2: Populate unique values for existing rows
        migrations.RunPython(generate_order_ids, migrations.RunPython.noop),
        # Step 3: Now make it unique + not null
        migrations.AlterField(
            model_name='order',
            name='order_id',
            field=models.CharField(
                blank=True, max_length=30, unique=True,
                help_text='Auto-generated: PK-YYYYXXXX',
                default='',
            ),
        ),
        # Add payment_status field
        migrations.AddField(
            model_name='order',
            name='payment_status',
            field=models.CharField(
                choices=[
                    ('unpaid',    'Unpaid'),
                    ('paid',      'Paid'),
                    ('failed',    'Failed'),
                    ('cancelled', 'Cancelled'),
                    ('refunded',  'Refunded'),
                ],
                default='unpaid',
                max_length=20,
            ),
        ),
        # Add ssl_transaction_id field
        migrations.AddField(
            model_name='order',
            name='ssl_transaction_id',
            field=models.CharField(
                blank=True, max_length=100,
                help_text='SSLCommerz bank_tran_id',
            ),
        ),
        # Update payment_method choices + max_length
        migrations.AlterField(
            model_name='order',
            name='payment_method',
            field=models.CharField(
                blank=True,
                choices=[
                    ('bkash',      'bKash'),
                    ('nagad',      'Nagad'),
                    ('cash',       'Cash on Delivery'),
                    ('sslcommerz', 'Card / Online (SSLCommerz)'),
                    ('other',      'Other'),
                ],
                default='bkash',
                max_length=20,
            ),
        ),
        # Update payment_ref max_length
        migrations.AlterField(
            model_name='order',
            name='payment_ref',
            field=models.CharField(
                blank=True, max_length=200,
                help_text='bKash/Nagad TrxID or SSLCommerz val_id',
            ),
        ),
    ]
