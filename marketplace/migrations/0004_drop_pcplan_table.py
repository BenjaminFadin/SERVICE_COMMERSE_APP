from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('marketplace', '0003_remove_appointment_plan_delete_pcplan'),
    ]

    operations = [
        migrations.RunSQL(
            sql='DROP TABLE IF EXISTS marketplace_pcplan CASCADE;',
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
