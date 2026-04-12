from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_gamification'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='estimated_delivery_date',
            field=models.DateField(
                blank=True,
                null=True,
                help_text='Expected delivery date (set manually by admin or auto on confirmation)',
            ),
        ),
    ]
